# MPI Image Processing: comparație între rezoluții

Acest README sintetizează suita de benchmark-uri MPI pentru prelucrarea imaginilor PPM. Studiul compară două calculatoare eterogene conectate prin Ethernet direct:

| Calculator | Procesor | Resurse relevante |
| --- | --- | --- |
| HP-Laptop | Intel i7-7500U | 2 nuclee, 4 fire hardware |
| Victus | Intel i5-12500H | 12 nuclee, 16 procesoare logice: 4 P-core și 8 E-core |

Am folosit Open MPI 4.1.6, compilare `mpicc -O3 -Wall` și `--bind-to none`. Coordonatorul este un proces MPI suplimentar față de numărul de workeri. Astfel, `8` workeri Victus înseamnă **8 workeri plus rank 0 coordonator**, adică 9 procese MPI în total.

## Rezumatul experimentului

Au fost colectate **3.120 de rulări**: 320 de configurații la fiecare dintre rezoluțiile 1.5MP, 4MP și 8MP, cu 3 repetări, plus 80 de configurații la 64MP, tot cu 3 repetări. Toate rezultatele raportate aici au fost măsurate prin cablu Ethernet; testele Wi-Fi au fost abandonate deoarece latența era prea mare.

Operațiile sunt `grayscale`, `blur` 9x9, `rotate90` și pipeline-ul `grayscale,blur,flip`. Strategiile sunt `static_1d`, `static_2d` și `dynamic_1d`. Timpul măsurat exclude citirea imaginii, scrierea rezultatului, lansarea MPI și verificarea pixelilor. Prima repetare a fiecărei configurații paralele a fost verificată pixel cu pixel față de referința secvențială; toate configurațiile au fost corecte.

Principalele concluzii:

- Pipeline-ul atinge aproximativ **60 MP/s** pe Victus cu 8 workeri și `dynamic_1d`, de la 1.5MP până la 64MP.
- `blur` este operația cu intensitatea de calcul suficientă pentru a scala: speedup-ul Victus ajunge la `6.76x` la 8MP.
- `grayscale` și `rotate90` sunt limitate de transferuri, memorie și coordonarea MPI; după aproximativ 5-7 workeri, adăugarea de procese poate să nu mai ajute.
- Workerii HP-Laptop adaugă penalizare în configurațiile mici și eterogene. Penalizarea se reduce pentru sarcini mai grele, dar Victus singur rămâne mai rapid în toate comparațiile principale.

## 1. Scalarea pipeline-ului

Pipeline-ul `grayscale,blur,flip` este singura operație măsurată la toate cele patru rezoluții. De la 1.44 milioane de pixeli la aproximativ 64 milioane de pixeli, volumul crește de **44.4x**.

| Rezoluție | Dimensiune | Secvențial HP (ms) | Secvențial Victus (ms) | Cel mai bun timp paralel (ms) | Configurație optimă | Speedup maxim pe Victus | Cel mai bun timp mixt 2 HP + 8 V |
| --- | ---: | ---: | ---: | ---: | --- | ---: | ---: |
| 1.5MP | 1600x900 | 152.94 | 118.96 | **23.18** | `dynamic_1d` (0 HP, 8 V) | **5.13x** | 82.36 ms (`static_1d`) |
| 4MP | 2400x1600 | 347.42 | 313.91 | **66.47** | `dynamic_1d` (0 HP, 8 V) | **4.72x** | 182.12 ms (`static_1d`) |
| 8MP | 3840x2160 | 734.25 | 673.32 | **136.92** | `dynamic_1d` (0 HP, 8 V) | **4.92x** | 286.46 ms (`dynamic_1d`) |
| 64MP | 10667x6000 | 5615.36 | 5256.82 | **1043.26** | `dynamic_1d` (0 HP, 8 V) | **5.04x** | 2092.94 ms (`dynamic_1d`) |

Speedup-ul de vârf rămâne între `4.72x` și `5.13x`, chiar dacă rezoluția crește de peste 40 de ori. Configurația optimă este de fiecare dată `dynamic_1d` cu 8 workeri Victus.

În configurația mixtă cu 2 HP și 8 Victus, `static_1d` câștigă la 1.5MP și 4MP: sarcinile sunt suficient de rapide încât mesajele suplimentare ale planificării dinamice să coste mai mult decât echilibrarea obținută. La 8MP și 64MP, fiecare task conține mai mult calcul, iar `dynamic_1d` poate amortiza costul coordonării și devine mai rapid.

### Throughput normalizat

Pentru `dynamic_1d`, 8 workeri Victus:

| Rezoluție | Calcul MP/s |
| --- | ---: |
| 1.5MP | 62.1 |
| 4MP | 57.8 |
| 8MP | 60.6 |
| 64MP | 61.3 |

Throughput-ul este stabil, în jur de **60 MP/s**. Aceasta este o comparație mai utilă între rezoluții decât timpul absolut, deoarece normalizează volumul de pixeli procesat.

## 2. Operații cu intensități diferite

Rezultatele de mai jos folosesc cea mai bună configurație Victus-only observată la fiecare rezoluție. `V` înseamnă worker Victus; coordonatorul este inclus separat în numărul total de procese MPI.

| Operație | Profil | 1.5MP: speedup / workeri | 4MP: speedup / workeri | 8MP: speedup / workeri | Comportament la scalare |
| --- | --- | ---: | ---: | ---: | --- |
| `grayscale` | Memorie/comunicație | `1.28x` / 6 V, `dynamic_1d` | `1.11x` / 5 V, `static_2d` | `1.21x` / 5 V, `static_1d` | Plafonare severă în jur de `1.2x`; peste 5-6 workeri timpul poate crește. |
| `rotate90` | Memorie/pack-unpack | `1.56x` / 7 V, `dynamic_1d` | `1.22x` / 3 V, `dynamic_1d` | `1.44x` / 5 V, `dynamic_1d` | Platou timpuriu; transformarea necesită extragerea și reasamblarea regiunilor. |
| `blur` 9x9 | Intensiv computațional | `5.24x` / 7 V, `dynamic_1d` | `5.94x` / 8 V, `dynamic_1d` | `6.76x` / 8 V, `dynamic_1d` | Scalare bună; 81 de citiri/medieri pe pixel oferă suficient calcul per task. |

`grayscale` și `rotate90` fac puțin calcul per pixel. La multe procese, economisirea calculului este prea mică pentru a compensa mesajele MPI, alocarea bufferelor, copierea datelor și sincronizarea. `blur` repetă vecinătatea 9x9 pentru fiecare pixel și are un raport calcul/comunicație mai favorabil.

Speedup-urile din grafice folosesc referințe secvențiale diferite: HP-Laptop în panoul HP-only și Victus în celelalte panouri. Pentru comparații între configurații eterogene, timpul total este indicatorul corect, nu speedup-ul luat izolat.

## 3. Penalizarea clusterului eterogen

Pentru a cuantifica efectul workerilor HP-Laptop, definim:

$$
R_{mix} = \frac{T_{2HP+4V}}{T_{0HP+4V}}
$$

Valorile următoare sunt comparații reprezentative din datele agregate; strategiile sunt cele mai bune pentru configurațiile raportate în studiile respective.

| Rezoluție și operație | 0 HP + 4 V | 2 HP + 4 V | Penalizare $R_{mix}$ |
| --- | ---: | ---: | ---: |
| 1.5MP `grayscale` | 4.68 ms | 47.12 ms | **10.0x** |
| 4MP `grayscale` | 12.53 ms | 86.19 ms | **6.9x** |
| 1.5MP `blur` | 30.95 ms | 56.81 ms | **1.84x** |
| 8MP `blur` | 174.58 ms | 182.63 ms | **1.05x** |
| 64MP pipeline | 1625.10 ms | 3880.83 ms | **2.39x** |

La operații rapide, latența Ethernet și diferența de viteză dintre calculatoare domină. La `blur` 8MP, diferența ajunge aproape de break-even: calculul suficient de mare amortizează overhead-ul. La pipeline-ul 64MP, 8 workeri Victus reduc timpul mixt la 2092.94 ms, dar configurația cu 4 Victus și 2 HP rămâne mult mai lentă decât Victus-only.

`dynamic_1d` poate limita dezechilibrul prin trimiterea următorului task către primul worker disponibil, dar nu elimină transferurile dintre calculatoare. În plus, un worker HP lent poate ține coordonatorul ocupat cu date care nu ar fi fost necesare într-o configurație Victus-only.

## 4. Geometria partiționării și strategiile

### `static_1d`

Împarte imaginea în benzi orizontale pe toată lățimea. Aceste regiuni sunt ușor de copiat și, pentru multe cazuri, pot fi trimise direct fără pack/unpack suplimentar. Este eficient pentru taskuri mici și omogene, motiv pentru care câștigă în unele configurații mixte de 1.5MP și 4MP.

### `static_2d` și efectul de tip sawtooth

Implementarea caută cea mai apropiată factorizare de un pătrat:

- 3, 5 și 7 workeri: grilă cu o singură coloană, echivalentă geometric cu benzi orizontale;
- 4, 6 și 8 workeri: grilă cu 2 coloane, deci apar blocuri înguste și necontigue în imagine.

Pentru blocurile care nu ocupă toată lățimea, coordonatorul trebuie să facă `pack_submatrix` și `unpack_submatrix`. La 64MP pipeline pe Victus, `static_2d` crește de la `2125.5 ms` cu 3 workeri la `2224.6 ms` cu 4 workeri și de la `1185.4 ms` cu 7 workeri la `1324.6 ms` cu 8 workeri. Numărul mai mare de workeri nu înseamnă automat mai puțin timp atunci când se schimbă geometria și apare copierea datelor.

### `dynamic_1d`

Crează până la 6 taskuri per worker și redistribuie un task când un worker termină. Pentru 8 workeri, o etapă poate ajunge la 48 de taskuri în loc de 8. Strategia este robustă pe Victus și pentru sarcini grele sau calculatoare de viteze diferite, deoarece nu presupune că fiecare worker termină aceeași cantitate de lucru în același timp.

Achilles heel-ul este costul mesajelor: pe pipeline-uri mici și mixte, 48 de taskuri per etapă pot costa mai mult decât echilibrarea obținută. De aceea `static_1d` este mai bună în unele configurații de 1.5MP și 4MP, în timp ce `dynamic_1d` domină Victus-only și workload-urile mai grele.

## 5. Stabilitate și limite experimentale

Fiecare configurație are numai trei repetări. Curbele de timp folosesc media și abaterea standard; benzile nu sunt intervale de încredere. Graficele de speedup și strategiile afișează medii fără benzi.

Coeficientul maxim de variație relativă raportat în fiecare studiu scade de la `78.5%` la 1.5MP, la `54.1%` la 4MP, `38.1%` la 8MP și `39.1%` la 64MP. Rulările mici sunt sensibile la planificarea sistemului, frecvența procesorului și latența Ethernet. Configurațiile au fost executate succesiv, fără randomizare și fără măsurători separate de trafic de rețea, presiune pe memorie sau frecvență CPU.

La 64MP, HP-Laptop este clar saturat: referința secvențială este `5615.36 ms`, în timp ce configurațiile paralele HP-only ajung la `7645.48 ms` (`dynamic_1d`, 1 worker) și `10829.42 ms` (`static_2d`, 2 workeri). Coordonatorul și workerii concurează pentru doar 2 nuclee fizice și pentru memoria necesară copierii unor buffer-e RGB de aproximativ 192 MB.

Prin urmare, rezultatele susțin concluzii despre tendințe și costuri de sistem, dar nu despre o ordine universală a strategiilor. Pentru confirmare ar fi utile mai multe repetări, ordine randomizată, binding explicit, măsurători de bandwidth/CPU frequency și separarea timpilor de rețea de așteptarea calculului.

## Reproducere și date

Implementarea, benchmark-urile și testele sunt documentate în [HW1/README.md](HW1/README.md). Pentru testarea helper-elor Python:

```bash
cd HW1
uv run --with numpy --with matplotlib python -m unittest -v test_benchmark.py test_benchmark_two_machines.py
```

Rularea curentă a scriptului de două calculatoare este configurată pentru 64MP și pipeline-ul `grayscale,blur,flip`:

```bash
cd HW1
uv run --with numpy --with matplotlib python benchmark_two_machines_small.py
uv run --with numpy --with matplotlib python benchmark_two_machines_small.py --plot-only
```

Rapoarte detaliate:

- [1.5MP](HW1/experimental_study_two_machines_1.5MP.md)
- [4MP](HW1/experimental_study_two_machines_4MP.md)
- [8MP](HW1/experimental_study_two_machines_8MP.md)
- [64MP](HW1/experimental_study_two_machines_64MP.md)

Datele agregate și brute se află în `HW1/benchmark_two_machines/<rezoluție>/results.csv`, `runs.csv` și `runs.jsonl`. Rapoartele generate pot conține text metodologic mai vechi; CSV-urile și constantele din script sunt sursa de adevăr pentru configurația executată efectiv.
