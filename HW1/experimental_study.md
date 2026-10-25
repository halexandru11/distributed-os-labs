# Studiul experimental al prelucrării paralele de imagini în MPI

## Metodologie

Mediu: `local`. Fiecare configurație rulează de 5 ori. Liniile din graficele timpului arată media, iar benzile semitransparente arată media ± abaterea standard între rulări. Speedup-ul folosește raportul mediilor `T_seq / T_par`, iar eficiența este `speedup / număr_workeri`. Coordonatorul nu procesează pixeli în modurile paralele. Aceste valori descriu rularea curentă și pot varia cu încărcarea sistemului.

Toate cele patru operații folosesc aceleași configurații. Pe imaginea `8MP` testăm cele trei strategii cu `np` în [2, 3, 4, 5, 6, 8, 9]. Pentru variația rezoluției fixăm `np=5` și folosim imaginile `small`: 256×256, `1.5MP`: 1600×900, `4MP`: 2400×1600, `8MP`: 3840×2160. Configurațiile comune celor două experimente sunt măsurate o singură dată.

Timpul total exclude citirea și scrierea imaginilor, pornirea MPI, oprirea workerilor și reducerea finală a timpilor. Prima repetare produce și o imagine pentru verificare; scrierea și compararea pixelilor au loc în afara intervalelor măsurate. Măsurătorile brute sunt în [benchmark_runs.csv](benchmark_runs.csv), iar mediile și verificările în [benchmark_results.csv](benchmark_results.csv).

## 1. Cum influențează numărul de workeri timpul?

Rezoluția este fixată la `8MP`. Fiecare curbă reprezintă o strategie; linia întreruptă arată referința secvențială. Speedup peste 1 indică un timp mediu mai mic decât cel secvențial. Eficiența de 100% este reperul ideal per worker.

Grilele `static_2d`, rânduri × coloane: `np=2` → 1×1; `np=3` → 2×1; `np=4` → 3×1; `np=5` → 2×2; `np=6` → 5×1; `np=8` → 7×1; `np=9` → 4×2. O singură coloană înseamnă felii pe întreaga lățime a rezultatului.

![Timp total](benchmark_figures/execution_time.png)

![Speedup](benchmark_figures/speedup.png)

![Eficiență](benchmark_figures/efficiency.png)

Pentru `grayscale`, cel mai mic timp mediu măsurat este 42.7 ms cu `seq`, `np=1`. Speedup-ul acestei configurații este 1.00×.

Pentru `blur`, cel mai mic timp mediu măsurat este 631.9 ms cu `dynamic_1d`, `np=9`. Speedup-ul acestei configurații este 1.38×.

Pentru `rotate90`, cel mai mic timp mediu măsurat este 109.1 ms cu `seq`, `np=1`. Speedup-ul acestei configurații este 1.00×.

Pentru `grayscale,blur,flip`, cel mai mic timp mediu măsurat este 819.9 ms cu `dynamic_1d`, `np=6`. Speedup-ul acestei configurații este 1.18×.

## 2. De la ce dimensiune merită paralelizarea?

Fixăm `np=5` pentru toate strategiile paralele și variem numărul de pixeli. Axa dimensiunii este logaritmică. Pragurile de mai jos sunt cele mai mici dimensiuni testate cu speedup peste 1, nu praguri exacte sau garanții pentru toate imaginile mai mari.

- `grayscale`, `static_1d`: primul câștig la `small`, 1.10×.

- `grayscale`, `static_2d`: niciun câștig la dimensiunile testate.

- `grayscale`, `dynamic_1d`: niciun câștig la dimensiunile testate.

- `blur`, `static_1d`: primul câștig la `small`, 1.01×.

- `blur`, `static_2d`: primul câștig la `small`, 1.82×.

- `blur`, `dynamic_1d`: primul câștig la `small`, 1.34×.

- `rotate90`, `static_1d`: niciun câștig la dimensiunile testate.

- `rotate90`, `static_2d`: niciun câștig la dimensiunile testate.

- `rotate90`, `dynamic_1d`: niciun câștig la dimensiunile testate.

- `grayscale,blur,flip`, `static_1d`: primul câștig la `small`, 1.23×.

- `grayscale,blur,flip`, `static_2d`: primul câștig la `small`, 2.07×.

- `grayscale,blur,flip`, `dynamic_1d`: primul câștig la `4MP`, 1.80×.

![Variația cu dimensiunea imaginii](benchmark_figures/resolution_scaling.png)

## 3. Cum se compară timpii coordonatorului și workerilor?

Comparăm toate operațiile la `8MP` și `np=5`. Fiecare strategie are două coloane, C pentru coordonator și W pentru worker. Coloana C împarte timpul total în pack/unpack, alte operații locale și comunicație și așteptare MPI. Pack/unpack include alocările bufferelor temporare. Alte operații locale reprezintă restul calculat ca `total - MPI - pack/unpack`; include pregătirea și planificarea taskurilor, administrarea memoriei din afara pack/unpack și costul instrumentării. Transmiterea și colectarea prin apeluri MPI intră în segmentul de comunicație și așteptare MPI, care nu reprezintă exclusiv timp inactiv. Coloana W arată media maximului timpului cumulat de calcul pe un worker, pentru fiecare rulare. Nu este suma timpilor tuturor workerilor și nu include așteptarea sau transferurile lor. Coloanele C și W se suprapun în timp și nu se adună. Împărțirea arată cât timp ocupă munca locală, dar nu dovedește singură că mutarea pack/unpack ar reduce timpul total.

Pentru `grayscale`, la `np=5`, strategia cu timpul mediu minim este `dynamic_1d`, 103.4 ms.

Pentru `blur`, la `np=5`, strategia cu timpul mediu minim este `dynamic_1d`, 777.9 ms.

Pentru `rotate90`, la `np=5`, strategia cu timpul mediu minim este `dynamic_1d`, 120.8 ms.

Pentru `grayscale,blur,flip`, la `np=5`, strategia cu timpul mediu minim este `dynamic_1d`, 952.3 ms.

![Timpii coordonatorului și timpul de calcul al workerului](benchmark_figures/partition_strategies.png)

## 4. Rezultatul paralel este corect?

Am comparat toți pixelii primei repetări din fiecare dintre cele 120 configurații paralele cu rezultatul secvențial pentru aceeași imagine și operație. Configurații cu diferențe: 0. Numărul maxim de pixeli diferiți este 0, iar diferența maximă pe canal este 0. Verificarea include dimensiunile rezultatului; o nepotrivire de dimensiuni oprește suita.

![Verificarea vizuală a operațiilor](benchmark_figures/visual_check.png)

## Date complete

<details>
<summary>Rezultate pentru small</summary>

### Rezultate măsurate pentru rezoluția `small`

Timpii sunt exprimați în milisecunde. `np` include coordonatorul; modurile paralele folosesc `np - 1` workeri. Total arată media ± abaterea standard. Cel mai mic timp mediu din fiecare tabel este marcat cu bold.

#### grayscale

| Mod | np | Total (ms) | Calcul (ms) | Pack (ms) | MPI (ms) | Speedup |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| seq | 1 | 1.9 ± 0.7 | 1.9 | 0.0 | 0.0 | 1.00x |
| static_1d | 5 | **1.7 ± 0.7** | 0.2 | 0.0 | 1.7 | 1.10x |
| static_2d | 5 | 5.1 ± 6.8 | 0.3 | 0.3 | 4.8 | 0.38x |
| dynamic_1d | 5 | 13.9 ± 22.3 | 0.2 | 0.0 | 13.9 | 0.14x |

#### blur

| Mod | np | Total (ms) | Calcul (ms) | Pack (ms) | MPI (ms) | Speedup |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| seq | 1 | 17.1 ± 7.5 | 17.1 | 0.0 | 0.0 | 1.00x |
| static_1d | 5 | 16.9 ± 6.6 | 12.4 | 0.0 | 16.9 | 1.01x |
| static_2d | 5 | **9.4 ± 1.6** | 5.0 | 0.2 | 9.1 | 1.82x |
| dynamic_1d | 5 | 12.7 ± 6.6 | 3.2 | 0.0 | 12.7 | 1.34x |

#### rotate90

| Mod | np | Total (ms) | Calcul (ms) | Pack (ms) | MPI (ms) | Speedup |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| seq | 1 | **1.4 ± 0.9** | 1.4 | 0.0 | 0.0 | 1.00x |
| static_1d | 5 | 2.0 ± 1.9 | 0.3 | 0.1 | 1.9 | 0.69x |
| static_2d | 5 | 10.3 ± 18.6 | 0.4 | 0.3 | 10.0 | 0.14x |
| dynamic_1d | 5 | 6.3 ± 9.2 | 0.2 | 0.1 | 6.1 | 0.22x |

#### grayscale,blur,flip

| Mod | np | Total (ms) | Calcul (ms) | Pack (ms) | MPI (ms) | Speedup |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| seq | 1 | 26.6 ± 21.3 | 26.6 | 0.0 | 0.0 | 1.00x |
| static_1d | 5 | 21.7 ± 6.1 | 6.6 | 0.0 | 21.7 | 1.23x |
| static_2d | 5 | **12.9 ± 7.3** | 4.9 | 0.7 | 12.1 | 2.07x |
| dynamic_1d | 5 | 34.7 ± 19.7 | 4.2 | 0.0 | 34.6 | 0.77x |

Calcul reprezintă timpul cumulat maxim de procesare pe un proces. Pack include împachetarea, despachetarea și alocarea bufferelor temporare. MPI include timpul petrecut de coordonator în apelurile MPI, inclusiv așteptarea workerilor. Aceste intervale se suprapun și nu se adună pentru a obține timpul total.

</details>

<details>
<summary>Rezultate pentru 1.5MP</summary>

### Rezultate măsurate pentru rezoluția `1.5MP`

Timpii sunt exprimați în milisecunde. `np` include coordonatorul; modurile paralele folosesc `np - 1` workeri. Total arată media ± abaterea standard. Cel mai mic timp mediu din fiecare tabel este marcat cu bold.

#### grayscale

| Mod | np | Total (ms) | Calcul (ms) | Pack (ms) | MPI (ms) | Speedup |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| seq | 1 | **11.0 ± 3.9** | 11.0 | 0.0 | 0.0 | 1.00x |
| static_1d | 5 | 23.5 ± 7.5 | 14.3 | 0.0 | 23.5 | 0.47x |
| static_2d | 5 | 23.2 ± 1.7 | 10.5 | 8.8 | 14.2 | 0.47x |
| dynamic_1d | 5 | 20.5 ± 3.0 | 7.8 | 0.0 | 20.4 | 0.54x |

#### blur

| Mod | np | Total (ms) | Calcul (ms) | Pack (ms) | MPI (ms) | Speedup |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| seq | 1 | 122.0 ± 6.7 | 122.0 | 0.0 | 0.0 | 1.00x |
| static_1d | 5 | **111.5 ± 35.4** | 103.4 | 0.0 | 111.5 | 1.09x |
| static_2d | 5 | 133.0 ± 19.2 | 124.5 | 6.2 | 126.5 | 0.92x |
| dynamic_1d | 5 | 134.7 ± 40.2 | 116.5 | 0.0 | 134.7 | 0.91x |

#### rotate90

| Mod | np | Total (ms) | Calcul (ms) | Pack (ms) | MPI (ms) | Speedup |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| seq | 1 | **21.7 ± 10.6** | 21.7 | 0.0 | 0.0 | 1.00x |
| static_1d | 5 | 25.8 ± 10.0 | 12.1 | 4.6 | 21.1 | 0.84x |
| static_2d | 5 | 29.8 ± 11.8 | 12.1 | 12.9 | 16.7 | 0.73x |
| dynamic_1d | 5 | 32.2 ± 12.5 | 8.8 | 2.7 | 29.3 | 0.67x |

#### grayscale,blur,flip

| Mod | np | Total (ms) | Calcul (ms) | Pack (ms) | MPI (ms) | Speedup |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| seq | 1 | **177.9 ± 7.9** | 177.9 | 0.0 | 0.0 | 1.00x |
| static_1d | 5 | 207.9 ± 29.6 | 182.0 | 0.0 | 207.9 | 0.86x |
| static_2d | 5 | 241.1 ± 32.4 | 190.7 | 25.7 | 215.2 | 0.74x |
| dynamic_1d | 5 | 221.0 ± 35.9 | 125.7 | 0.0 | 220.9 | 0.80x |

Calcul reprezintă timpul cumulat maxim de procesare pe un proces. Pack include împachetarea, despachetarea și alocarea bufferelor temporare. MPI include timpul petrecut de coordonator în apelurile MPI, inclusiv așteptarea workerilor. Aceste intervale se suprapun și nu se adună pentru a obține timpul total.

</details>

<details>
<summary>Rezultate pentru 4MP</summary>

### Rezultate măsurate pentru rezoluția `4MP`

Timpii sunt exprimați în milisecunde. `np` include coordonatorul; modurile paralele folosesc `np - 1` workeri. Total arată media ± abaterea standard. Cel mai mic timp mediu din fiecare tabel este marcat cu bold.

#### grayscale

| Mod | np | Total (ms) | Calcul (ms) | Pack (ms) | MPI (ms) | Speedup |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| seq | 1 | **49.0 ± 18.9** | 49.0 | 0.0 | 0.0 | 1.00x |
| static_1d | 5 | 51.4 ± 12.7 | 25.2 | 0.0 | 51.4 | 0.95x |
| static_2d | 5 | 71.7 ± 21.7 | 28.3 | 43.4 | 27.8 | 0.68x |
| dynamic_1d | 5 | 92.1 ± 44.7 | 29.1 | 0.0 | 92.1 | 0.53x |

#### blur

| Mod | np | Total (ms) | Calcul (ms) | Pack (ms) | MPI (ms) | Speedup |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| seq | 1 | 550.3 ± 63.7 | 550.3 | 0.0 | 0.0 | 1.00x |
| static_1d | 5 | 496.6 ± 134.4 | 477.0 | 0.0 | 496.6 | 1.11x |
| static_2d | 5 | 390.3 ± 56.5 | 350.9 | 31.2 | 358.6 | 1.41x |
| dynamic_1d | 5 | **343.2 ± 37.5** | 316.4 | 0.0 | 343.2 | 1.60x |

#### rotate90

| Mod | np | Total (ms) | Calcul (ms) | Pack (ms) | MPI (ms) | Speedup |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| seq | 1 | **59.7 ± 8.8** | 59.7 | 0.0 | 0.0 | 1.00x |
| static_1d | 5 | 95.3 ± 23.3 | 50.3 | 11.0 | 83.8 | 0.63x |
| static_2d | 5 | 76.6 ± 21.6 | 41.5 | 24.9 | 51.3 | 0.78x |
| dynamic_1d | 5 | 65.2 ± 10.8 | 27.8 | 5.6 | 59.5 | 0.92x |

#### grayscale,blur,flip

| Mod | np | Total (ms) | Calcul (ms) | Pack (ms) | MPI (ms) | Speedup |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| seq | 1 | 566.1 ± 23.6 | 566.1 | 0.0 | 0.0 | 1.00x |
| static_1d | 5 | 327.3 ± 77.7 | 274.8 | 0.0 | 327.2 | 1.73x |
| static_2d | 5 | 380.8 ± 113.4 | 316.1 | 51.4 | 328.8 | 1.49x |
| dynamic_1d | 5 | **315.3 ± 51.6** | 259.4 | 0.0 | 315.3 | 1.80x |

Calcul reprezintă timpul cumulat maxim de procesare pe un proces. Pack include împachetarea, despachetarea și alocarea bufferelor temporare. MPI include timpul petrecut de coordonator în apelurile MPI, inclusiv așteptarea workerilor. Aceste intervale se suprapun și nu se adună pentru a obține timpul total.

</details>

<details>
<summary>Rezultate pentru 8MP</summary>

### Rezultate măsurate pentru rezoluția `8MP`

Timpii sunt exprimați în milisecunde. `np` include coordonatorul; modurile paralele folosesc `np - 1` workeri. Total arată media ± abaterea standard. Cel mai mic timp mediu din fiecare tabel este marcat cu bold.

#### grayscale

| Mod | np | Total (ms) | Calcul (ms) | Pack (ms) | MPI (ms) | Speedup |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| seq | 1 | **42.7 ± 7.3** | 42.7 | 0.0 | 0.0 | 1.00x |
| static_1d | 2 | 85.5 ± 22.1 | 51.4 | 0.0 | 85.5 | 0.50x |
| static_1d | 3 | 106.7 ± 27.4 | 69.8 | 0.0 | 106.7 | 0.40x |
| static_1d | 4 | 126.8 ± 30.4 | 71.0 | 0.0 | 126.7 | 0.34x |
| static_1d | 5 | 111.8 ± 27.8 | 72.7 | 0.0 | 111.8 | 0.38x |
| static_1d | 6 | 123.8 ± 16.6 | 70.6 | 0.0 | 123.8 | 0.35x |
| static_1d | 8 | 119.2 ± 17.0 | 46.0 | 0.0 | 119.2 | 0.36x |
| static_1d | 9 | 122.8 ± 23.8 | 54.9 | 0.0 | 122.8 | 0.35x |
| static_2d | 2 | 124.2 ± 16.1 | 79.7 | 0.0 | 124.2 | 0.34x |
| static_2d | 3 | 104.1 ± 9.6 | 60.7 | 0.0 | 104.1 | 0.41x |
| static_2d | 4 | 157.0 ± 51.3 | 103.5 | 0.0 | 157.0 | 0.27x |
| static_2d | 5 | 159.5 ± 17.9 | 82.6 | 76.3 | 82.4 | 0.27x |
| static_2d | 6 | 97.8 ± 12.8 | 54.2 | 0.0 | 97.7 | 0.44x |
| static_2d | 8 | 126.0 ± 31.6 | 52.1 | 0.0 | 126.0 | 0.34x |
| static_2d | 9 | 125.6 ± 32.9 | 45.6 | 58.2 | 66.9 | 0.34x |
| dynamic_1d | 2 | 123.0 ± 13.8 | 78.9 | 0.0 | 123.0 | 0.35x |
| dynamic_1d | 3 | 108.3 ± 16.4 | 68.5 | 0.0 | 108.2 | 0.39x |
| dynamic_1d | 4 | 109.2 ± 15.2 | 58.7 | 0.0 | 109.2 | 0.39x |
| dynamic_1d | 5 | 103.4 ± 11.8 | 45.9 | 0.0 | 103.3 | 0.41x |
| dynamic_1d | 6 | 105.7 ± 9.2 | 51.2 | 0.0 | 105.7 | 0.40x |
| dynamic_1d | 8 | 123.9 ± 37.0 | 39.9 | 0.0 | 123.8 | 0.35x |
| dynamic_1d | 9 | 138.4 ± 91.3 | 30.0 | 0.0 | 138.3 | 0.31x |

#### blur

| Mod | np | Total (ms) | Calcul (ms) | Pack (ms) | MPI (ms) | Speedup |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| seq | 1 | 874.3 ± 11.4 | 874.3 | 0.0 | 0.0 | 1.00x |
| static_1d | 2 | 1686.5 ± 267.8 | 1644.9 | 0.0 | 1686.5 | 0.52x |
| static_1d | 3 | 1107.6 ± 148.5 | 1051.0 | 0.0 | 1107.6 | 0.79x |
| static_1d | 4 | 1106.6 ± 284.4 | 1064.8 | 0.0 | 1106.6 | 0.79x |
| static_1d | 5 | 968.5 ± 185.3 | 918.5 | 0.0 | 968.5 | 0.90x |
| static_1d | 6 | 864.2 ± 115.4 | 816.8 | 0.0 | 864.2 | 1.01x |
| static_1d | 8 | 797.5 ± 248.1 | 754.6 | 0.0 | 797.5 | 1.10x |
| static_1d | 9 | 863.9 ± 179.9 | 808.2 | 0.0 | 863.9 | 1.01x |
| static_2d | 2 | 1241.0 ± 120.3 | 1203.6 | 0.0 | 1241.0 | 0.70x |
| static_2d | 3 | 1012.0 ± 155.5 | 967.0 | 0.0 | 1012.0 | 0.86x |
| static_2d | 4 | 1086.5 ± 150.5 | 1031.6 | 0.0 | 1086.5 | 0.80x |
| static_2d | 5 | 982.8 ± 153.3 | 912.2 | 63.6 | 917.1 | 0.89x |
| static_2d | 6 | 837.7 ± 51.3 | 785.9 | 0.0 | 837.7 | 1.04x |
| static_2d | 8 | 870.0 ± 58.0 | 813.2 | 0.0 | 870.0 | 1.00x |
| static_2d | 9 | 737.9 ± 173.4 | 685.5 | 57.2 | 680.3 | 1.18x |
| dynamic_1d | 2 | 934.4 ± 46.5 | 899.1 | 0.0 | 934.4 | 0.94x |
| dynamic_1d | 3 | 1079.4 ± 152.4 | 1043.2 | 0.0 | 1079.4 | 0.81x |
| dynamic_1d | 4 | 892.3 ± 145.2 | 862.6 | 0.0 | 892.2 | 0.98x |
| dynamic_1d | 5 | 777.9 ± 168.5 | 747.3 | 0.0 | 777.8 | 1.12x |
| dynamic_1d | 6 | 713.3 ± 206.1 | 673.8 | 0.0 | 713.3 | 1.23x |
| dynamic_1d | 8 | 678.6 ± 105.9 | 616.4 | 0.0 | 678.6 | 1.29x |
| dynamic_1d | 9 | **631.9 ± 33.2** | 573.5 | 0.0 | 631.8 | 1.38x |

#### rotate90

| Mod | np | Total (ms) | Calcul (ms) | Pack (ms) | MPI (ms) | Speedup |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| seq | 1 | **109.1 ± 17.0** | 109.1 | 0.0 | 0.0 | 1.00x |
| static_1d | 2 | 150.0 ± 4.2 | 113.4 | 0.0 | 150.0 | 0.73x |
| static_1d | 3 | 171.5 ± 24.6 | 106.3 | 27.7 | 142.0 | 0.64x |
| static_1d | 4 | 199.9 ± 57.5 | 142.2 | 20.6 | 178.0 | 0.55x |
| static_1d | 5 | 216.4 ± 45.8 | 134.9 | 27.2 | 188.4 | 0.50x |
| static_1d | 6 | 151.6 ± 21.5 | 91.4 | 16.6 | 134.1 | 0.72x |
| static_1d | 8 | 161.4 ± 40.4 | 78.4 | 16.2 | 144.7 | 0.68x |
| static_1d | 9 | 168.9 ± 53.5 | 72.2 | 18.8 | 149.3 | 0.65x |
| static_2d | 2 | 158.5 ± 18.5 | 109.2 | 0.0 | 158.5 | 0.69x |
| static_2d | 3 | 163.4 ± 18.2 | 89.4 | 32.9 | 128.3 | 0.67x |
| static_2d | 4 | 185.0 ± 38.2 | 101.8 | 29.4 | 154.3 | 0.59x |
| static_2d | 5 | 163.0 ± 35.4 | 81.9 | 63.3 | 98.7 | 0.67x |
| static_2d | 6 | 157.1 ± 31.5 | 89.4 | 21.9 | 134.5 | 0.69x |
| static_2d | 8 | 178.8 ± 42.0 | 91.7 | 26.2 | 150.7 | 0.61x |
| static_2d | 9 | 146.5 ± 34.6 | 61.2 | 59.7 | 86.4 | 0.74x |
| dynamic_1d | 2 | 139.0 ± 5.4 | 87.4 | 14.1 | 124.3 | 0.79x |
| dynamic_1d | 3 | 121.0 ± 15.8 | 78.6 | 13.4 | 107.3 | 0.90x |
| dynamic_1d | 4 | 127.6 ± 24.5 | 74.9 | 16.2 | 110.9 | 0.86x |
| dynamic_1d | 5 | 120.8 ± 7.6 | 69.7 | 12.0 | 108.6 | 0.90x |
| dynamic_1d | 6 | 147.5 ± 19.6 | 80.8 | 14.2 | 133.1 | 0.74x |
| dynamic_1d | 8 | 173.6 ± 35.9 | 68.7 | 12.4 | 160.9 | 0.63x |
| dynamic_1d | 9 | 150.7 ± 37.4 | 62.1 | 12.1 | 138.4 | 0.72x |

#### grayscale,blur,flip

| Mod | np | Total (ms) | Calcul (ms) | Pack (ms) | MPI (ms) | Speedup |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| seq | 1 | 964.9 ± 34.1 | 964.9 | 0.0 | 0.0 | 1.00x |
| static_1d | 2 | 1506.1 ± 313.7 | 1387.6 | 0.0 | 1506.1 | 0.64x |
| static_1d | 3 | 1326.7 ± 212.9 | 1183.2 | 0.0 | 1326.7 | 0.73x |
| static_1d | 4 | 1031.4 ± 92.2 | 857.7 | 0.0 | 1031.4 | 0.94x |
| static_1d | 5 | 1127.8 ± 143.9 | 959.4 | 0.0 | 1127.8 | 0.86x |
| static_1d | 6 | 1281.5 ± 111.1 | 1086.8 | 0.0 | 1281.5 | 0.75x |
| static_1d | 8 | 1159.4 ± 93.4 | 955.7 | 0.0 | 1159.4 | 0.83x |
| static_1d | 9 | 1078.0 ± 231.8 | 924.2 | 0.0 | 1077.9 | 0.90x |
| static_2d | 2 | 1067.1 ± 28.4 | 962.1 | 0.0 | 1067.0 | 0.90x |
| static_2d | 3 | 1018.8 ± 112.0 | 921.4 | 0.0 | 1018.8 | 0.95x |
| static_2d | 4 | 890.1 ± 157.1 | 783.5 | 0.0 | 890.0 | 1.08x |
| static_2d | 5 | 1164.6 ± 41.7 | 934.2 | 174.2 | 988.6 | 0.83x |
| static_2d | 6 | 952.1 ± 143.6 | 829.9 | 0.0 | 952.0 | 1.01x |
| static_2d | 8 | 1188.9 ± 102.4 | 1001.3 | 0.0 | 1188.9 | 0.81x |
| static_2d | 9 | 1167.0 ± 117.4 | 932.0 | 144.4 | 1022.1 | 0.83x |
| dynamic_1d | 2 | 1301.8 ± 53.0 | 1198.1 | 0.0 | 1301.7 | 0.74x |
| dynamic_1d | 3 | 1136.9 ± 116.9 | 1039.9 | 0.0 | 1136.9 | 0.85x |
| dynamic_1d | 4 | 1084.8 ± 174.8 | 963.2 | 0.0 | 1084.7 | 0.89x |
| dynamic_1d | 5 | 952.3 ± 91.9 | 717.7 | 0.0 | 952.2 | 1.01x |
| dynamic_1d | 6 | **819.9 ± 109.6** | 615.2 | 0.0 | 819.8 | 1.18x |
| dynamic_1d | 8 | 926.4 ± 102.0 | 670.9 | 0.0 | 926.2 | 1.04x |
| dynamic_1d | 9 | 1011.5 ± 156.5 | 644.2 | 0.0 | 1011.3 | 0.95x |

Calcul reprezintă timpul cumulat maxim de procesare pe un proces. Pack include împachetarea, despachetarea și alocarea bufferelor temporare. MPI include timpul petrecut de coordonator în apelurile MPI, inclusiv așteptarea workerilor. Aceste intervale se suprapun și nu se adună pentru a obține timpul total.

</details>
