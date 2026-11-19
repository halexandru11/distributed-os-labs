#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <inttypes.h>
#include <limits.h>
#include <omp.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/resource.h>

/* Fixed-width unsigned arithmetic: multiplication and addition modulo 2^64.
 * In particular, the UINT64_MAX experiment has defined behavior in C.
 * Random inputs in [0,100] and the ones/zeros cases do not overflow. */
typedef uint64_t scalar;
typedef struct {
  int n, m, r;
  scalar *a, *b, *c;
  bool transposed;
  int threads[3];
  omp_sched_t schedules[3];
  int chunks[3];
} Problem;

static void fail(const char *message) {
  fprintf(stderr, "Error: %s\n", message);
  exit(EXIT_FAILURE);
}

static inline scalar b_at(const Problem *p, int k, int j) {
  return p->transposed ? p->b[(size_t)j * p->m + k]
                       : p->b[(size_t)k * p->r + j];
}

static inline scalar dot(const Problem *p, int i, int j) {
  const scalar *a = p->a + (size_t)i * p->m;
  scalar sum = 0;
  if (p->transposed) {
    const scalar *b = p->b + (size_t)j * p->m;
    for (int k = 0; k < p->m; ++k)
      sum += a[k] * b[k];
  } else {
    for (int k = 0; k < p->m; ++k)
      sum += a[k] * p->b[(size_t)k * p->r + j];
  }
  return sum;
}

/* run-sched-var is a task ICV: set it in the encountering task BEFORE the
 * parallel region, so the implicit tasks inherit the requested schedule. */
static void schedule_at(const Problem *p, int loop) {
  omp_set_schedule(p->schedules[loop], p->chunks[loop]);
}

static void sequential(const Problem *p) {
  for (int i = 0; i < p->n; ++i)
    for (int j = 0; j < p->r; ++j)
      p->c[(size_t)i * p->r + j] = dot(p, i, j);
}

static void parallel_i(const Problem *p) {
  schedule_at(p, 0);
#pragma omp parallel for num_threads(p->threads[0])                            \
    schedule(runtime) default(none) shared(p)
  for (int i = 0; i < p->n; ++i)
    for (int j = 0; j < p->r; ++j)
      p->c[(size_t)i * p->r + j] = dot(p, i, j);
}

static void parallel_j(const Problem *p) {
  schedule_at(p, 1);
  for (int i = 0; i < p->n; ++i) {
#pragma omp parallel for num_threads(p->threads[1])                            \
    schedule(runtime) default(none) shared(p, i)
    for (int j = 0; j < p->r; ++j)
      p->c[(size_t)i * p->r + j] = dot(p, i, j);
  }
}

static void parallel_dot_atomic(const Problem *p, int i, int j) {
  scalar *cell = p->c + (size_t)i * p->r + j;
#pragma omp parallel for num_threads(p->threads[2])                            \
    schedule(runtime) default(none) shared(p, i, j, cell)
  for (int k = 0; k < p->m; ++k) {
    scalar term = p->a[(size_t)i * p->m + k] * b_at(p, k, j);
#pragma omp atomic update
    *cell += term;
  }
}

/* Each thread accumulates into a private row or matrix on the heap. */
static scalar *allocate_partial_sum(size_t count) {
  scalar *partial = calloc(count, sizeof(*partial));
  if (!partial)
    fail("reduction buffer allocation failed");
  return partial;
}

/* The accumulation loop's barrier makes every partial sum visible here. */
static void reduce_partial_sums(scalar *output, size_t count,
                                scalar *const partials[]) {
  int team_size = omp_get_num_threads();
#pragma omp for schedule(static)
  for (size_t cell = 0; cell < count; ++cell) {
    scalar sum = 0;
    for (int thread = 0; thread < team_size; ++thread)
      sum += partials[thread][cell];
    output[cell] = sum;
  }
}

static void reduce_collapsed_row(const Problem *p, int i) {
  scalar *partials[p->threads[1]];
  scalar *row = p->c + (size_t)i * p->r;
#pragma omp parallel num_threads(p->threads[1]) default(none)                  \
    shared(p, i, partials, row)
  {
    scalar *partial = allocate_partial_sum(p->r);
    partials[omp_get_thread_num()] = partial;
#pragma omp for collapse(2) schedule(runtime)
    for (int64_t j = 0; j < p->r; ++j)
      for (int64_t k = 0; k < p->m; ++k)
        partial[j] += p->a[(size_t)i * p->m + k] * b_at(p, k, j);
    reduce_partial_sums(row, p->r, partials);
    free(partial);
  }
}

static void parallel_k_reduction(const Problem *p) {
  schedule_at(p, 2);
  for (int i = 0; i < p->n; ++i)
    for (int j = 0; j < p->r; ++j) {
      scalar sum = 0;
#pragma omp parallel for num_threads(p->threads[2]) schedule(runtime)          \
    reduction(+ : sum) default(none) shared(p, i, j)
      for (int k = 0; k < p->m; ++k)
        sum += p->a[(size_t)i * p->m + k] * b_at(p, k, j);
      p->c[(size_t)i * p->r + j] = sum;
    }
}

static void parallel_k_atomic(const Problem *p) {
  schedule_at(p, 2);
  for (int i = 0; i < p->n; ++i)
    for (int j = 0; j < p->r; ++j)
      parallel_dot_atomic(p, i, j);
}

static void collapse_ij(const Problem *p) {
  schedule_at(p, 0);
#pragma omp parallel for collapse(2) num_threads(p->threads[0])                \
    schedule(runtime) default(none) shared(p)
  for (int64_t i = 0; i < p->n; ++i)
    for (int64_t j = 0; j < p->r; ++j)
      p->c[(size_t)i * p->r + j] = dot(p, i, j);
}

static void collapse_jk_atomic(const Problem *p) {
  schedule_at(p, 1);
  for (int i = 0; i < p->n; ++i) {
#pragma omp parallel for collapse(2) num_threads(p->threads[1])                \
    schedule(runtime) default(none) shared(p, i)
    for (int64_t j = 0; j < p->r; ++j)
      for (int64_t k = 0; k < p->m; ++k) {
        scalar term = p->a[(size_t)i * p->m + k] * b_at(p, k, j);
/* Several collapsed iterations contribute to the same cell. */
#pragma omp atomic update
        p->c[(size_t)i * p->r + j] += term;
      }
  }
}

static void collapse_jk_reduction(const Problem *p) {
  schedule_at(p, 1);
  for (int i = 0; i < p->n; ++i)
    reduce_collapsed_row(p, i);
}

static void collapse_ijk_atomic(const Problem *p) {
  schedule_at(p, 0);
#pragma omp parallel for collapse(3) num_threads(p->threads[0])                \
    schedule(runtime) default(none) shared(p)
  for (int64_t i = 0; i < p->n; ++i)
    for (int64_t j = 0; j < p->r; ++j)
      for (int64_t k = 0; k < p->m; ++k) {
        scalar term = p->a[(size_t)i * p->m + k] * b_at(p, k, j);
#pragma omp atomic update
        p->c[(size_t)i * p->r + j] += term;
      }
}

static void collapse_ijk_reduction(const Problem *p) {
  schedule_at(p, 0);
  size_t count = (size_t)p->n * p->r;
  scalar *partials[p->threads[0]];
#pragma omp parallel num_threads(p->threads[0]) default(none)                  \
    shared(p, count, partials)
  {
    scalar *partial = allocate_partial_sum(count);
    partials[omp_get_thread_num()] = partial;
#pragma omp for collapse(3) schedule(runtime)
    for (int64_t i = 0; i < p->n; ++i)
      for (int64_t j = 0; j < p->r; ++j)
        for (int64_t k = 0; k < p->m; ++k)
          partial[(size_t)i * p->r + j] +=
              p->a[(size_t)i * p->m + k] * b_at(p, k, j);
    reduce_partial_sums(p->c, count, partials);
    free(partial);
  }
}

static void nested_ij(const Problem *p) {
  schedule_at(p, 0);
#pragma omp parallel for num_threads(p->threads[0])                            \
    schedule(runtime) default(none) shared(p)
  for (int i = 0; i < p->n; ++i) {
    schedule_at(p, 1);
#pragma omp parallel for num_threads(p->threads[1])                            \
    schedule(runtime) default(none) shared(p, i)
    for (int j = 0; j < p->r; ++j)
      p->c[(size_t)i * p->r + j] = dot(p, i, j);
  }
}

static void nested_jk_reduction(const Problem *p) {
  schedule_at(p, 1);
  for (int i = 0; i < p->n; ++i) {
#pragma omp parallel for num_threads(p->threads[1])                            \
    schedule(runtime) default(none) shared(p, i)
    for (int j = 0; j < p->r; ++j) {
      scalar sum = 0;
      schedule_at(p, 2);
#pragma omp parallel for num_threads(p->threads[2]) schedule(runtime)          \
    reduction(+ : sum) default(none) shared(p, i, j)
      for (int k = 0; k < p->m; ++k)
        sum += p->a[(size_t)i * p->m + k] * b_at(p, k, j);
      p->c[(size_t)i * p->r + j] = sum;
    }
  }
}

static void nested_jk_atomic(const Problem *p) {
  schedule_at(p, 1);
  for (int i = 0; i < p->n; ++i) {
#pragma omp parallel for num_threads(p->threads[1])                            \
    schedule(runtime) default(none) shared(p, i)
    for (int j = 0; j < p->r; ++j) {
      schedule_at(p, 2);
      parallel_dot_atomic(p, i, j);
    }
  }
}

static void nested_ik_reduction(const Problem *p) {
  schedule_at(p, 0);
#pragma omp parallel for num_threads(p->threads[0])                            \
    schedule(runtime) default(none) shared(p)
  for (int i = 0; i < p->n; ++i) {
    schedule_at(p, 2);
    for (int j = 0; j < p->r; ++j) {
      scalar sum = 0;
#pragma omp parallel for num_threads(p->threads[2]) schedule(runtime)          \
    reduction(+ : sum) default(none) shared(p, i, j)
      for (int k = 0; k < p->m; ++k)
        sum += p->a[(size_t)i * p->m + k] * b_at(p, k, j);
      p->c[(size_t)i * p->r + j] = sum;
    }
  }
}

static void nested_ik_atomic(const Problem *p) {
  schedule_at(p, 0);
#pragma omp parallel for num_threads(p->threads[0])                            \
    schedule(runtime) default(none) shared(p)
  for (int i = 0; i < p->n; ++i) {
    schedule_at(p, 2);
    for (int j = 0; j < p->r; ++j)
      parallel_dot_atomic(p, i, j);
  }
}

static void nested_ijk_reduction(const Problem *p) {
  schedule_at(p, 0);
#pragma omp parallel for num_threads(p->threads[0])                            \
    schedule(runtime) default(none) shared(p)
  for (int i = 0; i < p->n; ++i) {
    schedule_at(p, 1);
#pragma omp parallel for num_threads(p->threads[1])                            \
    schedule(runtime) default(none) shared(p, i)
    for (int j = 0; j < p->r; ++j) {
      scalar sum = 0;
      schedule_at(p, 2);
#pragma omp parallel for num_threads(p->threads[2]) schedule(runtime)          \
    reduction(+ : sum) default(none) shared(p, i, j)
      for (int k = 0; k < p->m; ++k)
        sum += p->a[(size_t)i * p->m + k] * b_at(p, k, j);
      p->c[(size_t)i * p->r + j] = sum;
    }
  }
}

static void nested_ijk_atomic(const Problem *p) {
  schedule_at(p, 0);
#pragma omp parallel for num_threads(p->threads[0])                            \
    schedule(runtime) default(none) shared(p)
  for (int i = 0; i < p->n; ++i) {
    schedule_at(p, 1);
#pragma omp parallel for num_threads(p->threads[1])                            \
    schedule(runtime) default(none) shared(p, i)
    for (int j = 0; j < p->r; ++j) {
      schedule_at(p, 2);
      parallel_dot_atomic(p, i, j);
    }
  }
}

static void hybrid_ij_k_reduction(const Problem *p) {
  schedule_at(p, 0);
#pragma omp parallel for collapse(2) num_threads(p->threads[0])                \
    schedule(runtime) default(none) shared(p)
  for (int64_t i = 0; i < p->n; ++i)
    for (int64_t j = 0; j < p->r; ++j) {
      scalar sum = 0;
      schedule_at(p, 2);
#pragma omp parallel for num_threads(p->threads[2]) schedule(runtime)          \
    reduction(+ : sum) default(none) shared(p, i, j)
      for (int k = 0; k < p->m; ++k)
        sum += p->a[(size_t)i * p->m + k] * b_at(p, k, j);
      p->c[(size_t)i * p->r + j] = sum;
    }
}

static void hybrid_ij_k_atomic(const Problem *p) {
  schedule_at(p, 0);
#pragma omp parallel for collapse(2) num_threads(p->threads[0])                \
    schedule(runtime) default(none) shared(p)
  for (int64_t i = 0; i < p->n; ++i)
    for (int64_t j = 0; j < p->r; ++j) {
      schedule_at(p, 2);
      parallel_dot_atomic(p, i, j);
    }
}

static void hybrid_i_jk_atomic(const Problem *p) {
  schedule_at(p, 0);
#pragma omp parallel for num_threads(p->threads[0])                            \
    schedule(runtime) default(none) shared(p)
  for (int i = 0; i < p->n; ++i) {
    schedule_at(p, 1);
#pragma omp parallel for collapse(2) num_threads(p->threads[1])                \
    schedule(runtime) default(none) shared(p, i)
    for (int64_t j = 0; j < p->r; ++j)
      for (int64_t k = 0; k < p->m; ++k) {
        scalar term = p->a[(size_t)i * p->m + k] * b_at(p, k, j);
#pragma omp atomic update
        p->c[(size_t)i * p->r + j] += term;
      }
  }
}

static void hybrid_i_jk_reduction(const Problem *p) {
  schedule_at(p, 0);
#pragma omp parallel for num_threads(p->threads[0])                            \
    schedule(runtime) default(none) shared(p)
  for (int i = 0; i < p->n; ++i) {
    schedule_at(p, 1);
    reduce_collapsed_row(p, i);
  }
}

/* Loop settings for each nested team; -1 ends the list.
 * A collapsed loop uses one team. */
typedef struct {
  const char *name;
  void (*run)(const Problem *);
  int loops[3];
} Variant;

static const Variant variants[] = {
    {"seq", sequential, {-1, -1, -1}},
    {"parallel_i", parallel_i, {0, -1, -1}},
    {"parallel_j", parallel_j, {1, -1, -1}},
    {"parallel_k", parallel_k_reduction, {2, -1, -1}},
    {"collapse_ij", collapse_ij, {0, -1, -1}},
    {"collapse_jk", collapse_jk_atomic, {1, -1, -1}},
    {"collapse_ijk", collapse_ijk_atomic, {0, -1, -1}},
    {"nested_ij", nested_ij, {0, 1, -1}},
    {"nested_jk", nested_jk_reduction, {1, 2, -1}},
    {"nested_ik", nested_ik_reduction, {0, 2, -1}},
    {"nested_ijk", nested_ijk_reduction, {0, 1, 2}},
    {"hybrid_ij_k", hybrid_ij_k_reduction, {0, 2, -1}},
    {"hybrid_i_jk", hybrid_i_jk_atomic, {0, 1, -1}},
    {"parallel_k_atomic", parallel_k_atomic, {2, -1, -1}},
    {"parallel_k_reduction", parallel_k_reduction, {2, -1, -1}},
    {"collapse_jk_atomic", collapse_jk_atomic, {1, -1, -1}},
    {"collapse_jk_reduction", collapse_jk_reduction, {1, -1, -1}},
    {"collapse_ijk_atomic", collapse_ijk_atomic, {0, -1, -1}},
    {"collapse_ijk_reduction", collapse_ijk_reduction, {0, -1, -1}},
    {"nested_jk_atomic", nested_jk_atomic, {1, 2, -1}},
    {"nested_jk_reduction", nested_jk_reduction, {1, 2, -1}},
    {"nested_ik_atomic", nested_ik_atomic, {0, 2, -1}},
    {"nested_ik_reduction", nested_ik_reduction, {0, 2, -1}},
    {"nested_ijk_atomic", nested_ijk_atomic, {0, 1, 2}},
    {"nested_ijk_reduction", nested_ijk_reduction, {0, 1, 2}},
    {"hybrid_ij_k_atomic", hybrid_ij_k_atomic, {0, 2, -1}},
    {"hybrid_ij_k_reduction", hybrid_ij_k_reduction, {0, 2, -1}},
    {"hybrid_i_jk_atomic", hybrid_i_jk_atomic, {0, 1, -1}},
    {"hybrid_i_jk_reduction", hybrid_i_jk_reduction, {0, 1, -1}},
};
#define VARIANTS ((int)(sizeof(variants) / sizeof(variants[0])))

static int level_count(const Variant *variant) {
  int count = 0;
  while (count < 3 && variant->loops[count] >= 0)
    ++count;
  return count;
}

/* A total budget GP is factored exactly. Prefer balanced teams, with the
 * larger factor at the outer level. For prime GP inner teams have size 1. */
static void allocate_budget(Problem *p, const Variant *variant, int budget) {
  int count = level_count(variant), best[3] = {1, 1, 1};
  if (count == 1)
    best[0] = budget;
  else if (count >= 2) {
    int score = INT_MAX;
    for (int a = 1; a <= budget; ++a)
      for (int b = 1; b <= a; ++b) {
        if (budget % (a * b))
          continue;
        int c = budget / (a * b);
        if ((count == 2 && c != 1) || (count == 3 && c > b))
          continue;
        int current = a - (count == 3 ? c : b);
        if (current < score) {
          score = current;
          best[0] = a;
          best[1] = b;
          best[2] = c;
        }
      }
  }
  for (int q = 0; q < 3; ++q)
    p->threads[q] = 1;
  for (int q = 0; q < count; ++q)
    p->threads[variant->loops[q]] = best[q];
}

/* Probe the requested nested team tree OUTSIDE the timed multiplication.
 * Min/max at each level expose runtime serialization (e.g. thread limits).
 * This records realized team sizes in a probe, not a CPU utilization sample. */
static void probe(const Problem *p, const int *loops, int depth, int count,
                  int *minimum, int *maximum) {
  if (depth == count)
    return;
  int requested = p->threads[loops[depth]];
#pragma omp parallel num_threads(requested) default(none)                      \
    shared(p, loops, depth, count, minimum, maximum, requested)
  {
#pragma omp critical(probe_sizes)
    {
      int actual = omp_get_num_threads();
      if (actual < minimum[depth])
        minimum[depth] = actual;
      if (actual > maximum[depth])
        maximum[depth] = actual;
    }
    probe(p, loops, depth + 1, count, minimum, maximum);
  }
}

static uint64_t number(const char *text, uint64_t limit, bool allow_zero) {
  char *end;
  errno = 0;
  if (!*text)
    fail("invalid non-negative integer");
  for (const char *digit = text; *digit; ++digit)
    if (*digit < '0' || *digit > '9')
      fail("invalid non-negative integer");
  unsigned long long value = strtoull(text, &end, 10);
  if (errno || *end || value > limit || (!allow_zero && value == 0))
    fail("integer outside the allowed range");
  return (uint64_t)value;
}

static void parse_threads(const char *text, int *threads) {
  char *copy = strdup(text), *save = NULL;
  if (!copy)
    fail("allocation failed");
  int count = 0;
  for (char *part = strtok_r(copy, ",", &save); part;
       part = strtok_r(NULL, ",", &save)) {
    if (count == 3)
      fail("--threads requires exactly I,J,K");
    threads[count++] = (int)number(part, 256, false);
  }
  if (count != 3 || text[0] == ',' || text[strlen(text) - 1] == ',' ||
      strstr(text, ",,"))
    fail("--threads requires exactly I,J,K");
  free(copy);
}

static void parse_schedule(const char *text, omp_sched_t *kind, int *chunk) {
  char *copy = strdup(text);
  if (!copy)
    fail("allocation failed");
  char *colon = strchr(copy, ':');
  *chunk = 0;
  if (colon) {
    *colon++ = '\0';
    *chunk = (int)number(colon, INT_MAX, false);
  }
  if (!strcmp(copy, "static"))
    *kind = omp_sched_static;
  else if (!strcmp(copy, "dynamic"))
    *kind = omp_sched_dynamic;
  else if (!strcmp(copy, "guided"))
    *kind = omp_sched_guided;
  else
    fail("schedule must be static[:chunk], dynamic[:chunk], or guided[:chunk]");
  if (*kind != omp_sched_static && !colon)
    *chunk = 1;
  free(copy);
}

static const char *schedule_name(omp_sched_t kind) {
  return kind == omp_sched_static    ? "static"
         : kind == omp_sched_dynamic ? "dynamic"
                                     : "guided";
}

static size_t elements(int rows, int columns) {
  if ((size_t)rows > SIZE_MAX / (size_t)columns / sizeof(scalar))
    fail("matrix size overflow");
  return (size_t)rows * (size_t)columns;
}

/* SplitMix64: reproducible across machines, independent of libc rand(). */
static uint64_t random64(uint64_t *state) {
  uint64_t z = (*state += UINT64_C(0x9e3779b97f4a7c15));
  z = (z ^ (z >> 30)) * UINT64_C(0xbf58476d1ce4e5b9);
  z = (z ^ (z >> 27)) * UINT64_C(0x94d049bb133111eb);
  return z ^ (z >> 31);
}

static scalar value_for(const char *dataset, uint64_t *state) {
  if (!strcmp(dataset, "zeros"))
    return 0;
  if (!strcmp(dataset, "ones"))
    return 1;
  if (!strcmp(dataset, "max"))
    return UINT64_MAX;
  if (!strcmp(dataset, "random_full"))
    return random64(state);
  return random64(state) % 101;
}

static uint64_t checksum(const scalar *data, size_t count) {
  uint64_t hash = UINT64_C(14695981039346656037);
  for (size_t q = 0; q < count; ++q) {
    hash ^= data[q];
    hash *= UINT64_C(1099511628211);
  }
  return hash;
}

static void dump_array(const char *name, const scalar *data, size_t count) {
  printf("\"%s\":[", name);
  for (size_t q = 0; q < count; ++q)
    printf("%s%" PRIu64, q ? "," : "", data[q]);
  printf("]");
}

static void usage(void) {
  puts("Usage: ./matmul --n N --m M --r R --variant NAME [options]\n"
       "  --budget GP          total thread budget, balanced over nested "
       "levels (default 4)\n"
       "  --threads I,J,K      explicit per-loop teams; mutually exclusive "
       "with --budget\n"
       "  --schedule S[:C]     static, dynamic or guided, optional positive "
       "chunk\n"
       "  --schedule-i S[:C]   override schedule at loop i (similarly -j and "
       "-k)\n"
       "  --layout row|transposed     B storage (default row)\n"
       "  --dataset random|random_full|zeros|ones|max (default random)\n"
       "  --seed N --repeats N --warmups N   defaults 1, 5, 1\n"
       "  --dump              include A, logical row-major B and C in JSON "
       "(small cases)\n"
       "  --list              list all variants\n"
       "Output: one verified JSON record per repetition; times in seconds.");
}

typedef struct {
  const Variant *variant;
  int repeats, warmups;
  bool dump;
  uint64_t seed;
  const char *dataset;
} Options;

static bool parse_options(int argc, char **argv, Problem *p, Options *options) {
  *p = (Problem){
      .n = 10,
      .m = 10,
      .r = 10,
      .threads = {1, 1, 1},
      .schedules = {omp_sched_static, omp_sched_static, omp_sched_static},
      .chunks = {0, 0, 0}};
  *options = (Options){.variant = &variants[0],
                       .repeats = 5,
                       .warmups = 1,
                       .seed = 1,
                       .dataset = "random"};
  int budget = 4;
  bool explicit_threads = false, explicit_budget = false;
  const char *common_schedule = "static", *overrides[3] = {NULL, NULL, NULL};
  for (int q = 1; q < argc; ++q) {
    const char *option = argv[q];
    if (!strcmp(option, "--help")) {
      usage();
      return false;
    }
    if (!strcmp(option, "--list")) {
      for (int v = 0; v < VARIANTS; ++v)
        puts(variants[v].name);
      return false;
    }
    if (!strcmp(option, "--dump")) {
      options->dump = true;
      continue;
    }
    if (++q == argc)
      fail("missing option argument (use --help)");
    const char *arg = argv[q];
    if (!strcmp(option, "--n"))
      p->n = (int)number(arg, INT_MAX, false);
    else if (!strcmp(option, "--m"))
      p->m = (int)number(arg, INT_MAX, false);
    else if (!strcmp(option, "--r"))
      p->r = (int)number(arg, INT_MAX, false);
    else if (!strcmp(option, "--variant")) {
      options->variant = NULL;
      for (int v = 0; v < VARIANTS; ++v)
        if (!strcmp(arg, variants[v].name)) {
          options->variant = &variants[v];
          break;
        }
      if (!options->variant)
        fail("unknown variant (use --list)");
    } else if (!strcmp(option, "--budget")) {
      budget = (int)number(arg, 256, false);
      explicit_budget = true;
    } else if (!strcmp(option, "--threads")) {
      parse_threads(arg, p->threads);
      explicit_threads = true;
    } else if (!strcmp(option, "--schedule"))
      common_schedule = arg;
    else if (!strcmp(option, "--schedule-i"))
      overrides[0] = arg;
    else if (!strcmp(option, "--schedule-j"))
      overrides[1] = arg;
    else if (!strcmp(option, "--schedule-k"))
      overrides[2] = arg;
    else if (!strcmp(option, "--layout")) {
      if (strcmp(arg, "row") && strcmp(arg, "transposed"))
        fail("invalid B layout");
      p->transposed = !strcmp(arg, "transposed");
    } else if (!strcmp(option, "--dataset"))
      options->dataset = arg;
    else if (!strcmp(option, "--seed"))
      options->seed = number(arg, UINT64_MAX, true);
    else if (!strcmp(option, "--repeats"))
      options->repeats = (int)number(arg, 1000000, false);
    else if (!strcmp(option, "--warmups"))
      options->warmups = (int)number(arg, 1000000, true);
    else
      fail("unknown option (use --help)");
  }
  if (explicit_budget && explicit_threads)
    fail("choose --budget OR --threads");
  if (strcmp(options->dataset, "random") &&
      strcmp(options->dataset, "random_full") &&
      strcmp(options->dataset, "zeros") && strcmp(options->dataset, "ones") &&
      strcmp(options->dataset, "max"))
    fail("unknown dataset");
  for (int q = 0; q < 3; ++q)
    parse_schedule(overrides[q] ? overrides[q] : common_schedule,
                   &p->schedules[q], &p->chunks[q]);
  if (!explicit_threads)
    allocate_budget(p, options->variant, budget);
  return true;
}

typedef struct {
  size_t na, nb, nc;
  scalar *reference, *logical_b;
  int thread_budget, levels;
  int team_min[3], team_max[3];
  double reference_seconds;
} Benchmark;

typedef struct {
  double seconds;
  long minor_faults, major_faults;
} Measurement;

static void validate_problem(const Problem *p, const Options *options,
                             Benchmark *benchmark) {
  benchmark->levels = level_count(options->variant);
  benchmark->thread_budget = 1;
  for (int q = 0; q < benchmark->levels; ++q)
    benchmark->thread_budget *= p->threads[options->variant->loops[q]];
  if (benchmark->thread_budget > 4096)
    fail("total requested nested team product exceeds 4096");
  /* Collapsed loops use 64-bit counters. Bound their iteration products. */
  if ((uint64_t)p->n * p->m > (uint64_t)LLONG_MAX / (uint64_t)p->r)
    fail("iteration space exceeds signed 64-bit indexing");
  benchmark->na = elements(p->n, p->m);
  benchmark->nb = elements(p->m, p->r);
  benchmark->nc = elements(p->n, p->r);
  size_t na = benchmark->na, nb = benchmark->nb, nc = benchmark->nc;
  if (options->dump && (na > 4096 || nb > 4096 || nc > 4096))
    fail("--dump is limited to 4096 elements per matrix");
  /* Refuse obviously unreasonable requests before the OS overcommits RAM. */
  const uint64_t max_elements = UINT64_C(2147483648) / sizeof(scalar);
  if (na > max_elements || nb > max_elements || nc > max_elements ||
      na + 2 * (uint64_t)nb + 2 * (uint64_t)nc > max_elements)
    fail("working set exceeds 2 GiB; reduce dimensions");
}

static void allocate_matrices(Problem *p, Benchmark *benchmark) {
  p->a = malloc(benchmark->na * sizeof(scalar));
  p->b = malloc(benchmark->nb * sizeof(scalar));
  p->c = calloc(benchmark->nc, sizeof(scalar));
  benchmark->reference = calloc(benchmark->nc, sizeof(scalar));
  if (!p->a || !p->b || !p->c || !benchmark->reference)
    fail("matrix allocation failed");
  benchmark->logical_b = malloc(benchmark->nb * sizeof(scalar));
  if (!benchmark->logical_b)
    fail("reference allocation failed");
}

static void initialize_matrices(const Problem *p, const Options *options,
                                const Benchmark *benchmark) {
  uint64_t state = options->seed;
  for (size_t q = 0; q < benchmark->na; ++q)
    p->a[q] = value_for(options->dataset, &state);
  /* Generate logical B in the same order for both storage layouts. */
  for (int k = 0; k < p->m; ++k)
    for (int j = 0; j < p->r; ++j) {
      size_t index =
          p->transposed ? (size_t)j * p->m + k : (size_t)k * p->r + j;
      p->b[index] = value_for(options->dataset, &state);
    }
  /* Force first-touch of output pages before any timed kernel. */
  memset(p->c, 0, benchmark->nc * sizeof(scalar));
  memset(benchmark->reference, 0, benchmark->nc * sizeof(scalar));
}

static void configure_openmp(const Problem *p, const Variant *variant,
                             Benchmark *benchmark) {
  /* Disable auto ajusting team sizing. Use the sizes given at the input */
  omp_set_dynamic(0);
  /* Allow max 3 levels of nested parallel regions */
  omp_set_max_active_levels(3);
  for (int q = 0; q < 3; ++q) {
    benchmark->team_min[q] = INT_MAX;
    benchmark->team_max[q] = 0;
  }
  probe(p, variant->loops, 0, benchmark->levels, benchmark->team_min,
        benchmark->team_max);
}

static void compute_reference(const Problem *p, Benchmark *benchmark) {
  /* An independent row-major sequential reference, even for transposed B. */
  scalar *logical_b = benchmark->logical_b;
  scalar *reference = benchmark->reference;
  for (int k = 0; k < p->m; ++k)
    for (int j = 0; j < p->r; ++j)
      logical_b[(size_t)k * p->r + j] = b_at(p, k, j);

  double start = omp_get_wtime();
  for (int i = 0; i < p->n; ++i)
    for (int j = 0; j < p->r; ++j) {
      scalar sum = 0;
      for (int k = 0; k < p->m; ++k)
        sum += p->a[(size_t)i * p->m + k] * logical_b[(size_t)k * p->r + j];
      reference[(size_t)i * p->r + j] = sum;
    }
  benchmark->reference_seconds = omp_get_wtime() - start;
}

static Measurement measure_kernel(const Problem *p, const Variant *variant,
                                  size_t nc) {
  memset(p->c, 0, nc * sizeof(scalar));
  struct rusage before, after;
  if (getrusage(RUSAGE_SELF, &before))
    fail("getrusage failed");
  double start = omp_get_wtime();
  variant->run(p);
  double seconds = omp_get_wtime() - start;
  if (getrusage(RUSAGE_SELF, &after))
    fail("getrusage failed");
  return (Measurement){.seconds = seconds,
                       .minor_faults = after.ru_minflt - before.ru_minflt,
                       .major_faults = after.ru_majflt - before.ru_majflt};
}

static bool verify_result(const Problem *p, const Benchmark *benchmark) {
  /* Check every entry after every run, including warmups. */
  for (size_t q = 0; q < benchmark->nc; ++q)
    if (p->c[q] != benchmark->reference[q]) {
      fprintf(stderr,
              "Mismatch at (%zu,%zu): got %" PRIu64 ", expected %" PRIu64 "\n",
              q / (size_t)p->r, q % (size_t)p->r, p->c[q],
              benchmark->reference[q]);
      return false;
    }
  return true;
}

static void print_record(const Problem *p, const Options *options,
                         const Benchmark *benchmark, int iteration,
                         const Measurement *measurement) {
  printf("{\"variant\":\"%s\",\"n\":%d,\"m\":%d,\"r\":%d,\"layout\":\"%s\","
         "\"dataset\":\"%s\",\"seed\":%" PRIu64 ",\"repeat\":%d,\"gp\":%d,"
         "\"threads_i\":%d,\"threads_j\":%d,\"threads_k\":%d,",
         options->variant->name, p->n, p->m, p->r,
         p->transposed ? "transposed" : "row", options->dataset, options->seed,
         iteration, benchmark->thread_budget, p->threads[0], p->threads[1],
         p->threads[2]);
  for (int q = 0; q < 3; ++q)
    printf("\"schedule_%c\":\"%s\",\"chunk_%c\":%d,", 'i' + q,
           schedule_name(p->schedules[q]), 'i' + q, p->chunks[q]);
  printf("\"team_min\":[%d,%d,%d],\"team_max\":[%d,%d,%d],\"levels\":%d,"
         "\"max_active_levels\":%d,\"thread_limit\":%d,\"seconds\":%.12g,"
         "\"reference_seconds\":%.12g,"
         "\"minor_faults\":%ld,\"major_faults\":%ld,\"verified\":true,"
         "\"checksum\":\"%016" PRIx64 "\"",
         benchmark->levels > 0 ? benchmark->team_min[0] : 0,
         benchmark->levels > 1 ? benchmark->team_min[1] : 0,
         benchmark->levels > 2 ? benchmark->team_min[2] : 0,
         benchmark->team_max[0], benchmark->team_max[1], benchmark->team_max[2],
         benchmark->levels, omp_get_max_active_levels(), omp_get_thread_limit(),
         measurement->seconds, benchmark->reference_seconds,
         measurement->minor_faults, measurement->major_faults,
         checksum(p->c, benchmark->nc));
  if (options->dump) {
    putchar(',');
    dump_array("a", p->a, benchmark->na);
    putchar(',');
    dump_array("b", benchmark->logical_b, benchmark->nb);
    putchar(',');
    dump_array("c", p->c, benchmark->nc);
  }
  puts("}");
  fflush(stdout);
}

static bool run_benchmark(const Problem *p, const Options *options,
                          const Benchmark *benchmark) {
  for (int iteration = -options->warmups; iteration < options->repeats;
       ++iteration) {
    Measurement measurement =
        measure_kernel(p, options->variant, benchmark->nc);
    if (!verify_result(p, benchmark))
      return false;
    if (iteration >= 0)
      print_record(p, options, benchmark, iteration, &measurement);
  }
  return true;
}

static void free_matrices(Problem *p, Benchmark *benchmark) {
  free(benchmark->logical_b);
  free(benchmark->reference);
  free(p->c);
  free(p->b);
  free(p->a);
}

int main(int argc, char **argv) {
  Problem p;
  Options options;
  Benchmark benchmark = {0};
  if (!parse_options(argc, argv, &p, &options))
    return EXIT_SUCCESS;

  validate_problem(&p, &options, &benchmark);
  allocate_matrices(&p, &benchmark);
  initialize_matrices(&p, &options, &benchmark);
  configure_openmp(&p, options.variant, &benchmark);
  compute_reference(&p, &benchmark);
  bool success = run_benchmark(&p, &options, &benchmark);
  free_matrices(&p, &benchmark);
  return success ? EXIT_SUCCESS : EXIT_FAILURE;
}
