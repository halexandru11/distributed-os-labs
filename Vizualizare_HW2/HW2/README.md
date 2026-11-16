# HW2 — Înmulțirea matricilor cu OpenMP

Rezolvarea [temei 2](https://edu.info.uaic.ro/sisteme-de-operare-distribuite/SOD/labs/homeworks/tema2.html): referință secvențială, cele **10 variante cerute**, cele **2 variante bonus**, verificarea rezultatelor și studiul experimental pe **Victus și HP-Laptop**. Spre deosebire de HW1, fiecare proces OpenMP folosește memoria partajată a unui singur calculator; experimentele se repetă separat pe fiecare platformă.

- [EXPERIMENTS.md](EXPERIMENTS.md): metodologia, acoperirea cerințelor și reproducerea studiului.
- [Laboratorul interactiv HTML](interactive.html): editarea/paste-ul matricilor, toate cele 13 moduri inclusiv seq, echipe/schedule/chunk per buclă, vizualizarea contribuțiilor, execuția pas cu pas și demonstrarea curselor de date. Include import/export JSON. Se deschide direct în browser, fără server sau dependențe; dimensiunile vizuale sunt 1–12 pe axă, valorile sunt întregi BigInt, cu mod uint64 sau exact. Este o simulare a distribuției lucrului, nu un benchmark de performanță.
- [Raportul cu rezultate și concluzii](results/study/report.md): date măsurate, tabele și grafice.
- [Prezentare HTML autonomă](results/study/dashboard.html): comparația platformelor și scalarea.
- [Date agregate CSV](results/study/summary.csv): medii, deviații, speedup și eficiență.
- [Grafice PNG/SVG](figures/study/): fișiere pentru prezentare/export.

## Compilare și prima rulare

Necesită GCC cu OpenMP și Python 3.10+. Colectarea benchmark-urilor folosește numai biblioteca standard Python; graficele necesită Matplotlib și NumPy.

```bash
cd HW2
make
./matmul --n 100 --m 200 --r 150 --variant parallel_i --budget 4
```

Programul generează A[n,m] și B[m,r], calculează C[n,r] și compară **toate elementele** cu o referință secvențială. Implicit execută o încălzire și cinci repetări; emite câte un obiect JSON pe linie, numai după verificarea rezultatului. O eroare de corectitudine produce cod de ieșire nenul.

```bash
./matmul --list
./matmul --help
./matmul --n 3 --m 7 --r 5 --variant collapse_ijk --budget 4 --repeats 1 --dump
```

`--dump` include A, B logică și C ca vectori pe linii și este limitat la 4096 elemente/matrice. Nu există dependență de fișiere externe de intrare; `--seed` permite regenerarea exactă a matricilor.

## Variante și evitarea curselor de date

Indicii rămân în ordinea i, j, k, cu k peste dimensiunea comună m. O funcție `dot()` conține bucla secvențială k în variantele care atribuie o celulă unui singur fir.

| Variantă CLI | Bucle paralele | Echipe cerute | Protecția rezultatului |
| --- | --- | --- | --- |
| `seq` | niciuna | 1 fir | referință secvențială |
| `parallel_i` | i | Ti | fiecare fir deține linii distincte |
| `parallel_j` | j, pentru fiecare i | Tj | celule distincte |
| `parallel_k` | k, pentru fiecare (i,j) | Tk | `reduction(+:sum)` |
| `collapse_ij` | i și j, `collapse(2)` | Ti | celule distincte |
| `collapse_jk` | j și k, `collapse(2)`, pentru fiecare i | Tj | `atomic update` pe C[i,j] |
| `collapse_ijk` | i, j și k, `collapse(3)` | Ti | `atomic update` pe C[i,j] |
| `nested_ij` | i, apoi echipe j | Ti × Tj | celule distincte |
| `nested_jk` | j, apoi echipe k | Tj × Tk | reducere k pentru fiecare celulă |
| `nested_ik` | i, apoi echipe k; j secvențial | Ti × Tk | reducere k pentru fiecare celulă |
| `nested_ijk` | i, apoi j, apoi k | Ti × Tj × Tk | reducere k pentru fiecare celulă |
| `hybrid_ij_k` (bonus) | `collapse(ij)`, apoi nested k | Ti × Tk | reducere k |
| `hybrid_i_jk` (bonus) | i, apoi nested `collapse(jk)` | Ti × Tj | `atomic update` |

Un `collapse` produce o singură echipă pentru spațiul aplatizat. Când acesta include k, contribuțiile către aceeași celulă trebuie sincronizate. `atomic` previne pierderea actualizărilor; nu elimină costul contendenței. Pentru k paralel separat, reducerea folosește sume private și scrie celula după bariera implicită. Indicii declarați în bucle sunt privați; matricile sunt partajate; A și B rămân nemodificate.

Nested parallelism este activat prin `omp_set_max_active_levels(3)`. Nu se folosește API-ul depreciat `omp_set_nested`. Echipele cerute sunt verificate printr-o probă separată, în afara intervalului măsurat; `team_min`, `team_max` și `thread_limit` expun eventuala serializare impusă de runtime. Proba nu este o măsurătoare a utilizării CPU și nici o garanție de simultaneitate la fiecare instrucțiune.

## Thread-uri și schedule pentru fiecare nivel

`--budget GP` împarte bugetul total între nivelurile variantei. Exemplu: GP=8 produce (2,2,2) la `nested_ijk` și (4,2) la o variantă cu două niveluri. La un singur nivel cere o echipă de 8 fire. Pentru GP prim, factorii interiori sunt 1: această limitare a factorizării este intenționată și este vizibilă în date.

`--threads I,J,K` configurează explicit dimensiunea echipei fiecărei bucle și este incompatibil cu `--budget`. Firele nivelurilor secvențiale nu intră în GP; pentru collapse se folosește dimensiunea primei bucle din grup. Astfel, exemplul următor cere GP=8:

```bash
OMP_WAIT_POLICY=PASSIVE ./matmul --n 30 --m 200 --r 40 \
  --variant nested_ijk --threads 2,2,2 \
  --schedule-i static --schedule-j dynamic:4 --schedule-k guided:8
```

`--schedule` stabilește politica pentru toate buclele, iar `--schedule-i`, `--schedule-j`, `--schedule-k` o suprascriu independent. Sunt acceptate `static`, `dynamic`, `guided` și un chunk pozitiv opțional, de exemplu `static:8`. `static` fără chunk folosește împărțirea implicită a runtime-ului; dynamic/guided fără chunk folosesc 1. Într-un collapse se aplică schedule-ul primei bucle din grup. Fiecare task setează `omp_set_schedule` înainte de a crea echipa următoare, iar buclele folosesc `schedule(runtime)`.

```bash
./matmul --n 100 --m 100 --r 100 --variant nested_ij --threads 2,4,1
./matmul --n 100 --m 100 --r 100 --variant collapse_ij --budget 4 --schedule dynamic:8
```

## Tip numeric, intrări și layout

Toate matricile folosesc `uint64_t`. Adunările și înmulțirile au semantica definită de C **modulo 2⁶⁴**. Alegerea evită overflow-ul semnat nedefinit în experimentul cu valori maxime; nu oferă precizie arbitrară. Pentru intrările aleatoare mici, rezultatele încap în 64 de biți și coincid cu produsul matematic obișnuit.

| `--dataset` | Valori A și B | Rezultat |
| --- | --- | --- |
| `random` | pseudoaleator în [0,100], SplitMix64 | exact pentru dimensiunile studiate |
| `zeros` | numai 0; cazul „best” din enunț | toate celulele 0 |
| `ones` | numai 1; alternativă pentru „best” | toate celulele m |
| `max` | numai UINT64_MAX; cazul „worst” pentru tipul ales | toate celulele m modulo 2⁶⁴ |
| `random_full` | pseudoaleator pe 64 de biți | produs modulo 2⁶⁴; folosit și la teste |

Aceleași seed-uri produc exact aceleași intrări pe ambele calculatoare și în ambele layout-uri. Seed-uri distincte dau perechi distincte. Programul nu sare peste operații pentru zero sau unu; „best” și „worst” desemnează valorile, fără să impună ordinea timpilor.

`--layout row` stochează B pe linii. `--layout transposed` stochează B[k,j] la poziția j*m+k, astfel încât ambii operanzi ai produsului scalar sunt citiți consecutiv. Aranjarea memoriei este realizată înaintea măsurării; comparăm costul nucleului, nu timpul total incluzând o transpunere separată. Referința de verificare folosește întotdeauna B logică pe linii.

## Ce conține timpul raportat

`seconds` măsoară exclusiv apelul variantei de înmulțire, cu `omp_get_wtime()`. Include operațiile aritmetice, accesul la matrici, crearea echipelor, scheduling-ul, reducerile, atomicele și barierele. Exclude generarea intrărilor, alocarea, aranjarea lui B, resetarea lui C, proba de thread-uri, calculul referinței și verificarea rezultatului.

`reference_seconds` este timpul referinței independente folosite la verificare. Studiul calculează speedup folosind **rulări `seq` separate, cu aceleași repetări și încălzire**, pentru fiecare campanie, formă, intrare și layout. Numărul de page faults din apelul nucleului este în `minor_faults`/`major_faults`.

## Benchmark-uri, raport și teste

Din `HW2`:

```bash
# Studiul complet al factorilor, pe cele două calculatoare, consecutiv:
python3 benchmark.py --hosts local HP-Laptop --collect-only

# Regenerarea raportului și a graficelor din datele existente:
python3 analyze.py --input results/study
# Dacă Matplotlib/NumPy lipsesc:
uv run --with matplotlib --with numpy python analyze.py --input results/study

# Verificare rapidă a colectării, fără a modifica datele studiului:
python3 benchmark.py --profile smoke --collect-only --output /tmp/hw2-smoke

# Corectitudine C, planificare experimente, agregare și timeout-uri:
make test
# Modelul vizual: acoperirea tuturor produselor, schedule-uri, nested, overflow,
# race-uri și compararea generatorului/rezultatelor cu programul C (necesită Node 18+):
make test-visualizer
# Opțional: interacțiuni reale în Chrome, layout desktop/mobil, teme light/dark:
uv run --with playwright python tests/browser_visualizer.py
# Repetarea testelor C cu UndefinedBehaviorSanitizer:
make debug
MATMUL_EXE="$PWD/matmul_debug" python3 -m unittest discover -s tests -p test_matmul.py -v
```

`--hosts` colectează pe fiecare calculator separat și consecutiv. Pentru un host SSH, scriptul folosește autentificarea existentă, copiază sursele într-un director temporar, compilează local, rulează benchmark-ul acolo și aduce datele înapoi. Nu necesită NFS sau instalarea Matplotlib pe mașina remote. Dacă apare o eroare, afișează directorul remote păstrat pentru recuperare.

Rezultatele se reiau automat din jurnalul local numai când sursele, planul, setările și mediul OpenMP coincid. Pentru o campanie nouă sau o sursă modificată, folosește alt `--output`. Instrucțiuni pentru grile personalizate, timeout-uri și limitele interpretării sunt în [EXPERIMENTS.md](EXPERIMENTS.md).

## Cod C urmărit în vizualizare

Pagina [interactive.html](interactive.html) folosește întregul spațiu al ferestrei, cu setările în stânga și taburi pentru matrici, execuție, inspectarea unei celule și thread-uri/memorie. Play/Next și timeline-ul rămân vizibile în fiecare tab; schimbarea tabului păstrează execuția și selecția. Pe ecrane mici, butonul Settings deschide panoul lateral. Full screen activează modul ecran complet al browserului, iar Help text afișează explicațiile setărilor. Secțiunea Others este inițial închisă și grupează limita nivelurilor nested, seed-ul de dispatch, aritmetica, layout-ul B și demonstrația de race; strategia, thread-urile și scheduling-ul rămân la vedere.

Tabul Follow the work afișează funcția C a strategiei alese și, unde este folosit, helper-ul `dot()` cu bucla k. Play/Next actualizează i/j/k, slice-ul k și instrucțiunea produsului, în culoarea thread-ului urmărit. Lista thread-urilor active arată separat indicii concurenți; selectarea unei celule permite inspectarea unui produs viitor sau deja finalizat. Codul și matricea C au zone de derulare proprii pentru exemple mari, fără a prelungi întreaga pagină.

Fragmentele sunt copii exacte din `matmul.c`, cu numerele de linie. Evidențierea urmărește operațiile modelului, fără a simula separat fiecare instrucțiune C, verificare de buclă sau join. În modul race, codul sigur rămâne referința, iar înlocuirea nesincronizată este afișată separat. Matricea de progres prezintă și sumele private/locale conceptuale, înainte ca programul C să scrie valoarea finală a celulei.

După modificarea sursei C, actualizează fragmentele incluse în HTML:

```bash
python3 sync_visualizer_source.py
make test-visualizer
```

Testele verifică și hash-ul sursei, identitatea fragmentelor, avansarea k/j, contextele simultane și distincția dintre execuție și inspecție.

[Toate temele](../README.md)
