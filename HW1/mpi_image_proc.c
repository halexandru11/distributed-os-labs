#include <mpi.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>

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
    OP_BLUR = 4,      /* Cat 2: Neighborhood (5x5 Box Blur) */
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
    int orig_w;
    int orig_h;
    /* Output region (in destination image coordinates) this worker is responsible for */
    int out_x;
    int out_y;
    int out_w;
    int out_h;
    /* Input region (in source image coordinates, including halo/ghost cells) sent to worker */
    int in_x;
    int in_y;
    int in_w;
    int in_h;
} TaskMeta;

#define BLUR_RADIUS 4 /* 9x9 kernel */

/* =========================================================================
 * PPM (P6) Image I/O (Direct Memory Matrix Representation)
 * ========================================================================= */
unsigned char* read_ppm(const char *filename, int *width, int *height) {
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
            while (c != '\n' && c != EOF) c = getc(fp);
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
    unsigned char *data = (unsigned char*)malloc(num_bytes);
    if (!data) {
        fprintf(stderr, "Error: Memory allocation failed for %zu bytes.\n", num_bytes);
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

int write_ppm(const char *filename, const unsigned char *data, int width, int height) {
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
void process_submatrix(const TaskMeta *meta, const unsigned char *in_buf, unsigned char *out_buf) {
    int out_w = meta->out_w;
    int out_h = meta->out_h;
    int in_w  = meta->in_w;
    int in_h  = meta->in_h;

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
            }
            else if (meta->op == OP_INVERT) {
                size_t in_idx = ((size_t)r * in_w + c) * 3;
                out_buf[out_idx]     = 255 - in_buf[in_idx];
                out_buf[out_idx + 1] = 255 - in_buf[in_idx + 1];
                out_buf[out_idx + 2] = 255 - in_buf[in_idx + 2];
            }
            else if (meta->op == OP_SEPIA) {
                size_t in_idx = ((size_t)r * in_w + c) * 3;
                unsigned char R = in_buf[in_idx];
                unsigned char G = in_buf[in_idx + 1];
                unsigned char B = in_buf[in_idx + 2];
                int tr = (int)(0.393 * R + 0.769 * G + 0.189 * B);
                int tg = (int)(0.349 * R + 0.686 * G + 0.168 * B);
                int tb = (int)(0.272 * R + 0.534 * G + 0.131 * B);
                out_buf[out_idx]     = (tr > 255) ? 255 : tr;
                out_buf[out_idx + 1] = (tg > 255) ? 255 : tg;
                out_buf[out_idx + 2] = (tb > 255) ? 255 : tb;
            }
            else if (meta->op == OP_BLUR) {
                /* Global coordinates of this output pixel */
                int glob_r = meta->out_y + r;
                int glob_c = meta->out_x + c;
                /* Local coordinates inside in_buf (accounting for halo offset) */
                int center_r = glob_r - meta->in_y;
                int center_c = glob_c - meta->in_x;

                int sum_r = 0, sum_g = 0, sum_b = 0, count = 0;
                for (int dr = -BLUR_RADIUS; dr <= BLUR_RADIUS; dr++) {
                    for (int dc = -BLUR_RADIUS; dc <= BLUR_RADIUS; dc++) {
                        int nr = center_r + dr;
                        int nc = center_c + dc;
                        if (nr >= 0 && nr < in_h && nc >= 0 && nc < in_w) {
                            size_t idx = ((size_t)nr * in_w + nc) * 3;
                            sum_r += in_buf[idx];
                            sum_g += in_buf[idx + 1];
                            sum_b += in_buf[idx + 2];
                            count++;
                        }
                    }
                }
                out_buf[out_idx]     = (unsigned char)(sum_r / count);
                out_buf[out_idx + 1] = (unsigned char)(sum_g / count);
                out_buf[out_idx + 2] = (unsigned char)(sum_b / count);
            }
            else if (meta->op == OP_FLIP_H) {
                /* In horizontal flip, output pixel (r, c) in submatrix comes from (r, in_w - 1 - c) */
                int src_c = in_w - 1 - c;
                size_t in_idx = ((size_t)r * in_w + src_c) * 3;
                out_buf[out_idx]     = in_buf[in_idx];
                out_buf[out_idx + 1] = in_buf[in_idx + 1];
                out_buf[out_idx + 2] = in_buf[in_idx + 2];
            }
            else if (meta->op == OP_ROTATE90) {
                /* 90 deg clockwise: dest(r_glob, c_glob) = src(H - 1 - c_glob, r_glob)
                 * Inside our cropped input block:
                 * glob_r = out_y + r, glob_c = out_x + c
                 * src_glob_r = orig_h - 1 - glob_c
                 * src_glob_c = glob_r
                 */
                int glob_r = meta->out_y + r;
                int glob_c = meta->out_x + c;
                int src_glob_r = meta->orig_h - 1 - glob_c;
                int src_glob_c = glob_r;

                int local_r = src_glob_r - meta->in_y;
                int local_c = src_glob_c - meta->in_x;
                size_t in_idx = ((size_t)local_r * in_w + local_c) * 3;
                out_buf[out_idx]     = in_buf[in_idx];
                out_buf[out_idx + 1] = in_buf[in_idx + 1];
                out_buf[out_idx + 2] = in_buf[in_idx + 2];
            }
        }
    }
}

/* =========================================================================
 * Helper: Compute Input Bounding Box (with Halo if needed) for an Output Tile
 * ========================================================================= */
void compute_input_region(TaskMeta *t) {
    if (t->op == OP_GRAYSCALE || t->op == OP_INVERT || t->op == OP_SEPIA) {
        t->in_x = t->out_x;
        t->in_y = t->out_y;
        t->in_w = t->out_w;
        t->in_h = t->out_h;
    }
    else if (t->op == OP_BLUR) {
        int x0 = t->out_x - BLUR_RADIUS;
        int y0 = t->out_y - BLUR_RADIUS;
        int x1 = t->out_x + t->out_w + BLUR_RADIUS;
        int y1 = t->out_y + t->out_h + BLUR_RADIUS;
        if (x0 < 0) x0 = 0;
        if (y0 < 0) y0 = 0;
        if (x1 > t->orig_w) x1 = t->orig_w;
        if (y1 > t->orig_h) y1 = t->orig_h;
        t->in_x = x0;
        t->in_y = y0;
        t->in_w = x1 - x0;
        t->in_h = y1 - y0;
    }
    else if (t->op == OP_FLIP_H) {
        t->in_x = t->orig_w - (t->out_x + t->out_w);
        t->in_y = t->out_y;
        t->in_w = t->out_w;
        t->in_h = t->out_h;
    }
    else if (t->op == OP_ROTATE90) {
        /* Output region [out_y .. out_y+out_h-1] x [out_x .. out_x+out_w-1]
         * maps from source rows [orig_h - (out_x + out_w) .. orig_h - 1 - out_x]
         * and source cols [out_y .. out_y + out_h - 1]
         */
        t->in_x = t->out_y;
        t->in_y = t->orig_h - (t->out_x + t->out_w);
        t->in_w = t->out_h;
        t->in_h = t->out_w;
    }
}

/* Pack a 2D submatrix from full image into a contiguous buffer */
void pack_submatrix(const unsigned char *full_img, int full_w,
                    int sub_x, int sub_y, int sub_w, int sub_h,
                    unsigned char *packed_buf) {
    for (int r = 0; r < sub_h; r++) {
        const unsigned char *src_row = full_img + ((size_t)(sub_y + r) * full_w + sub_x) * 3;
        unsigned char *dst_row = packed_buf + ((size_t)r * sub_w) * 3;
        memcpy(dst_row, src_row, (size_t)sub_w * 3);
    }
}

/* Unpack a contiguous buffer back into a 2D submatrix of the full output image */
void unpack_submatrix(const unsigned char *packed_buf,
                      unsigned char *full_img, int full_w,
                      int sub_x, int sub_y, int sub_w, int sub_h) {
    for (int r = 0; r < sub_h; r++) {
        const unsigned char *src_row = packed_buf + ((size_t)r * sub_w) * 3;
        unsigned char *dst_row = full_img + ((size_t)(sub_y + r) * full_w + sub_x) * 3;
        memcpy(dst_row, src_row, (size_t)sub_w * 3);
    }
}

/* =========================================================================
 * Coordinator Execution for One Operation in the Pipeline
 * ========================================================================= */
void execute_operation_coordinator(OpType op, ModeType mode, int num_procs,
                                   unsigned char **img_ptr, int *w_ptr, int *h_ptr,
                                   double *total_time, double *comm_time, double *comp_time) {
    int orig_w = *w_ptr;
    int orig_h = *h_ptr;
    int new_w  = (op == OP_ROTATE90) ? orig_h : orig_w;
    int new_h  = (op == OP_ROTATE90) ? orig_w : orig_h;

    unsigned char *src_img = *img_ptr;
    unsigned char *dst_img = (unsigned char*)malloc((size_t)new_w * new_h * 3);

    double t_start = MPI_Wtime();
    double t_comm_acc = 0.0;
    double t_comp_acc = 0.0;

    int num_workers = num_procs - 1;

    /* 1. SEQUENTIAL MODE (or if launched with -np 1) */
    if (mode == MODE_SEQ || num_workers < 1) {
        TaskMeta meta = { op, orig_w, orig_h, 0, 0, new_w, new_h, 0, 0, orig_w, orig_h };
        double c0 = MPI_Wtime();
        process_submatrix(&meta, src_img, dst_img);
        t_comp_acc += (MPI_Wtime() - c0);
    }
    /* 2. STATIC 1D (Horizontal Strips) */
    else if (mode == MODE_STATIC_1D) {
        int rows_per_worker = new_h / num_workers;
        int rem = new_h % num_workers;
        int cur_y = 0;

        TaskMeta *tasks = (TaskMeta*)malloc(sizeof(TaskMeta) * num_workers);

        /* Send tasks to all workers */
        for (int w = 0; w < num_workers; w++) {
            int worker_rank = w + 1;
            int h_slice = rows_per_worker + (w < rem ? 1 : 0);

            tasks[w].op = op;
            tasks[w].orig_w = orig_w;
            tasks[w].orig_h = orig_h;
            tasks[w].out_x = 0;
            tasks[w].out_y = cur_y;
            tasks[w].out_w = new_w;
            tasks[w].out_h = h_slice;
            compute_input_region(&tasks[w]);
            cur_y += h_slice;

            double cm0 = MPI_Wtime();
            MPI_Send(&tasks[w], sizeof(TaskMeta), MPI_BYTE, worker_rank, TAG_TASK_META, MPI_COMM_WORLD);

            if (tasks[w].in_w == orig_w && tasks[w].in_x == 0) {
                /* Contiguous 1D horizontal slice: zero-copy MPI_Send directly from src_img! */
                const unsigned char *slice_ptr = src_img + ((size_t)tasks[w].in_y * orig_w) * 3;
                MPI_Send(slice_ptr, tasks[w].in_w * tasks[w].in_h * 3, MPI_UNSIGNED_CHAR,
                         worker_rank, TAG_TASK_DATA, MPI_COMM_WORLD);
            } else {
                /* Non-contiguous input (e.g., Rotate90): pack into temporary buffer */
                size_t in_bytes = (size_t)tasks[w].in_w * tasks[w].in_h * 3;
                unsigned char *tmp = (unsigned char*)malloc(in_bytes);
                pack_submatrix(src_img, orig_w, tasks[w].in_x, tasks[w].in_y, tasks[w].in_w, tasks[w].in_h, tmp);
                MPI_Send(tmp, in_bytes, MPI_UNSIGNED_CHAR, worker_rank, TAG_TASK_DATA, MPI_COMM_WORLD);
                free(tmp);
            }
            t_comm_acc += (MPI_Wtime() - cm0);
        }

        /* Receive results from all workers */
        for (int w = 0; w < num_workers; w++) {
            int worker_rank = w + 1;
            TaskMeta res_meta;
            double cm0 = MPI_Wtime();
            MPI_Recv(&res_meta, sizeof(TaskMeta), MPI_BYTE, worker_rank, TAG_RESULT_META, MPI_COMM_WORLD, MPI_STATUS_IGNORE);
            unsigned char *dst_slice = dst_img + ((size_t)res_meta.out_y * new_w) * 3;
            MPI_Recv(dst_slice, res_meta.out_w * res_meta.out_h * 3, MPI_UNSIGNED_CHAR,
                     worker_rank, TAG_RESULT_DATA, MPI_COMM_WORLD, MPI_STATUS_IGNORE);
            t_comm_acc += (MPI_Wtime() - cm0);
        }
        free(tasks);
    }
    /* 3. STATIC 2D (Grid Tiles) */
    else if (mode == MODE_STATIC_2D) {
        /* Factor num_workers into grid_rows x grid_cols */
        int grid_cols = 1, grid_rows = num_workers;
        for (int i = 1; i * i <= num_workers; i++) {
            if (num_workers % i == 0) {
                grid_cols = i;
                grid_rows = num_workers / i;
            }
        }

        TaskMeta *tasks = (TaskMeta*)malloc(sizeof(TaskMeta) * num_workers);
        int w_idx = 0;

        for (int gr = 0; gr < grid_rows; gr++) {
            int y0 = (gr * new_h) / grid_rows;
            int y1 = ((gr + 1) * new_h) / grid_rows;
            for (int gc = 0; gc < grid_cols; gc++) {
                int x0 = (gc * new_w) / grid_cols;
                int x1 = ((gc + 1) * new_w) / grid_cols;
                int worker_rank = w_idx + 1;

                tasks[w_idx].op = op;
                tasks[w_idx].orig_w = orig_w;
                tasks[w_idx].orig_h = orig_h;
                tasks[w_idx].out_x = x0;
                tasks[w_idx].out_y = y0;
                tasks[w_idx].out_w = x1 - x0;
                tasks[w_idx].out_h = y1 - y0;
                compute_input_region(&tasks[w_idx]);

                double cm0 = MPI_Wtime();
                MPI_Send(&tasks[w_idx], sizeof(TaskMeta), MPI_BYTE, worker_rank, TAG_TASK_META, MPI_COMM_WORLD);

                size_t in_bytes = (size_t)tasks[w_idx].in_w * tasks[w_idx].in_h * 3;
                unsigned char *tmp = (unsigned char*)malloc(in_bytes);
                pack_submatrix(src_img, orig_w, tasks[w_idx].in_x, tasks[w_idx].in_y,
                               tasks[w_idx].in_w, tasks[w_idx].in_h, tmp);
                MPI_Send(tmp, in_bytes, MPI_UNSIGNED_CHAR, worker_rank, TAG_TASK_DATA, MPI_COMM_WORLD);
                free(tmp);
                t_comm_acc += (MPI_Wtime() - cm0);

                w_idx++;
            }
        }

        /* Collect 2D tiles */
        for (int w = 0; w < num_workers; w++) {
            int worker_rank = w + 1;
            TaskMeta res_meta;
            double cm0 = MPI_Wtime();
            MPI_Recv(&res_meta, sizeof(TaskMeta), MPI_BYTE, worker_rank, TAG_RESULT_META, MPI_COMM_WORLD, MPI_STATUS_IGNORE);

            size_t out_bytes = (size_t)res_meta.out_w * res_meta.out_h * 3;
            unsigned char *tmp = (unsigned char*)malloc(out_bytes);
            MPI_Recv(tmp, out_bytes, MPI_UNSIGNED_CHAR, worker_rank, TAG_RESULT_DATA, MPI_COMM_WORLD, MPI_STATUS_IGNORE);
            unpack_submatrix(tmp, dst_img, new_w, res_meta.out_x, res_meta.out_y, res_meta.out_w, res_meta.out_h);
            free(tmp);
            t_comm_acc += (MPI_Wtime() - cm0);
        }
        free(tasks);
    }
    /* 4. DYNAMIC 1D (Master-Worker Pool with Fine-Grained Chunks) */
    else if (mode == MODE_DYNAMIC_1D) {
        int num_chunks = num_workers * 6; /* 6 chunks per worker for smooth load balancing */
        if (num_chunks > new_h) num_chunks = new_h;
        if (num_chunks < num_workers) num_chunks = num_workers;

        TaskMeta *chunks = (TaskMeta*)malloc(sizeof(TaskMeta) * num_chunks);
        for (int i = 0; i < num_chunks; i++) {
            int y0 = (i * new_h) / num_chunks;
            int y1 = ((i + 1) * new_h) / num_chunks;
            chunks[i].op = op;
            chunks[i].orig_w = orig_w;
            chunks[i].orig_h = orig_h;
            chunks[i].out_x = 0;
            chunks[i].out_y = y0;
            chunks[i].out_w = new_w;
            chunks[i].out_h = y1 - y0;
            compute_input_region(&chunks[i]);
        }

        int next_chunk = 0;
        int active_workers = 0;

        /* Seed initial tasks to workers */
        for (int w = 1; w <= num_workers && next_chunk < num_chunks; w++) {
            TaskMeta *t = &chunks[next_chunk++];
            double cm0 = MPI_Wtime();
            MPI_Send(t, sizeof(TaskMeta), MPI_BYTE, w, TAG_TASK_META, MPI_COMM_WORLD);
            if (t->in_w == orig_w && t->in_x == 0) {
                const unsigned char *slice_ptr = src_img + ((size_t)t->in_y * orig_w) * 3;
                MPI_Send(slice_ptr, t->in_w * t->in_h * 3, MPI_UNSIGNED_CHAR, w, TAG_TASK_DATA, MPI_COMM_WORLD);
            } else {
                size_t in_bytes = (size_t)t->in_w * t->in_h * 3;
                unsigned char *tmp = (unsigned char*)malloc(in_bytes);
                pack_submatrix(src_img, orig_w, t->in_x, t->in_y, t->in_w, t->in_h, tmp);
                MPI_Send(tmp, in_bytes, MPI_UNSIGNED_CHAR, w, TAG_TASK_DATA, MPI_COMM_WORLD);
                free(tmp);
            }
            t_comm_acc += (MPI_Wtime() - cm0);
            active_workers++;
        }

        /* Dynamic dispatch loop: receive finished chunk -> immediately send next chunk */
        while (active_workers > 0) {
            MPI_Status status;
            TaskMeta res_meta;
            double cm0 = MPI_Wtime();
            MPI_Recv(&res_meta, sizeof(TaskMeta), MPI_BYTE, MPI_ANY_SOURCE, TAG_RESULT_META, MPI_COMM_WORLD, &status);
            int worker_rank = status.MPI_SOURCE;

            unsigned char *dst_slice = dst_img + ((size_t)res_meta.out_y * new_w) * 3;
            MPI_Recv(dst_slice, res_meta.out_w * res_meta.out_h * 3, MPI_UNSIGNED_CHAR,
                     worker_rank, TAG_RESULT_DATA, MPI_COMM_WORLD, MPI_STATUS_IGNORE);
            t_comm_acc += (MPI_Wtime() - cm0);

            if (next_chunk < num_chunks) {
                TaskMeta *t = &chunks[next_chunk++];
                double cm1 = MPI_Wtime();
                MPI_Send(t, sizeof(TaskMeta), MPI_BYTE, worker_rank, TAG_TASK_META, MPI_COMM_WORLD);
                if (t->in_w == orig_w && t->in_x == 0) {
                    const unsigned char *slice_ptr = src_img + ((size_t)t->in_y * orig_w) * 3;
                    MPI_Send(slice_ptr, t->in_w * t->in_h * 3, MPI_UNSIGNED_CHAR, worker_rank, TAG_TASK_DATA, MPI_COMM_WORLD);
                } else {
                    size_t in_bytes = (size_t)t->in_w * t->in_h * 3;
                    unsigned char *tmp = (unsigned char*)malloc(in_bytes);
                    pack_submatrix(src_img, orig_w, t->in_x, t->in_y, t->in_w, t->in_h, tmp);
                    MPI_Send(tmp, in_bytes, MPI_UNSIGNED_CHAR, worker_rank, TAG_TASK_DATA, MPI_COMM_WORLD);
                    free(tmp);
                }
                t_comm_acc += (MPI_Wtime() - cm1);
            } else {
                active_workers--;
            }
        }
        free(chunks);
    }

    double t_total = MPI_Wtime() - t_start;
    if (mode != MODE_SEQ && num_workers >= 1) {
        t_comp_acc = t_total - t_comm_acc;
        if (t_comp_acc < 0.0) t_comp_acc = 0.0;
    }

    *total_time += t_total;
    *comm_time  += t_comm_acc;
    *comp_time  += t_comp_acc;

    free(src_img);
    *img_ptr = dst_img;
    *w_ptr = new_w;
    *h_ptr = new_h;
}

/* =========================================================================
 * Worker Event Loop (Ranks 1 .. N-1)
 * ========================================================================= */
void worker_loop(void) {
    while (1) {
        MPI_Status status;
        TaskMeta meta;
        MPI_Recv(&meta, sizeof(TaskMeta), MPI_BYTE, 0, MPI_ANY_TAG, MPI_COMM_WORLD, &status);

        if (status.MPI_TAG == TAG_TERMINATE) {
            break;
        }

        size_t in_bytes  = (size_t)meta.in_w * meta.in_h * 3;
        size_t out_bytes = (size_t)meta.out_w * meta.out_h * 3;

        unsigned char *in_buf  = (unsigned char*)malloc(in_bytes);
        unsigned char *out_buf = (unsigned char*)malloc(out_bytes);

        MPI_Recv(in_buf, in_bytes, MPI_UNSIGNED_CHAR, 0, TAG_TASK_DATA, MPI_COMM_WORLD, MPI_STATUS_IGNORE);

        /* Perform matrix computation */
        process_submatrix(&meta, in_buf, out_buf);

        /* Send processed submatrix back to Coordinator */
        MPI_Send(&meta, sizeof(TaskMeta), MPI_BYTE, 0, TAG_RESULT_META, MPI_COMM_WORLD);
        MPI_Send(out_buf, out_bytes, MPI_UNSIGNED_CHAR, 0, TAG_RESULT_DATA, MPI_COMM_WORLD);

        free(in_buf);
        free(out_buf);
    }
}

/* =========================================================================
 * CLI Parsing Helpers
 * ========================================================================= */
OpType parse_op(const char *str) {
    if (strcmp(str, "grayscale") == 0) return OP_GRAYSCALE;
    if (strcmp(str, "invert") == 0)    return OP_INVERT;
    if (strcmp(str, "sepia") == 0)     return OP_SEPIA;
    if (strcmp(str, "blur") == 0)      return OP_BLUR;
    if (strcmp(str, "flip") == 0)      return OP_FLIP_H;
    if (strcmp(str, "rotate90") == 0)  return OP_ROTATE90;
    return OP_NONE;
}

ModeType parse_mode(const char *str) {
    if (strcmp(str, "seq") == 0)        return MODE_SEQ;
    if (strcmp(str, "static_1d") == 0)  return MODE_STATIC_1D;
    if (strcmp(str, "static_2d") == 0)  return MODE_STATIC_2D;
    if (strcmp(str, "dynamic_1d") == 0) return MODE_DYNAMIC_1D;
    return MODE_STATIC_1D;
}

int main(int argc, char *argv[]) {
    int rank, size;
    MPI_Init(&argc, &argv);
    MPI_Comm_rank(MPI_COMM_WORLD, &rank);
    MPI_Comm_size(MPI_COMM_WORLD, &size);

    if (argc < 5) {
        if (rank == 0) {
            fprintf(stderr, "Usage: %s <input.ppm> <output.ppm> <mode: seq|static_1d|static_2d|dynamic_1d> <pipeline: grayscale,blur,flip,...>\n", argv[0]);
        }
        MPI_Finalize();
        return 1;
    }

    if (rank == 0) {
        const char *in_file   = argv[1];
        const char *out_file  = argv[2];
        const char *mode_str  = argv[3];
        const char *pipe_str  = argv[4];

        ModeType mode = parse_mode(mode_str);
        int width = 0, height = 0;
        unsigned char *img = read_ppm(in_file, &width, &height);
        if (!img) {
            MPI_Abort(MPI_COMM_WORLD, 1);
        }

        int init_w = width, init_h = height;
        double total_time = 0.0, comm_time = 0.0, comp_time = 0.0;

        /* Parse comma-separated pipeline of operations */
        char *pipe_copy = strdup(pipe_str);
        char *token = strtok(pipe_copy, ",");
        while (token != NULL) {
            OpType op = parse_op(token);
            if (op == OP_NONE) {
                fprintf(stderr, "Warning: Unknown operation '%s' skipped.\n", token);
            } else {
                execute_operation_coordinator(op, mode, size, &img, &width, &height,
                                              &total_time, &comm_time, &comp_time);
            }
            token = strtok(NULL, ",");
        }
        free(pipe_copy);

        /* Terminate all workers */
        for (int w = 1; w < size; w++) {
            TaskMeta dummy = {0};
            MPI_Send(&dummy, sizeof(TaskMeta), MPI_BYTE, w, TAG_TERMINATE, MPI_COMM_WORLD);
        }

        /* Write output image (skip disk write if output is "NONE" during pure benchmarking) */
        if (strcmp(out_file, "NONE") != 0) {
            write_ppm(out_file, img, width, height);
        }
        free(img);

        /* Structured CSV line for Python benchmark script */
        printf("BENCHMARK,%s,%s,%d,%d,%d,%.6f,%.6f,%.6f\n",
               pipe_str, mode_str, init_w, init_h, size, total_time, comm_time, comp_time);
        fflush(stdout);
    } else {
        worker_loop();
    }

    MPI_Finalize();
    return 0;
}