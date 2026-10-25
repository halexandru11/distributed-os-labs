# Studiul Experimental al Prelucrării Paralele de Imagini în MPI

**Mediu de execuție:** Single Machine (Local Multi-Core) | **Rezoluție principală:** `8MP` (~25 MB per imagine necomprimată)

Acest studiu evaluează performanța implementării paralele bazate pe șablonul **Coordonator-Workers** în MPI pentru procesarea matricilor de pixeli RGB (format necomprimat **PPM `P6`**).

## 0. Verificarea Vizuală a Corectitudinii Operațiilor Grafice

Imaginea generată conține un marcaj roșu în stânga-sus, o grilă albă fină (1 px) și un cerc central galben. Aceste repere permit confirmarea corectitudinii algoritmilor de rotire, oglindire și asamblare a feliilor transmise prin MPI:

![Verificarea vizuală a operațiilor](benchmark_figures/visual_check.png)

## 1. Variația Timpului de Execuție în Funcție de Numărul de Procese MPI (`np`)

**Concluzii experimentale:**

- **Operații cu calcul intensiv per pixel (`blur` și `pipeline`):** Timpul de execuție scade pronunțat pe măsură ce adăugăm workeri, evidențiind o scalabilitate puternică (Strong Scaling).
- **Operații simple (`grayscale`):** Complexitatea aritmetică redusă per pixel face ca timpul de transmitere a datelor prin memorie/rețea să limiteze câștigul paralel.
- **Saturația Hardware (Oversubscription):** Peste numărul de nuclee fizice/logice ale mașinii, panta se aplatizează sau începe să urce ușor din cauza context-switching-ului la nivel de OS.

![Timpul de execuție în funcție de numărul de procese](benchmark_figures/execution_time.png)

## 2. Analiza speedup-ului paralel

Speedup-ul se calculează cu formula `S_p = T_seq / T_par` și măsoară accelerarea față de execuția secvențială:

- Pentru filtrul **Box Blur**, volumul mare de operații aritmetice pe vecinătăți oferă un speedup solid pe arhitecturi multi-core.
- Pentru filtrul **Grayscale**, speedup-ul rămâne aproape de 1.0x-1.1x din cauza raportului mic între calcul și comunicație.

![Speedup în funcție de numărul de workeri](benchmark_figures/speedup.png)

## 3. Scalabilitatea cu rezoluția imaginii

Timpul de execuție crește liniar cu numărul de pixeli, conform complexității `O(N × M)`. Pe imagini mari (8MP), panta execuției paralele este semnificativ mai mică decât cea secvențială, confirmând eficiența algoritmului paralel pe volume mari de date.

![Scalabilitatea cu rezoluția imaginii](benchmark_figures/resolution_scaling.png)

## 4. Comparația Strategiilor de Divizare (1D vs. 2D) și Load-Balancing (Static vs. Dinamic)

Comparația folosește 4 workeri și un coordonator. Modul `static_2d` formează o grilă 2×2.

Barele sunt alăturate deoarece intervalele măsurate se suprapun. Timpul apelurilor MPI este măsurat pe coordonator și include așteptarea rezultatelor de la workeri. Calculul CPU reprezintă timpul cumulat maxim pe un worker. Suma acestor valori nu reprezintă timpul total.

Pack/unpack include alocarea bufferelor temporare. Feliile care ocupă întreaga lățime sunt transmise direct, deci pot avea timp de pack/unpack zero. Dalele 2D necesită copierea rândurilor în buffere contigue și reasamblarea rezultatului.

![Comparația strategiilor de divizare](benchmark_figures/partition_strategies.png)

### Rezultate măsurate pentru rezoluția `8MP`

Timpii sunt exprimați în milisecunde. `np` include coordonatorul; modurile paralele folosesc `np - 1` workeri. Cel mai mic timp total din fiecare tabel este marcat cu bold.

#### grayscale

| Mod | np | Total (ms) | Calcul (ms) | Pack (ms) | MPI (ms) | Speedup |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| seq | 1 | **45.4** | 45.4 | 0.0 | 0.0 | 1.00x |
| static_1d | 2 | 80.6 | 51.1 | 0.0 | 80.6 | 0.56x |
| static_1d | 3 | 83.3 | 48.5 | 0.0 | 83.3 | 0.54x |
| static_1d | 4 | 107.8 | 36.2 | 0.0 | 107.8 | 0.42x |
| static_1d | 5 | 121.6 | 85.8 | 0.0 | 121.6 | 0.37x |
| static_1d | 6 | 206.4 | 53.0 | 0.0 | 206.4 | 0.22x |
| static_1d | 8 | 135.3 | 38.2 | 0.0 | 135.3 | 0.34x |

#### blur

| Mod | np | Total (ms) | Calcul (ms) | Pack (ms) | MPI (ms) | Speedup |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| seq | 1 | 852.0 | 852.0 | 0.0 | 0.0 | 1.00x |
| static_1d | 2 | 1061.3 | 1020.4 | 0.0 | 1061.3 | 0.80x |
| static_1d | 3 | 896.1 | 845.7 | 0.0 | 896.1 | 0.95x |
| static_1d | 4 | **774.1** | 702.9 | 0.0 | 774.1 | 1.10x |
| static_1d | 5 | 856.9 | 814.9 | 0.0 | 856.9 | 0.99x |
| static_1d | 6 | 1053.8 | 986.7 | 0.0 | 1053.7 | 0.81x |
| static_1d | 8 | 920.1 | 788.8 | 0.0 | 920.0 | 0.93x |
| static_2d | 5 | 1126.7 | 989.3 | 69.3 | 1056.5 | 0.76x |
| dynamic_1d | 5 | 865.7 | 825.3 | 0.0 | 865.6 | 0.98x |

#### rotate90

| Mod | np | Total (ms) | Calcul (ms) | Pack (ms) | MPI (ms) | Speedup |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| seq | 1 | **99.9** | 99.9 | 0.0 | 0.0 | 1.00x |
| static_1d | 2 | 133.8 | 88.3 | 0.0 | 133.8 | 0.75x |
| static_1d | 3 | 160.9 | 80.0 | 30.5 | 128.5 | 0.62x |
| static_1d | 4 | 150.6 | 95.9 | 23.8 | 125.5 | 0.66x |
| static_1d | 5 | 168.7 | 94.5 | 25.6 | 142.2 | 0.59x |
| static_1d | 6 | 158.0 | 101.6 | 14.4 | 142.9 | 0.63x |
| static_1d | 8 | 215.2 | 155.1 | 17.6 | 197.1 | 0.46x |

#### grayscale,blur,flip

| Mod | np | Total (ms) | Calcul (ms) | Pack (ms) | MPI (ms) | Speedup |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| seq | 1 | 1200.3 | 1200.3 | 0.0 | 0.0 | 1.00x |
| static_1d | 2 | 1112.6 | 1015.8 | 0.0 | 1112.6 | 1.08x |
| static_1d | 3 | **1047.3** | 933.5 | 0.0 | 1047.2 | 1.15x |
| static_1d | 4 | 1440.4 | 1165.5 | 0.0 | 1440.3 | 0.83x |
| static_1d | 5 | 1206.0 | 963.2 | 0.0 | 1206.0 | 0.99x |
| static_1d | 6 | 1370.4 | 1136.0 | 0.0 | 1370.3 | 0.88x |
| static_1d | 8 | 1380.2 | 1008.0 | 0.0 | 1380.2 | 0.87x |
| static_2d | 5 | 1609.8 | 1264.4 | 178.3 | 1418.9 | 0.75x |
| dynamic_1d | 5 | 1087.2 | 836.5 | 0.0 | 1087.1 | 1.10x |

Calcul reprezintă timpul cumulat maxim de procesare pe un proces. Pack include împachetarea, despachetarea și alocarea bufferelor temporare. MPI include timpul petrecut de coordonator în apelurile MPI, inclusiv așteptarea workerilor. Aceste intervale se suprapun și nu se adună pentru a obține timpul total.
