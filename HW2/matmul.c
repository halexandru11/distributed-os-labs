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

static const char *names[] = {
    "seq", "parallel_i", "parallel_j", "parallel_k",
    "collapse_ij", "collapse_jk", "collapse_ijk",
    "nested_ij", "nested_jk", "nested_ik", "nested_ijk",
    "hybrid_ij_k", "hybrid_i_jk"
};
#define VARIANTS ((int)(sizeof(names) / sizeof(names[0])))

static void fail(const char *message) {
    fprintf(stderr, "Error: %s\n", message);
    exit(EXIT_FAILURE);
}

static inline scalar b_at(const Problem *p, int k, int j) {
    return p->transposed ? p->b[(size_t)j * p->m + k]
                         : p->b[(size_t)k * p->r + j];
}

static inline scalar dot(const Problem *p, int i, int j) {
    scalar sum = 0;
    for (int k = 0; k < p->m; ++k)
        sum += p->a[(size_t)i * p->m + k] * b_at(p, k, j);
    return sum;
}

/* run-sched-var is a task ICV: set it in the encountering task BEFORE the
 * parallel region, so the implicit tasks inherit the requested schedule. */
static void schedule_at(const Problem *p, int loop) {
    omp_set_schedule(p->schedules[loop], p->chunks[loop]);
}

static void sequential(Problem *p) {
    for (int i = 0; i < p->n; ++i)
        for (int j = 0; j < p->r; ++j)
            p->c[(size_t)i * p->r + j] = dot(p, i, j);
}

static void parallel_i(Problem *p) {
    schedule_at(p, 0);
    #pragma omp parallel for num_threads(p->threads[0]) schedule(runtime) default(none) shared(p)
    for (int i = 0; i < p->n; ++i)
        for (int j = 0; j < p->r; ++j)
            p->c[(size_t)i * p->r + j] = dot(p, i, j);
}

static void parallel_j(Problem *p) {
    schedule_at(p, 1);
    for (int i = 0; i < p->n; ++i) {
        #pragma omp parallel for num_threads(p->threads[1]) schedule(runtime) default(none) shared(p, i)
        for (int j = 0; j < p->r; ++j)
            p->c[(size_t)i * p->r + j] = dot(p, i, j);
    }
}

static void parallel_k(Problem *p) {
    schedule_at(p, 2);
    for (int i = 0; i < p->n; ++i)
        for (int j = 0; j < p->r; ++j) {
            scalar sum = 0;
            #pragma omp parallel for num_threads(p->threads[2]) schedule(runtime) reduction(+:sum) default(none) shared(p, i, j)
            for (int k = 0; k < p->m; ++k)
                sum += p->a[(size_t)i * p->m + k] * b_at(p, k, j);
            p->c[(size_t)i * p->r + j] = sum;
        }
}

static void collapse_ij(Problem *p) {
    schedule_at(p, 0);
    #pragma omp parallel for collapse(2) num_threads(p->threads[0]) schedule(runtime) default(none) shared(p)
    for (int i = 0; i < p->n; ++i)
        for (int j = 0; j < p->r; ++j)
            p->c[(size_t)i * p->r + j] = dot(p, i, j);
}

static void collapse_jk(Problem *p) {
    schedule_at(p, 1);
    for (int i = 0; i < p->n; ++i) {
        #pragma omp parallel for collapse(2) num_threads(p->threads[1]) schedule(runtime) default(none) shared(p, i)
        for (int j = 0; j < p->r; ++j)
            for (int k = 0; k < p->m; ++k) {
                scalar term = p->a[(size_t)i * p->m + k] * b_at(p, k, j);
                /* Several collapsed iterations contribute to the same cell. */
                #pragma omp atomic update
                p->c[(size_t)i * p->r + j] += term;
            }
    }
}

static void collapse_ijk(Problem *p) {
    schedule_at(p, 0);
    #pragma omp parallel for collapse(3) num_threads(p->threads[0]) schedule(runtime) default(none) shared(p)
    for (int i = 0; i < p->n; ++i)
        for (int j = 0; j < p->r; ++j)
            for (int k = 0; k < p->m; ++k) {
                scalar term = p->a[(size_t)i * p->m + k] * b_at(p, k, j);
                #pragma omp atomic update
                p->c[(size_t)i * p->r + j] += term;
            }
}

static void nested_ij(Problem *p) {
    schedule_at(p, 0);
    #pragma omp parallel for num_threads(p->threads[0]) schedule(runtime) default(none) shared(p)
    for (int i = 0; i < p->n; ++i) {
        schedule_at(p, 1);
        #pragma omp parallel for num_threads(p->threads[1]) schedule(runtime) default(none) shared(p, i)
        for (int j = 0; j < p->r; ++j)
            p->c[(size_t)i * p->r + j] = dot(p, i, j);
    }
}

static void nested_jk(Problem *p) {
    schedule_at(p, 1);
    for (int i = 0; i < p->n; ++i) {
        #pragma omp parallel for num_threads(p->threads[1]) schedule(runtime) default(none) shared(p, i)
        for (int j = 0; j < p->r; ++j) {
            scalar sum = 0;
            schedule_at(p, 2);
            #pragma omp parallel for num_threads(p->threads[2]) schedule(runtime) reduction(+:sum) default(none) shared(p, i, j)
            for (int k = 0; k < p->m; ++k)
                sum += p->a[(size_t)i * p->m + k] * b_at(p, k, j);
            p->c[(size_t)i * p->r + j] = sum;
        }
    }
}

static void nested_ik(Problem *p) {
    schedule_at(p, 0);
    #pragma omp parallel for num_threads(p->threads[0]) schedule(runtime) default(none) shared(p)
    for (int i = 0; i < p->n; ++i) {
        schedule_at(p, 2);
        for (int j = 0; j < p->r; ++j) {
            scalar sum = 0;
            #pragma omp parallel for num_threads(p->threads[2]) schedule(runtime) reduction(+:sum) default(none) shared(p, i, j)
            for (int k = 0; k < p->m; ++k)
                sum += p->a[(size_t)i * p->m + k] * b_at(p, k, j);
            p->c[(size_t)i * p->r + j] = sum;
        }
    }
}

static void nested_ijk(Problem *p) {
    schedule_at(p, 0);
    #pragma omp parallel for num_threads(p->threads[0]) schedule(runtime) default(none) shared(p)
    for (int i = 0; i < p->n; ++i) {
        schedule_at(p, 1);
        #pragma omp parallel for num_threads(p->threads[1]) schedule(runtime) default(none) shared(p, i)
        for (int j = 0; j < p->r; ++j) {
            scalar sum = 0;
            schedule_at(p, 2);
            #pragma omp parallel for num_threads(p->threads[2]) schedule(runtime) reduction(+:sum) default(none) shared(p, i, j)
            for (int k = 0; k < p->m; ++k)
                sum += p->a[(size_t)i * p->m + k] * b_at(p, k, j);
            p->c[(size_t)i * p->r + j] = sum;
        }
    }
}

static void hybrid_ij_k(Problem *p) {
    schedule_at(p, 0);
    #pragma omp parallel for collapse(2) num_threads(p->threads[0]) schedule(runtime) default(none) shared(p)
    for (int i = 0; i < p->n; ++i)
        for (int j = 0; j < p->r; ++j) {
            scalar sum = 0;
            schedule_at(p, 2);
            #pragma omp parallel for num_threads(p->threads[2]) schedule(runtime) reduction(+:sum) default(none) shared(p, i, j)
            for (int k = 0; k < p->m; ++k)
                sum += p->a[(size_t)i * p->m + k] * b_at(p, k, j);
            p->c[(size_t)i * p->r + j] = sum;
        }
}

static void hybrid_i_jk(Problem *p) {
    schedule_at(p, 0);
    #pragma omp parallel for num_threads(p->threads[0]) schedule(runtime) default(none) shared(p)
    for (int i = 0; i < p->n; ++i) {
        schedule_at(p, 1);
        #pragma omp parallel for collapse(2) num_threads(p->threads[1]) schedule(runtime) default(none) shared(p, i)
        for (int j = 0; j < p->r; ++j)
            for (int k = 0; k < p->m; ++k) {
                scalar term = p->a[(size_t)i * p->m + k] * b_at(p, k, j);
                #pragma omp atomic update
                p->c[(size_t)i * p->r + j] += term;
            }
    }
}

static void (*kernels[])(Problem *) = {
    sequential, parallel_i, parallel_j, parallel_k, collapse_ij,
    collapse_jk, collapse_ijk, nested_ij, nested_jk, nested_ik,
    nested_ijk, hybrid_ij_k, hybrid_i_jk
};

/* OpenMP levels used by each variant; a collapse uses ONE team. */
static const int levels[VARIANTS][3] = {
    {-1,-1,-1}, {0,-1,-1}, {1,-1,-1}, {2,-1,-1},
    {0,-1,-1}, {1,-1,-1}, {0,-1,-1}, {0,1,-1},
    {1,2,-1}, {0,2,-1}, {0,1,2}, {0,2,-1}, {0,1,-1}
};

static int level_count(int variant) {
    int count = 0;
    while (count < 3 && levels[variant][count] >= 0) ++count;
    return count;
}

/* A total budget GP is factored exactly. Prefer balanced teams, with the
 * larger factor at the outer level. For prime GP inner teams have size 1. */
static void allocate_budget(Problem *p, int variant, int budget) {
    int count = level_count(variant), best[3] = {1,1,1};
    if (count == 1) best[0] = budget;
    else if (count >= 2) {
        int score = INT_MAX;
        for (int a = 1; a <= budget; ++a)
            for (int b = 1; b <= a; ++b) {
                if (budget % (a*b)) continue;
                int c = budget / (a*b);
                if ((count == 2 && c != 1) || (count == 3 && c > b)) continue;
                int current = a - (count == 3 ? c : b);
                if (current < score) {
                    score = current;
                    best[0] = a; best[1] = b; best[2] = c;
                }
            }
    }
    for (int q = 0; q < 3; ++q) p->threads[q] = 1;
    for (int q = 0; q < count; ++q) p->threads[levels[variant][q]] = best[q];
}

/* Probe the requested nested team tree OUTSIDE the timed multiplication.
 * Min/max at each level expose runtime serialization (e.g. thread limits).
 * This records realized team sizes in a probe, not a CPU utilization sample. */
static void probe(const Problem *p, const int *loops, int depth, int count,
                  int *minimum, int *maximum) {
    if (depth == count) return;
    int requested = p->threads[loops[depth]];
    #pragma omp parallel num_threads(requested) default(none) shared(p, loops, depth, count, minimum, maximum, requested)
    {
        #pragma omp critical(probe_sizes)
        {
            int actual = omp_get_num_threads();
            if (actual < minimum[depth]) minimum[depth] = actual;
            if (actual > maximum[depth]) maximum[depth] = actual;
        }
        probe(p, loops, depth+1, count, minimum, maximum);
    }
}

static uint64_t number(const char *text, uint64_t limit, bool allow_zero) {
    char *end;
    errno = 0;
    if (!*text || *text == '-' || *text == '+') fail("invalid non-negative integer");
    unsigned long long value = strtoull(text, &end, 10);
    if (errno || *end || value > limit || (!allow_zero && value == 0))
        fail("integer outside the allowed range");
    return (uint64_t)value;
}

static void parse_threads(const char *text, int *threads) {
    char *copy = strdup(text), *save = NULL;
    if (!copy) fail("allocation failed");
    int count = 0;
    for (char *part = strtok_r(copy, ",", &save); part; part = strtok_r(NULL, ",", &save)) {
        if (count == 3) fail("--threads requires exactly I,J,K");
        threads[count++] = (int)number(part, 256, false);
    }
    if (count != 3 || text[0] == ',' || text[strlen(text)-1] == ',' || strstr(text, ",,"))
        fail("--threads requires exactly I,J,K");
    free(copy);
}

static void parse_schedule(const char *text, omp_sched_t *kind, int *chunk) {
    char *copy = strdup(text);
    if (!copy) fail("allocation failed");
    char *colon = strchr(copy, ':');
    *chunk = 0;
    if (colon) {
        *colon++ = '\0';
        *chunk = (int)number(colon, INT_MAX, false);
    }
    if (!strcmp(copy, "static")) *kind = omp_sched_static;
    else if (!strcmp(copy, "dynamic")) *kind = omp_sched_dynamic;
    else if (!strcmp(copy, "guided")) *kind = omp_sched_guided;
    else fail("schedule must be static[:chunk], dynamic[:chunk], or guided[:chunk]");
    if (*kind != omp_sched_static && !colon) *chunk = 1;
    free(copy);
}

static const char *schedule_name(omp_sched_t kind) {
    return kind == omp_sched_static ? "static" : kind == omp_sched_dynamic ? "dynamic" : "guided";
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
    if (!strcmp(dataset, "zeros")) return 0;
    if (!strcmp(dataset, "ones")) return 1;
    if (!strcmp(dataset, "max")) return UINT64_MAX;
    if (!strcmp(dataset, "random_full")) return random64(state);
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
         "  --budget GP          total thread budget, balanced over nested levels (default 4)\n"
         "  --threads I,J,K      explicit per-loop teams; mutually exclusive with --budget\n"
         "  --schedule S[:C]     static, dynamic or guided, optional positive chunk\n"
         "  --schedule-i S[:C]   override schedule at loop i (similarly -j and -k)\n"
         "  --layout row|transposed     B storage (default row)\n"
         "  --dataset random|random_full|zeros|ones|max (default random)\n"
         "  --seed N --repeats N --warmups N   defaults 1, 5, 1\n"
         "  --dump              include A, logical row-major B and C in JSON (small cases)\n"
         "  --list              list all variants\n"
         "Output: one verified JSON record per repetition; times in seconds.");
}

int main(int argc, char **argv) {
    Problem p = {.n=10, .m=10, .r=10, .threads={1,1,1},
                 .schedules={omp_sched_static,omp_sched_static,omp_sched_static}, .chunks={0,0,0}};
    int variant = 0, budget = 4, repeats = 5, warmups = 1;
    bool explicit_threads = false, explicit_budget = false, dump = false;
    uint64_t seed = 1;
    const char *dataset = "random";
    const char *common_schedule = "static", *overrides[3] = {NULL,NULL,NULL};
    for (int q = 1; q < argc; ++q) {
        const char *option = argv[q];
        if (!strcmp(option, "--help")) { usage(); return 0; }
        if (!strcmp(option, "--list")) {
            for (int v = 0; v < VARIANTS; ++v) puts(names[v]);
            return 0;
        }
        if (!strcmp(option, "--dump")) { dump = true; continue; }
        if (++q == argc) fail("missing option argument (use --help)");
        const char *arg = argv[q];
        if (!strcmp(option, "--n")) p.n = (int)number(arg, INT_MAX, false);
        else if (!strcmp(option, "--m")) p.m = (int)number(arg, INT_MAX, false);
        else if (!strcmp(option, "--r")) p.r = (int)number(arg, INT_MAX, false);
        else if (!strcmp(option, "--variant")) {
            variant = -1;
            for (int v = 0; v < VARIANTS; ++v) if (!strcmp(arg, names[v])) variant = v;
            if (variant < 0) fail("unknown variant (use --list)");
        } else if (!strcmp(option, "--budget")) {
            budget = (int)number(arg, 256, false); explicit_budget = true;
        } else if (!strcmp(option, "--threads")) {
            parse_threads(arg, p.threads); explicit_threads = true;
        } else if (!strcmp(option, "--schedule")) common_schedule = arg;
        else if (!strcmp(option, "--schedule-i")) overrides[0] = arg;
        else if (!strcmp(option, "--schedule-j")) overrides[1] = arg;
        else if (!strcmp(option, "--schedule-k")) overrides[2] = arg;
        else if (!strcmp(option, "--layout")) {
            if (strcmp(arg, "row") && strcmp(arg, "transposed")) fail("invalid B layout");
            p.transposed = !strcmp(arg, "transposed");
        } else if (!strcmp(option, "--dataset")) dataset = arg;
        else if (!strcmp(option, "--seed")) seed = number(arg, UINT64_MAX, true);
        else if (!strcmp(option, "--repeats")) repeats = (int)number(arg, 1000000, false);
        else if (!strcmp(option, "--warmups")) warmups = (int)number(arg, 1000000, true);
        else fail("unknown option (use --help)");
    }
    if (explicit_budget && explicit_threads) fail("choose --budget OR --threads");
    if (strcmp(dataset,"random") && strcmp(dataset,"random_full") && strcmp(dataset,"zeros") &&
        strcmp(dataset,"ones") && strcmp(dataset,"max")) fail("unknown dataset");
    for (int q = 0; q < 3; ++q)
        parse_schedule(overrides[q] ? overrides[q] : common_schedule, &p.schedules[q], &p.chunks[q]);
    if (!explicit_threads) allocate_budget(&p, variant, budget);
    int count = level_count(variant), gp = 1;
    for (int q = 0; q < count; ++q) gp *= p.threads[levels[variant][q]];
    if (gp > 4096) fail("total requested nested team product exceeds 4096");
    /* Bound the collapsed induction spaces before libgomp multiplies them. */
    if ((uint64_t)p.n * p.m > (uint64_t)LLONG_MAX / (uint64_t)p.r)
        fail("iteration space exceeds signed 64-bit indexing");
    size_t na = elements(p.n,p.m), nb = elements(p.m,p.r), nc = elements(p.n,p.r);
    if (dump && (na > 4096 || nb > 4096 || nc > 4096)) fail("--dump is limited to 4096 elements per matrix");
    /* Refuse obviously unreasonable requests before the OS overcommits RAM. */
    const uint64_t max_elements = UINT64_C(2147483648) / sizeof(scalar);
    if (na > max_elements || nb > max_elements || nc > max_elements ||
        na + 2*(uint64_t)nb + 2*(uint64_t)nc > max_elements)
        fail("working set exceeds 2 GiB; reduce dimensions");
    p.a = malloc(na*sizeof(scalar)); p.b = malloc(nb*sizeof(scalar));
    p.c = calloc(nc,sizeof(scalar)); scalar *reference = calloc(nc,sizeof(scalar));
    if (!p.a || !p.b || !p.c || !reference) fail("matrix allocation failed");
    uint64_t state = seed;
    for (size_t q = 0; q < na; ++q) p.a[q] = value_for(dataset, &state);
    /* Generate logical B in the same order for both storage layouts. */
    for (int k = 0; k < p.m; ++k)
        for (int j = 0; j < p.r; ++j) {
            size_t index = p.transposed ? (size_t)j*p.m+k : (size_t)k*p.r+j;
            p.b[index] = value_for(dataset, &state);
        }
    /* Force first-touch of output pages before any timed kernel. */
    memset(p.c, 0, nc*sizeof(scalar));
    memset(reference, 0, nc*sizeof(scalar));
    omp_set_dynamic(0);
    omp_set_max_active_levels(3);
    int minimum[3] = {INT_MAX,INT_MAX,INT_MAX}, maximum[3] = {0,0,0};
    probe(&p, levels[variant], 0, count, minimum, maximum);
    /* An independent row-major sequential reference, even for transposed B. */
    scalar *logical_b = malloc(nb*sizeof(scalar));
    if (!logical_b) fail("reference allocation failed");
    for (int k = 0; k < p.m; ++k)
        for (int j = 0; j < p.r; ++j) logical_b[(size_t)k*p.r+j] = b_at(&p,k,j);
    double reference_start = omp_get_wtime();
    for (int i = 0; i < p.n; ++i)
        for (int j = 0; j < p.r; ++j) {
            scalar sum = 0;
            for (int k = 0; k < p.m; ++k) sum += p.a[(size_t)i*p.m+k]*logical_b[(size_t)k*p.r+j];
            reference[(size_t)i*p.r+j] = sum;
        }
    double reference_seconds = omp_get_wtime() - reference_start;
    for (int iteration = -warmups; iteration < repeats; ++iteration) {
        memset(p.c, 0, nc*sizeof(scalar));
        struct rusage before, after;
        if (getrusage(RUSAGE_SELF, &before)) fail("getrusage failed");
        double start = omp_get_wtime();
        kernels[variant](&p);
        double seconds = omp_get_wtime() - start;
        if (getrusage(RUSAGE_SELF, &after)) fail("getrusage failed");
        /* All entries, not just checksums, are checked after EVERY run. */
        for (size_t q = 0; q < nc; ++q)
            if (p.c[q] != reference[q]) {
                fprintf(stderr,"Mismatch at (%zu,%zu): got %" PRIu64 ", expected %" PRIu64 "\n",
                        q/(size_t)p.r,q%(size_t)p.r,p.c[q],reference[q]);
                return EXIT_FAILURE;
            }
        if (iteration < 0) continue;
        printf("{\"variant\":\"%s\",\"n\":%d,\"m\":%d,\"r\":%d,\"layout\":\"%s\","
               "\"dataset\":\"%s\",\"seed\":%" PRIu64 ",\"repeat\":%d,\"gp\":%d,"
               "\"threads_i\":%d,\"threads_j\":%d,\"threads_k\":%d,",
               names[variant],p.n,p.m,p.r,p.transposed?"transposed":"row",dataset,seed,iteration,gp,
               p.threads[0],p.threads[1],p.threads[2]);
        for (int q = 0; q < 3; ++q)
            printf("\"schedule_%c\":\"%s\",\"chunk_%c\":%d,",'i'+q,schedule_name(p.schedules[q]),'i'+q,p.chunks[q]);
        printf("\"team_min\":[%d,%d,%d],\"team_max\":[%d,%d,%d],\"levels\":%d,"
               "\"max_active_levels\":%d,\"thread_limit\":%d,\"seconds\":%.12g,\"reference_seconds\":%.12g,"
               "\"minor_faults\":%ld,\"major_faults\":%ld,\"verified\":true,\"checksum\":\"%016" PRIx64 "\"",
               count>0?minimum[0]:0,count>1?minimum[1]:0,count>2?minimum[2]:0,
               maximum[0],maximum[1],maximum[2],count,omp_get_max_active_levels(),omp_get_thread_limit(),
               seconds,reference_seconds,after.ru_minflt-before.ru_minflt,after.ru_majflt-before.ru_majflt,
               checksum(p.c,nc));
        if (dump) {
            putchar(','); dump_array("a",p.a,na); putchar(','); dump_array("b",logical_b,nb);
            putchar(','); dump_array("c",p.c,nc);
        }
        puts("}");
        fflush(stdout);
    }
    free(logical_b); free(reference); free(p.c); free(p.b); free(p.a);
    return EXIT_SUCCESS;
}
