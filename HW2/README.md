# HW2 — Înmulțirea matricilor cu OpenMP

Rezolvarea [temei 2](https://edu.info.uaic.ro/sisteme-de-operare-distribuite/SOD/labs/homeworks/tema2.html) include referința secvențială, **10 variante cerute**, **2 variante bonus** și un studiu experimental pe **Victus și HP-Laptop**. Fiecare rulare OpenMP folosește memoria partajată a unui singur calculator.

- [Exemple de rulare](USAGE.md) și [vizualizare interactivă](USAGE.html).
- [Metodologia și reproducerea studiului](EXPERIMENTS.md).
- [Raport](results/study/report.md), [prezentare HTML](results/study/dashboard.html), [date CSV](results/study/summary.csv) și [grafice PNG/SVG](figures/study/).

## Compilare și rulare

Necesită GCC cu OpenMP. Scripturile folosesc Python 3.10+, iar graficele necesită Matplotlib și NumPy.

```bash
cd HW2
make
./matmul --n 100 --m 200 --r 150 --variant parallel_i --budget 4
./matmul --list
./matmul --help
```

Programul generează A[n,m] și B[m,r], apoi verifică fiecare element din C[n,r] față de referința secvențială. Implicit face o încălzire și cinci repetări măsurate. Scrie câte un obiect JSON pe linie pentru fiecare repetare verificată și returnează un cod nenul la o eroare de corectitudine.

`--seed` reproduce intrările pe ambele platforme și în ambele layout-uri. Pentru matrici mici, `--dump` include A, B logică și C în ordinea pe linii, cu o limită de 4096 elemente per matrice.

```bash
./matmul --n 3 --m 7 --r 5 --variant collapse_ijk --budget 4 --repeats 1 --dump
```

## Variante OpenMP

| Variantă CLI | Bucle paralele | Echipe cerute | Protecția rezultatului |
| --- | --- | --- | --- |
| `seq` | niciuna | 1 fir | referință secvențială |
| `parallel_i` | i | Ti | linii distincte |
| `parallel_j` | j, pentru fiecare i | Tj | celule distincte |
| `parallel_k` | k, pentru fiecare (i,j) | Tk | `reduction(+:sum)` |
| `collapse_ij` | i și j, `collapse(2)` | Ti | celule distincte |
| `collapse_jk` | j și k, `collapse(2)`, pentru fiecare i | Tj | `atomic update` |
| `collapse_ijk` | i, j și k, `collapse(3)` | Ti | `atomic update` |
| `nested_ij` | i, apoi echipe j | Ti × Tj | celule distincte |
| `nested_jk` | j, apoi echipe k | Tj × Tk | reducere pe k |
| `nested_ik` | i, apoi echipe k, cu j secvențial | Ti × Tk | reducere pe k |
| `nested_ijk` | i, apoi j, apoi k | Ti × Tj × Tk | reducere pe k |
| `hybrid_ij_k` (bonus) | `collapse(ij)`, apoi echipe k | Ti × Tk | reducere pe k |
| `hybrid_i_jk` (bonus) | i, apoi echipe `collapse(jk)` | Ti × Tj | `atomic update` |

Un `collapse` folosește o singură echipă. Când k este paralel, mai multe fire contribuie la aceeași celulă, prin sume private combinate la reducere sau prin actualizări atomice. `--list` afișează și variantele cu sufixele `_atomic` și `_reduction`.

## Fire și scheduling

- `--budget GP` factorizează bugetul între echipele imbricate. GP=8 dă (2,2,2) pentru trei niveluri și (4,2) pentru două. Pentru GP prim, echipele interioare au câte un fir.
- `--threads I,J,K` setează explicit echipele și este incompatibil cu `--budget`. Buclele secvențiale sunt ignorate, iar un grup `collapse` preia numărul de fire și politica primei bucle.
- `--schedule` setează politica globală, cu suprascrieri prin `--schedule-i`, `--schedule-j` și `--schedule-k`. Politicile `static`, `dynamic` și `guided` acceptă un chunk pozitiv opțional. Fără chunk, `static` folosește împărțirea implicită, iar `dynamic` și `guided` folosesc 1.

```bash
OMP_WAIT_POLICY=PASSIVE ./matmul --n 30 --m 200 --r 40 \
  --variant nested_ijk --threads 2,2,2 \
  --schedule-i static --schedule-j dynamic:4 --schedule-k guided:8
```

Programul permite trei niveluri active. Câmpurile `team_min` și `team_max` provin dintr-o probă de echipe efectuată în afara măsurării și arată când runtime-ul formează echipe mai mici decât cele cerute.

## Intrări și măsurare

Matricile folosesc `uint64_t`, cu aritmetică modulo 2⁶⁴. Opțiunea `--dataset` acceptă `random` (valori între 0 și 100), `zeros`, `ones`, `max` (UINT64_MAX) și `random_full` (valori aleatoare pe 64 de biți). Cazurile „best” și „worst” din enunț corespund intrărilor `zeros` și `max`. Nucleul execută aceleași operații pentru toate seturile.

`--layout row` stochează B pe linii. `--layout transposed` stochează B pe coloane, astfel încât ambii operanzi ai produsului scalar sunt citiți consecutiv.

`seconds` măsoară apelul de înmulțire cu `omp_get_wtime()`, inclusiv costurile OpenMP. Pregătirea matricilor și verificarea au loc în afara intervalului. Câmpurile `minor_faults` și `major_faults` numără page faults în timpul apelului. `reference_seconds` măsoară referința de verificare, iar speedup-ul studiului folosește rulări `seq` separate, în aceleași condiții experimentale.

## Benchmark-uri, raport și teste

```bash
# Colectarea studiului pe ambele calculatoare
python3 benchmark.py --hosts local HP-Laptop --collect-only

# Regenerarea raportului din datele existente
python3 analyze.py --input results/study
# Dacă Matplotlib și NumPy lipsesc
uv run --with matplotlib --with numpy python analyze.py --input results/study

# Probă de colectare într-un director separat
python3 benchmark.py --profile smoke --collect-only --output /tmp/hw2-smoke

# Teste și verificare cu UndefinedBehaviorSanitizer
make test
make debug
MATMUL_EXE="$PWD/matmul_debug" python3 -m unittest discover -s tests -p test_matmul.py -v
```

`--hosts` rulează pe fiecare calculator separat. Pentru o gazdă SSH, scriptul folosește autentificarea existentă, compilează într-un director temporar pe gazdă și copiază datele înapoi. Colectarea se reia din jurnal când sursele, planul, setările și mediul OpenMP coincid. Pentru o campanie nouă, folosește alt `--output`. Detaliile sunt în [EXPERIMENTS.md](EXPERIMENTS.md).

[Toate temele](../README.md)
