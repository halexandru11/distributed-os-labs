#include <ctype.h>
#include <errno.h>
#include <limits.h>
#include <mpi.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* MPI Message Tags */
#define TAG_TASK_META 10
#define TAG_TASK_DATA 11
#define TAG_RESULT_META 12
#define TAG_RESULT_DATA 13
#define TAG_TERMINATE 99

/* Operation IDs */
typedef enum {
  OP_NONE = 0,
  OP_GRAYSCALE = 1, /* Cat 1: Color in-place */
  OP_INVERT = 2,    /* Cat 1: Color in-place */
  OP_SEPIA = 3,     /* Cat 1: Color in-place */
  OP_BLUR = 4,      /* Cat 2: Neighborhood (Box Blur) */
  OP_FLIP_H = 5,    /* Cat 3: Move pixels (Horizontal Flip) */
  OP_ROTATE90 = 6   /* Cat 3: Move pixels + change dimensions (90 deg CW) */
} OpType;

/* Parallelization Mode IDs */
typedef enum {
  MODE_SEQ = 0,
  MODE_STATIC_1D = 1,
  MODE_STATIC_2D = 2,
  MODE_DYNAMIC_1D = 3
} ModeType;

/* Task descriptor sent from Coordinator (Rank 0) to Workers */
typedef struct {
  int op;
  int blur_radius;
  int orig_w;
  int orig_h;
  /* Output region (in destination image coordinates) this worker is responsible
   * for */
  int out_x;
  int out_y;
  int out_w;
  int out_h;
  /* Input region (in source image coordinates, including halo/ghost cells) sent
   * to worker */
  int in_x;
  int in_y;
  int in_w;
  int in_h;
} TaskMeta;

typedef struct {
  int width;
  int height;
} ImageSize;

typedef struct {
  int x;
  int y;
  int width;
  int height;
} TileRegion;

/* Durations overlap across ranks, so total is not transfer + computation.
 * All fields exclude image I/O, worker shutdown, and the final timing reduction. */
typedef struct {
  double total;       /* Coordinator execution intervals across the pipeline. */
  double transfer;    /* Pure blocking MPI_Send / MPI_Recv time on rank 0. */
  double pack_unpack; /* Exact time spent in pack_submatrix & unpack_submatrix. */
  double computation; /* Local pixel processing; take MPI_MAX at shutdown. */
} ExecutionTiming;

#define DEFAULT_BLUR_KERNEL_SIZE 9

/* =========================================================================
 * PPM (P6) Image I/O (Direct Memory Matrix Representation)
 * ========================================================================= */
unsigned char *read_ppm(const char *filename, int *width, int *height) {
  FILE *fp = fopen(filename, "rb");
  if (!fp) {
    fprintf(stderr, "Error: Cannot open input file %s\n", filename);
    return NULL;
  }

  char magic[3];
  if (fscanf(fp, "%2s", magic) != 1 || strcmp(magic, "P6") != 0) {
    fprintf(stderr, "Error: Input must be binary PPM (P6) format.\n");
    fclose(fp);
    return NULL;
  }

  /* Skip comments and whitespace */
  int c = getc(fp);
  while (isspace(c) || c == '#') {
    if (c == '#') {
      while (c != '\n' && c != EOF)
        c = getc(fp);
    }
    c = getc(fp);
  }
  ungetc(c, fp);

  int maxval;
  if (fscanf(fp, "%d %d %d", width, height, &maxval) != 3) {
    fprintf(stderr, "Error: Failed to read PPM dimensions.\n");
    fclose(fp);
    return NULL;
  }
  fgetc(fp); /* consume single whitespace byte after maxval */

  size_t num_bytes = (size_t)(*width) * (*height) * 3;
  unsigned char *data = (unsigned char *)malloc(num_bytes);
  if (!data) {
    fprintf(stderr, "Error: Memory allocation failed for %zu bytes.\n",
            num_bytes);
    fclose(fp);
    return NULL;
  }

  if (fread(data, 1, num_bytes, fp) != num_bytes) {
    fprintf(stderr, "Error: Unexpected EOF while reading pixel matrix.\n");
    free(data);
    fclose(fp);
    return NULL;
  }

  fclose(fp);
  return data;
}

int write_ppm(const char *filename, const unsigned char *data, int width,
              int height) {
  FILE *fp = fopen(filename, "wb");
  if (!fp) {
    fprintf(stderr, "Error: Cannot open output file %s\n", filename);
    return 0;
  }
  fprintf(fp, "P6\n%d %d\n255\n", width, height);
  size_t num_bytes = (size_t)width * height * 3;
  fwrite(data, 1, num_bytes, fp);
  fclose(fp);
  return 1;
}

/* =========================================================================
 * Core Pixel Matrix Operations (Applied to a Submatrix / Tile)
 * ========================================================================= */
void process_submatrix(const TaskMeta *meta, const unsigned char *in_buf,
                       unsigned char *out_buf) {
  int out_w = meta->out_w;
  int out_h = meta->out_h;
  int in_w = meta->in_w;
  int in_h = meta->in_h;

  for (int r = 0; r < out_h; r++) {
    for (int c = 0; c < out_w; c++) {
      size_t out_idx = ((size_t)r * out_w + c) * 3;

      if (meta->op == OP_GRAYSCALE) {
        size_t in_idx = ((size_t)r * in_w + c) * 3;
        unsigned char R = in_buf[in_idx];
        unsigned char G = in_buf[in_idx + 1];
        unsigned char B = in_buf[in_idx + 2];
        unsigned char gray = (unsigned char)(0.299 * R + 0.587 * G + 0.114 * B);
        out_buf[out_idx] = out_buf[out_idx + 1] = out_buf[out_idx + 2] = gray;
      } else if (meta->op == OP_INVERT) {
        size_t in_idx = ((size_t)r * in_w + c) * 3;
        out_buf[out_idx] = 255 - in_buf[in_idx];
        out_buf[out_idx + 1] = 255 - in_buf[in_idx + 1];
        out_buf[out_idx + 2] = 255 - in_buf[in_idx + 2];
      } else if (meta->op == OP_SEPIA) {
        size_t in_idx = ((size_t)r * in_w + c) * 3;
        unsigned char R = in_buf[in_idx];
        unsigned char G = in_buf[in_idx + 1];
        unsigned char B = in_buf[in_idx + 2];
        int tr = (int)(0.393 * R + 0.769 * G + 0.189 * B);
        int tg = (int)(0.349 * R + 0.686 * G + 0.168 * B);
        int tb = (int)(0.272 * R + 0.534 * G + 0.131 * B);
        out_buf[out_idx] = (tr > 255) ? 255 : tr;
        out_buf[out_idx + 1] = (tg > 255) ? 255 : tg;
        out_buf[out_idx + 2] = (tb > 255) ? 255 : tb;
      } else if (meta->op == OP_BLUR) {
        int glob_r = meta->out_y + r;
        int glob_c = meta->out_x + c;
        int center_r = glob_r - meta->in_y;
        int center_c = glob_c - meta->in_x;

        int radius = meta->blur_radius;
        int r0 = center_r > radius ? center_r - radius : 0;
        int c0 = center_c > radius ? center_c - radius : 0;
        int r1 = radius < in_h - 1 - center_r ? center_r + radius : in_h - 1;
        int c1 = radius < in_w - 1 - center_c ? center_c + radius : in_w - 1;
        unsigned long long sum_r = 0, sum_g = 0, sum_b = 0, count = 0;
        for (int nr = r0; nr <= r1; nr++) {
          for (int nc = c0; nc <= c1; nc++) {
            size_t idx = ((size_t)nr * in_w + nc) * 3;
            sum_r += in_buf[idx];
            sum_g += in_buf[idx + 1];
            sum_b += in_buf[idx + 2];
            count++;
          }
        }
        out_buf[out_idx] = (unsigned char)(sum_r / count);
        out_buf[out_idx + 1] = (unsigned char)(sum_g / count);
        out_buf[out_idx + 2] = (unsigned char)(sum_b / count);
      } else if (meta->op == OP_FLIP_H) {
        int src_c = in_w - 1 - c;
        size_t in_idx = ((size_t)r * in_w + src_c) * 3;
        out_buf[out_idx] = in_buf[in_idx];
        out_buf[out_idx + 1] = in_buf[in_idx + 1];
        out_buf[out_idx + 2] = in_buf[in_idx + 2];
      } else if (meta->op == OP_ROTATE90) {
        int local_r = in_h - 1 - c;
        int local_c = r;
        size_t in_idx = ((size_t)local_r * in_w + local_c) * 3;
        out_buf[out_idx] = in_buf[in_idx];
        out_buf[out_idx + 1] = in_buf[in_idx + 1];
        out_buf[out_idx + 2] = in_buf[in_idx + 2];
      }
    }
  }
}

static ImageSize operation_output_size(OpType op, ImageSize input) {
  if (op == OP_ROTATE90) {
    return (ImageSize){input.height, input.width};
  }
  return input;
}

static TaskMeta make_tile_task(OpType op, int blur_radius, ImageSize input,
                              TileRegion output) {
  TaskMeta task = {.op = op,
                   .blur_radius = blur_radius,
                   .orig_w = input.width,
                   .orig_h = input.height,
                   .out_x = output.x,
                   .out_y = output.y,
                   .out_w = output.width,
                   .out_h = output.height};
  if (output.width == 0 || output.height == 0)
    return task;
  if (task.op == OP_GRAYSCALE || task.op == OP_INVERT || task.op == OP_SEPIA) {
    task.in_x = task.out_x;
    task.in_y = task.out_y;
    task.in_w = task.out_w;
    task.in_h = task.out_h;
  } else if (task.op == OP_BLUR) {
    int x0 = task.out_x - blur_radius;
    int y0 = task.out_y - blur_radius;
    int x1 = task.out_x + task.out_w;
    int y1 = task.out_y + task.out_h;
    x1 += blur_radius < task.orig_w - x1 ? blur_radius : task.orig_w - x1;
    y1 += blur_radius < task.orig_h - y1 ? blur_radius : task.orig_h - y1;
    if (x0 < 0)
      x0 = 0;
    if (y0 < 0)
      y0 = 0;
    task.in_x = x0;
    task.in_y = y0;
    task.in_w = x1 - x0;
    task.in_h = y1 - y0;
  } else if (task.op == OP_FLIP_H) {
    task.in_x = task.orig_w - (task.out_x + task.out_w);
    task.in_y = task.out_y;
    task.in_w = task.out_w;
    task.in_h = task.out_h;
  } else if (task.op == OP_ROTATE90) {
    task.in_x = task.out_y;
    task.in_y = task.orig_h - (task.out_x + task.out_w);
    task.in_w = task.out_h;
    task.in_h = task.out_w;
  }
  return task;
}

/* Pack a 2D submatrix from full image into a contiguous buffer */
void pack_submatrix(const unsigned char *full_img, int full_w, int sub_x,
                    int sub_y, int sub_w, int sub_h,
                    unsigned char *packed_buf) {
  for (int r = 0; r < sub_h; r++) {
    const unsigned char *src_row =
        full_img + ((size_t)(sub_y + r) * full_w + sub_x) * 3;
    unsigned char *dst_row = packed_buf + ((size_t)r * sub_w) * 3;
    memcpy(dst_row, src_row, (size_t)sub_w * 3);
  }
}

/* Unpack a contiguous buffer back into a 2D submatrix of the full output image */
void unpack_submatrix(const unsigned char *packed_buf, unsigned char *full_img,
                      int full_w, int sub_x, int sub_y, int sub_w, int sub_h) {
  for (int r = 0; r < sub_h; r++) {
    const unsigned char *src_row = packed_buf + ((size_t)r * sub_w) * 3;
    unsigned char *dst_row =
        full_img + ((size_t)(sub_y + r) * full_w + sub_x) * 3;
    memcpy(dst_row, src_row, (size_t)sub_w * 3);
  }
}

/* =========================================================================
 * Tile Transfer: blocking metadata and pixel messages, with owned scratch
 * buffers and separate timing for pack/unpack vs MPI communication
 * ========================================================================= */
static int tile_byte_count(int width, int height) {
  if (width < 0 || height < 0 ||
      (height != 0 && (size_t)width > (size_t)INT_MAX / 3 / (size_t)height)) {
    fprintf(stderr, "Error: Tile exceeds the MPI message count limit.\n");
    MPI_Abort(MPI_COMM_WORLD, 1);
    exit(EXIT_FAILURE);
  }
  return (int)((size_t)width * (size_t)height * 3);
}

static unsigned char *allocate_tile(int bytes) {
  unsigned char *buffer = malloc(bytes > 0 ? (size_t)bytes : 1);
  if (!buffer) {
    fprintf(stderr, "Error: Cannot allocate tile buffer.\n");
    MPI_Abort(MPI_COMM_WORLD, 1);
    exit(EXIT_FAILURE);
  }
  return buffer;
}

static void send_tile_task(int worker_rank, const TaskMeta *task,
                           const unsigned char *source, double *t_comm,
                           double *t_pack) {
  int bytes = tile_byte_count(task->in_w, task->in_h);
  unsigned char *packed = NULL;
  const unsigned char *pixels = source;
  if (bytes > 0) {
    if (task->in_x == 0 && task->in_w == task->orig_w) {
      pixels = source + (size_t)task->in_y * task->orig_w * 3;
    } else {
      double p0 = MPI_Wtime();
      packed = allocate_tile(bytes);
      pack_submatrix(source, task->orig_w, task->in_x, task->in_y, task->in_w,
                     task->in_h, packed);
      *t_pack += (MPI_Wtime() - p0);
      pixels = packed;
    }
  }
  double c0 = MPI_Wtime();
  MPI_Send(task, sizeof(*task), MPI_BYTE, worker_rank, TAG_TASK_META,
           MPI_COMM_WORLD);
  MPI_Send(pixels, bytes, MPI_UNSIGNED_CHAR, worker_rank, TAG_TASK_DATA,
           MPI_COMM_WORLD);
  *t_comm += (MPI_Wtime() - c0);
  free(packed);
}

static int receive_tile_result(int worker_rank, unsigned char *destination,
                               int width, double *t_comm, double *t_unpack) {
  TaskMeta task;
  MPI_Status status;
  double c0 = MPI_Wtime();
  MPI_Recv(&task, sizeof(task), MPI_BYTE, worker_rank, TAG_RESULT_META,
           MPI_COMM_WORLD, &status);
  *t_comm += (MPI_Wtime() - c0);

  int bytes = tile_byte_count(task.out_w, task.out_h);
  unsigned char *packed = NULL;
  unsigned char *pixels = destination;
  if (bytes > 0) {
    if (task.out_x == 0 && task.out_w == width) {
      pixels = destination + (size_t)task.out_y * width * 3;
    } else {
      double p0 = MPI_Wtime();
      packed = allocate_tile(bytes);
      *t_unpack += (MPI_Wtime() - p0);
      pixels = packed;
    }
  }

  double c1 = MPI_Wtime();
  MPI_Recv(pixels, bytes, MPI_UNSIGNED_CHAR, status.MPI_SOURCE, TAG_RESULT_DATA,
           MPI_COMM_WORLD, MPI_STATUS_IGNORE);
  *t_comm += (MPI_Wtime() - c1);

  if (packed) {
    double p1 = MPI_Wtime();
    unpack_submatrix(packed, destination, width, task.out_x, task.out_y,
                     task.out_w, task.out_h);
    free(packed);
    *t_unpack += (MPI_Wtime() - p1);
  }
  return status.MPI_SOURCE;
}

/* =========================================================================
 * Coordinator Execution for One Operation in the Pipeline
 * ========================================================================= */
void execute_operation_coordinator(OpType op, ModeType mode, int blur_radius,
                                   int num_procs, unsigned char **img_ptr, int *w_ptr,
                                   int *h_ptr, ExecutionTiming *timing) {
  int orig_w = *w_ptr;
  int orig_h = *h_ptr;
  ImageSize input = {orig_w, orig_h};
  ImageSize output = operation_output_size(op, input);
  int new_w = output.width;
  int new_h = output.height;

  unsigned char *src_img = *img_ptr;
  unsigned char *dst_img = (unsigned char *)malloc((size_t)new_w * new_h * 3);

  double t_start = MPI_Wtime();
  double t_comm_acc = 0.0;
  double t_pack_acc = 0.0;
  double t_comp_acc = 0.0;

  int num_workers = num_procs - 1;

  /* 1. SEQUENTIAL MODE (or if launched with -np 1) */
  if (mode == MODE_SEQ || num_workers < 1) {
    TaskMeta meta = make_tile_task(op, blur_radius, input,
                                   (TileRegion){0, 0, new_w, new_h});
    double c0 = MPI_Wtime();
    process_submatrix(&meta, src_img, dst_img);
    t_comp_acc += (MPI_Wtime() - c0);
  }
  /* 2. STATIC 1D (Horizontal Strips) */
  else if (mode == MODE_STATIC_1D) {
    int rows_per_worker = new_h / num_workers;
    int rem = new_h % num_workers;
    int cur_y = 0;

    TaskMeta *tasks = (TaskMeta *)malloc(sizeof(TaskMeta) * num_workers);

    for (int w = 0; w < num_workers; w++) {
      int worker_rank = w + 1;
      int h_slice = rows_per_worker + (w < rem ? 1 : 0);

      tasks[w] = make_tile_task(op, blur_radius, input,
                                (TileRegion){0, cur_y, new_w, h_slice});
      cur_y += h_slice;

      send_tile_task(worker_rank, &tasks[w], src_img, &t_comm_acc, &t_pack_acc);
    }

    for (int w = 0; w < num_workers; w++) {
      int worker_rank = w + 1;
      receive_tile_result(worker_rank, dst_img, new_w, &t_comm_acc, &t_pack_acc);
    }
    free(tasks);
  }
  /* 3. STATIC 2D (Grid Tiles) */
  else if (mode == MODE_STATIC_2D) {
    int grid_cols = 1, grid_rows = num_workers;
    for (int i = 1; i * i <= num_workers; i++) {
      if (num_workers % i == 0) {
        grid_cols = i;
        grid_rows = num_workers / i;
      }
    }

    TaskMeta *tasks = (TaskMeta *)malloc(sizeof(TaskMeta) * num_workers);
    int w_idx = 0;

    for (int gr = 0; gr < grid_rows; gr++) {
      int y0 = (gr * new_h) / grid_rows;
      int y1 = ((gr + 1) * new_h) / grid_rows;
      for (int gc = 0; gc < grid_cols; gc++) {
        int x0 = (gc * new_w) / grid_cols;
        int x1 = ((gc + 1) * new_w) / grid_cols;
        int worker_rank = w_idx + 1;

        tasks[w_idx] = make_tile_task(op, blur_radius, input,
                                      (TileRegion){x0, y0, x1 - x0, y1 - y0});

        send_tile_task(worker_rank, &tasks[w_idx], src_img, &t_comm_acc,
                       &t_pack_acc);
        w_idx++;
      }
    }

    for (int w = 0; w < num_workers; w++) {
      int worker_rank = w + 1;
      receive_tile_result(worker_rank, dst_img, new_w, &t_comm_acc, &t_pack_acc);
    }
    free(tasks);
  }
  /* 4. DYNAMIC 1D (Master-Worker Pool with Fine-Grained Chunks) */
  else if (mode == MODE_DYNAMIC_1D) {
    int num_chunks = num_workers * 6;
    if (num_chunks > new_h)
      num_chunks = new_h;
    if (num_chunks < num_workers)
      num_chunks = num_workers;

    TaskMeta *chunks = (TaskMeta *)malloc(sizeof(TaskMeta) * num_chunks);
    for (int i = 0; i < num_chunks; i++) {
      int y0 = (i * new_h) / num_chunks;
      int y1 = ((i + 1) * new_h) / num_chunks;
      chunks[i] = make_tile_task(op, blur_radius, input,
                                 (TileRegion){0, y0, new_w, y1 - y0});
    }

    int next_chunk = 0;
    int active_workers = 0;

    for (int w = 1; w <= num_workers && next_chunk < num_chunks; w++) {
      TaskMeta *t = &chunks[next_chunk++];
      send_tile_task(w, t, src_img, &t_comm_acc, &t_pack_acc);
      active_workers++;
    }

    while (active_workers > 0) {
      int worker_rank = receive_tile_result(MPI_ANY_SOURCE, dst_img, new_w,
                                            &t_comm_acc, &t_pack_acc);

      if (next_chunk < num_chunks) {
        TaskMeta *t = &chunks[next_chunk++];
        send_tile_task(worker_rank, t, src_img, &t_comm_acc, &t_pack_acc);
      } else {
        active_workers--;
      }
    }
    free(chunks);
  }

  double t_total = MPI_Wtime() - t_start;
  timing->total += t_total;
  timing->transfer += t_comm_acc;
  timing->pack_unpack += t_pack_acc;
  timing->computation += t_comp_acc;

  free(src_img);
  *img_ptr = dst_img;
  *w_ptr = new_w;
  *h_ptr = new_h;
}

/* =========================================================================
 * Worker Event Loop (Ranks 1 .. N-1)
 * ========================================================================= */
double worker_loop(void) {
  double computation_time = 0.0;
  while (1) {
    MPI_Status status;
    TaskMeta meta;
    MPI_Recv(&meta, sizeof(TaskMeta), MPI_BYTE, 0, MPI_ANY_TAG, MPI_COMM_WORLD,
             &status);

    if (status.MPI_TAG == TAG_TERMINATE) {
      break;
    }

    int in_bytes = tile_byte_count(meta.in_w, meta.in_h);
    int out_bytes = tile_byte_count(meta.out_w, meta.out_h);

    unsigned char *in_buf = allocate_tile(in_bytes);
    unsigned char *out_buf = allocate_tile(out_bytes);

    MPI_Recv(in_buf, in_bytes, MPI_UNSIGNED_CHAR, 0, TAG_TASK_DATA,
             MPI_COMM_WORLD, MPI_STATUS_IGNORE);

    double compute_start = MPI_Wtime();
    process_submatrix(&meta, in_buf, out_buf);
    computation_time += MPI_Wtime() - compute_start;

    MPI_Send(&meta, sizeof(TaskMeta), MPI_BYTE, 0, TAG_RESULT_META,
             MPI_COMM_WORLD);
    MPI_Send(out_buf, out_bytes, MPI_UNSIGNED_CHAR, 0, TAG_RESULT_DATA,
             MPI_COMM_WORLD);

    free(in_buf);
    free(out_buf);
  }
  return computation_time;
}

/* =========================================================================
 * CLI Parsing Helpers
 * ========================================================================= */
OpType parse_op(const char *str) {
  if (strcmp(str, "grayscale") == 0)
    return OP_GRAYSCALE;
  if (strcmp(str, "invert") == 0)
    return OP_INVERT;
  if (strcmp(str, "sepia") == 0)
    return OP_SEPIA;
  if (strcmp(str, "blur") == 0)
    return OP_BLUR;
  if (strcmp(str, "flip") == 0)
    return OP_FLIP_H;
  if (strcmp(str, "rotate90") == 0)
    return OP_ROTATE90;
  return OP_NONE;
}

static int parse_pipeline_step(const char *token, OpType *op, int *blur_radius) {
  *op = parse_op(token);
  *blur_radius = DEFAULT_BLUR_KERNEL_SIZE / 2;
  if (strncmp(token, "blur:", 5) != 0)
    return 1;

  const char *size = token + 5;
  char *end;
  errno = 0;
  long parsed = strtol(size, &end, 10);
  if (errno == ERANGE || end == size || *end != '\0' || parsed < 1 ||
      parsed > INT_MAX || parsed % 2 == 0)
    return 0;

  *op = OP_BLUR;
  *blur_radius = (int)parsed / 2;
  return 1;
}

ModeType parse_mode(const char *str) {
  if (strcmp(str, "seq") == 0)
    return MODE_SEQ;
  if (strcmp(str, "static_1d") == 0)
    return MODE_STATIC_1D;
  if (strcmp(str, "static_2d") == 0)
    return MODE_STATIC_2D;
  if (strcmp(str, "dynamic_1d") == 0)
    return MODE_DYNAMIC_1D;
  return MODE_STATIC_1D;
}

int main(int argc, char *argv[]) {
  int rank, size;
  ExecutionTiming timing = {0};
  int init_w = 0, init_h = 0;
  MPI_Init(&argc, &argv);
  MPI_Comm_rank(MPI_COMM_WORLD, &rank);
  MPI_Comm_size(MPI_COMM_WORLD, &size);

  if (argc != 5) {
    if (rank == 0) {
      fprintf(stderr,
              "Usage: %s <input.ppm> <output.ppm> <mode: "
              "seq|static_1d|static_2d|dynamic_1d> <pipeline: "
              "grayscale,blur,blur:13,flip,...>\n"
              "Blur sizes must be positive odd integers; plain blur uses 9.\n",
              argv[0]);
    }
    MPI_Finalize();
    return 1;
  }

  if (rank == 0) {
    const char *in_file = argv[1];
    const char *out_file = argv[2];
    const char *mode_str = argv[3];
    const char *pipe_str = argv[4];

    ModeType mode = parse_mode(mode_str);
    char *pipe_copy = strdup(pipe_str);
    if (!pipe_copy) {
      fprintf(stderr, "Error: Cannot allocate pipeline.\n");
      MPI_Abort(MPI_COMM_WORLD, 1);
    }
    char *token = strtok(pipe_copy, ",");
    while (token != NULL) {
      OpType op;
      int blur_radius;
      if (!parse_pipeline_step(token, &op, &blur_radius)) {
        fprintf(stderr, "Error: Blur kernel size must be a positive odd integer "
                        "no greater than %d, in '%s'.\n", INT_MAX, token);
        free(pipe_copy);
        MPI_Abort(MPI_COMM_WORLD, 1);
      }
      token = strtok(NULL, ",");
    }
    strcpy(pipe_copy, pipe_str);
    int width = 0, height = 0;
    unsigned char *img = read_ppm(in_file, &width, &height);
    if (!img) {
      MPI_Abort(MPI_COMM_WORLD, 1);
    }

    init_w = width;
    init_h = height;

    token = strtok(pipe_copy, ",");
    while (token != NULL) {
      OpType op;
      int blur_radius;
      parse_pipeline_step(token, &op, &blur_radius);
      if (op == OP_NONE) {
        fprintf(stderr, "Warning: Unknown operation '%s' skipped.\n", token);
      } else {
        execute_operation_coordinator(op, mode, blur_radius, size, &img, &width,
                                      &height, &timing);
      }
      token = strtok(NULL, ",");
    }
    free(pipe_copy);

    for (int w = 1; w < size; w++) {
      TaskMeta dummy = {0};
      MPI_Send(&dummy, sizeof(TaskMeta), MPI_BYTE, w, TAG_TERMINATE,
               MPI_COMM_WORLD);
    }

    if (strcmp(out_file, "NONE") != 0) {
      write_ppm(out_file, img, width, height);
    }
    free(img);
  } else {
    timing.computation = worker_loop();
  }

  double max_computation_time = 0.0;
  MPI_Reduce(&timing.computation, &max_computation_time, 1, MPI_DOUBLE, MPI_MAX,
             0, MPI_COMM_WORLD);
  if (rank == 0) {
    /* Fields: BENCHMARK,op,mode,w,h,np,total,comm,pack_unpack,comp */
    printf("BENCHMARK,%s,%s,%d,%d,%d,%.6f,%.6f,%.6f,%.6f\n", argv[4], argv[3],
           init_w, init_h, size, timing.total, timing.transfer,
           timing.pack_unpack, max_computation_time);
    fflush(stdout);
  }

  MPI_Finalize();
  return 0;
}