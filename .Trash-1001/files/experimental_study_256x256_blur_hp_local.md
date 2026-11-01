# Studiu pilot pe două calculatoare, 256×256

Imaginea `test_images/sample_small.ppm` are 65.536 pixeli. Acest raport păstrează studiul original și folosește numai imaginea de 256×256.

## Metodologie

Am măsurat 80 de configurații, cu câte 3 repetări, în total 240 de rulări măsurate. În această etapă măsurăm numai blur 9×9. Strategiile sunt static_1d, static_2d și dynamic_1d.

HP-Laptop are un Intel Core i7-7500U, cu 2 nuclee și 4 fire hardware. Victus are un Intel Core i5-12500H și 16 fire hardware. Am folosit Open MPI 4.1.6, compilare `mpicc -O3 -Wall` și `--bind-to none`. Procesele rulează fără fixare pe nuclee. Coordonatorul este un proces suplimentar față de numărul de workeri.

Rangul 0 rulează pe HP-Laptop pentru testele exclusiv pe HP-Laptop și pe Victus pentru celelalte teste. Graficul HP-Laptop include 1 proces secvențial, 2 procese cu un worker și 3 procese cu doi workeri. Rangurile 1 până la numărul de workeri HP-Laptop rulează pe HP-Laptop, iar workerii rămași rulează pe Victus. Limitele de 2 și 8 se referă la workeri, fără coordonator.

Speedup = media timpului secvențial / media timpului paralel. Referința secvențială rulează pe HP-Laptop pentru testele exclusiv pe HP-Laptop și pe Victus pentru celelalte teste. Eficiența este speedup / numărul total de workeri. Pe calculatoare diferite, acest raport depinde de performanța referinței secvențiale.

Timpii provin din instrumentarea C și exclud lansarea MPI, citirea imaginii, scrierea rezultatului și verificarea pixelilor. Prima repetare a fiecărei configurații salvează rezultatul pentru comparație integrală cu referința secvențială. Celelalte repetări folosesc ieșirea NONE. Timpii sunt afișați ca medie și abatere standard. Trei repetări oferă o verificare pilot, cu precizie limitată pentru operațiile scurte.

Toate graficele de timp folosesc aceeași limită verticală, inclusiv graficele strategiilor. Graficele de speedup folosesc o limită comună. Valorile extreme ridică limita verticală, astfel că unele curbe și bare sunt aproape de zero pe această scară. Tabelele păstrează valorile numerice. Datele brute includ timpii fiecărui worker, distribuția pe calculatoare și datele necesare eficienței. Variația cu rezoluția necesită măsurători la alte dimensiuni și nu poate fi evaluată cu această singură imagine.

## blur

![Timp total (ms), blur](benchmark_small_two_machines_blur_hp_local/execution_time_blur.png)

![Speedup, blur](benchmark_small_two_machines_blur_hp_local/speedup_blur.png)

![Strategii, blur](benchmark_small_two_machines_blur_hp_local/partition_strategies_blur.png)

Cel mai mic timp paralel mediu este 21.172 ms, cu static_1d, 0 workeri HP-Laptop și 8 workeri Victus. Speedup față de referința de pe victus este 5.06.

## Verificare și interpretare

Cea mai lentă repetare a durat 220.008 ms, pentru blur, static_2d, cu 2 workeri HP-Laptop și 0 workeri Victus. Cea mai mare abatere standard relativă este 27.2%, pentru blur, static_1d, HP=2, Victus=8. Am păstrat toate repetările. Acest pilot verifică matricea și graficele, dar variația limitează concluziile despre ordinea strategiilor. Nu am măsurat separat rețeaua sau încărcarea de fond, deci nu pot atribui variația unei singure cauze.

Toate cele 80 de configurații au rezultate identice pixel cu pixel cu referința secvențială în prima repetare.

Barele C și W se suprapun în timp și nu se adună. HP înseamnă HP-Laptop, iar V înseamnă Victus. Barele workerilor arată calculul și timpul instrumentat de alocare/transfer. Timpul rămas până la timpul coordonatorului nu este etichetat drept inactivitate, deoarece programul nu măsoară separat acea durată. Segmentele pack/unpack nu sunt defalcate per worker, deoarece instrumentarea oferă numai totalul coordonatorului.

## Reproducere

Scriptul separat este [benchmark_two_machines_small.py](benchmark_two_machines_small.py). Ambele calculatoare trebuie să acceseze același director și să accepte conexiuni SSH fără parolă. Rularea completă folosește comanda de mai jos. Scriptul reia configurațiile lipsă din jurnalul existent.

```bash
uv run --with numpy --with matplotlib python benchmark_two_machines_small.py
```

Pentru regenerarea raportului și a figurilor din măsurătorile salvate:

```bash
uv run --with numpy --with matplotlib python benchmark_two_machines_small.py --plot-only
```

## Date complete

Datele sunt în [results.csv](benchmark_small_two_machines_blur_hp_local/results.csv), [runs.csv](benchmark_small_two_machines_blur_hp_local/runs.csv) și [runs.jsonl](benchmark_small_two_machines_blur_hp_local/runs.jsonl). Fișierul [metadata.json](benchmark_small_two_machines_blur_hp_local/metadata.json) păstrează informațiile calculatoarelor și hash-urile imaginii și sursei. Câmpurile hp și victus reprezintă numărul de workeri. În CSV, modul seq are zero workeri și coloana coordinator identifică laptopul. În jurnalul JSONL, hp=1 selectează referința secvențială HP-Laptop, iar hp=0 selectează Victus.

| Operație | Strategie | HP workeri | Victus workeri | Coordonator | Total ms | Abatere ms | Speedup | Eficiență |
| --- | --- | ---: | ---: | --- | ---: | ---: | ---: | ---: |
| blur | seq | 0 | 0 | HP-Laptop | 133.114 | 2.870 | 1.000 | 1.000 |
| blur | seq | 0 | 0 | victus | 107.050 | 0.746 | 1.000 | 1.000 |
| blur | static_1d | 1 | 0 | HP-Laptop | 153.234 | 32.950 | 0.869 | 0.869 |
| blur | static_1d | 2 | 0 | HP-Laptop | 178.887 | 13.713 | 0.744 | 0.372 |
| blur | static_1d | 0 | 1 | victus | 110.256 | 1.989 | 0.971 | 0.971 |
| blur | static_1d | 0 | 2 | victus | 56.542 | 1.015 | 1.893 | 0.947 |
| blur | static_1d | 0 | 3 | victus | 38.524 | 0.459 | 2.779 | 0.926 |
| blur | static_1d | 0 | 4 | victus | 31.171 | 0.931 | 3.434 | 0.859 |
| blur | static_1d | 0 | 5 | victus | 27.024 | 1.310 | 3.961 | 0.792 |
| blur | static_1d | 0 | 6 | victus | 27.247 | 6.594 | 3.929 | 0.655 |
| blur | static_1d | 0 | 7 | victus | 24.058 | 5.854 | 4.450 | 0.636 |
| blur | static_1d | 0 | 8 | victus | 21.172 | 4.608 | 5.056 | 0.632 |
| blur | static_1d | 1 | 1 | victus | 115.730 | 1.446 | 0.925 | 0.462 |
| blur | static_1d | 1 | 2 | victus | 94.822 | 9.273 | 1.129 | 0.376 |
| blur | static_1d | 1 | 3 | victus | 74.518 | 0.624 | 1.437 | 0.359 |
| blur | static_1d | 1 | 4 | victus | 66.518 | 1.439 | 1.609 | 0.322 |
| blur | static_1d | 1 | 5 | victus | 62.215 | 4.598 | 1.721 | 0.287 |
| blur | static_1d | 1 | 6 | victus | 51.919 | 4.329 | 2.062 | 0.295 |
| blur | static_1d | 1 | 7 | victus | 55.805 | 2.717 | 1.918 | 0.240 |
| blur | static_1d | 1 | 8 | victus | 53.559 | 5.951 | 1.999 | 0.222 |
| blur | static_1d | 2 | 1 | victus | 104.710 | 1.264 | 1.022 | 0.341 |
| blur | static_1d | 2 | 2 | victus | 79.021 | 1.745 | 1.355 | 0.339 |
| blur | static_1d | 2 | 3 | victus | 71.766 | 6.473 | 1.492 | 0.298 |
| blur | static_1d | 2 | 4 | victus | 62.637 | 1.358 | 1.709 | 0.285 |
| blur | static_1d | 2 | 5 | victus | 68.013 | 12.926 | 1.574 | 0.225 |
| blur | static_1d | 2 | 6 | victus | 60.430 | 0.500 | 1.771 | 0.221 |
| blur | static_1d | 2 | 7 | victus | 61.120 | 2.302 | 1.751 | 0.195 |
| blur | static_1d | 2 | 8 | victus | 67.297 | 18.315 | 1.591 | 0.159 |
| blur | static_2d | 1 | 0 | HP-Laptop | 148.211 | 33.866 | 0.898 | 0.898 |
| blur | static_2d | 2 | 0 | HP-Laptop | 186.886 | 28.714 | 0.712 | 0.356 |
| blur | static_2d | 0 | 1 | victus | 118.342 | 6.667 | 0.905 | 0.905 |
| blur | static_2d | 0 | 2 | victus | 63.894 | 8.821 | 1.675 | 0.838 |
| blur | static_2d | 0 | 3 | victus | 53.691 | 9.517 | 1.994 | 0.665 |
| blur | static_2d | 0 | 4 | victus | 53.602 | 1.707 | 1.997 | 0.499 |
| blur | static_2d | 0 | 5 | victus | 49.008 | 0.035 | 2.184 | 0.437 |
| blur | static_2d | 0 | 6 | victus | 44.936 | 0.087 | 2.382 | 0.397 |
| blur | static_2d | 0 | 7 | victus | 35.101 | 8.605 | 3.050 | 0.436 |
| blur | static_2d | 0 | 8 | victus | 38.742 | 1.312 | 2.763 | 0.345 |
| blur | static_2d | 1 | 1 | victus | 115.767 | 0.816 | 0.925 | 0.462 |
| blur | static_2d | 1 | 2 | victus | 87.548 | 1.573 | 1.223 | 0.408 |
| blur | static_2d | 1 | 3 | victus | 74.263 | 2.848 | 1.441 | 0.360 |
| blur | static_2d | 1 | 4 | victus | 63.898 | 6.723 | 1.675 | 0.335 |
| blur | static_2d | 1 | 5 | victus | 61.091 | 3.717 | 1.752 | 0.292 |
| blur | static_2d | 1 | 6 | victus | 56.152 | 1.857 | 1.906 | 0.272 |
| blur | static_2d | 1 | 7 | victus | 56.858 | 0.919 | 1.883 | 0.235 |
| blur | static_2d | 1 | 8 | victus | 54.878 | 2.872 | 1.951 | 0.217 |
| blur | static_2d | 2 | 1 | victus | 96.636 | 2.200 | 1.108 | 0.369 |
| blur | static_2d | 2 | 2 | victus | 79.335 | 0.590 | 1.349 | 0.337 |
| blur | static_2d | 2 | 3 | victus | 74.704 | 7.895 | 1.433 | 0.287 |
| blur | static_2d | 2 | 4 | victus | 67.202 | 5.093 | 1.593 | 0.265 |
| blur | static_2d | 2 | 5 | victus | 62.389 | 3.336 | 1.716 | 0.245 |
| blur | static_2d | 2 | 6 | victus | 63.680 | 0.906 | 1.681 | 0.210 |
| blur | static_2d | 2 | 7 | victus | 61.406 | 1.514 | 1.743 | 0.194 |
| blur | static_2d | 2 | 8 | victus | 61.244 | 5.256 | 1.748 | 0.175 |
| blur | dynamic_1d | 1 | 0 | HP-Laptop | 137.205 | 13.554 | 0.970 | 0.970 |
| blur | dynamic_1d | 2 | 0 | HP-Laptop | 110.059 | 12.426 | 1.209 | 0.605 |
| blur | dynamic_1d | 0 | 1 | victus | 118.558 | 6.867 | 0.903 | 0.903 |
| blur | dynamic_1d | 0 | 2 | victus | 62.491 | 7.697 | 1.713 | 0.857 |
| blur | dynamic_1d | 0 | 3 | victus | 53.101 | 10.712 | 2.016 | 0.672 |
| blur | dynamic_1d | 0 | 4 | victus | 50.845 | 1.343 | 2.105 | 0.526 |
| blur | dynamic_1d | 0 | 5 | victus | 46.735 | 0.946 | 2.291 | 0.458 |
| blur | dynamic_1d | 0 | 6 | victus | 40.473 | 0.368 | 2.645 | 0.441 |
| blur | dynamic_1d | 0 | 7 | victus | 37.795 | 1.610 | 2.832 | 0.405 |
| blur | dynamic_1d | 0 | 8 | victus | 32.613 | 0.525 | 3.282 | 0.410 |
| blur | dynamic_1d | 1 | 1 | victus | 111.194 | 0.714 | 0.963 | 0.481 |
| blur | dynamic_1d | 1 | 2 | victus | 74.204 | 1.391 | 1.443 | 0.481 |
| blur | dynamic_1d | 1 | 3 | victus | 62.954 | 2.156 | 1.700 | 0.425 |
| blur | dynamic_1d | 1 | 4 | victus | 84.814 | 20.994 | 1.262 | 0.252 |
| blur | dynamic_1d | 1 | 5 | victus | 56.518 | 0.394 | 1.894 | 0.316 |
| blur | dynamic_1d | 1 | 6 | victus | 55.151 | 0.721 | 1.941 | 0.277 |
| blur | dynamic_1d | 1 | 7 | victus | 51.557 | 1.362 | 2.076 | 0.260 |
| blur | dynamic_1d | 1 | 8 | victus | 46.762 | 1.879 | 2.289 | 0.254 |
| blur | dynamic_1d | 2 | 1 | victus | 89.337 | 2.623 | 1.198 | 0.399 |
| blur | dynamic_1d | 2 | 2 | victus | 75.748 | 4.969 | 1.413 | 0.353 |
| blur | dynamic_1d | 2 | 3 | victus | 66.095 | 2.513 | 1.620 | 0.324 |
| blur | dynamic_1d | 2 | 4 | victus | 61.817 | 2.575 | 1.732 | 0.289 |
| blur | dynamic_1d | 2 | 5 | victus | 60.827 | 2.483 | 1.760 | 0.251 |
| blur | dynamic_1d | 2 | 6 | victus | 65.183 | 4.425 | 1.642 | 0.205 |
| blur | dynamic_1d | 2 | 7 | victus | 61.530 | 4.685 | 1.740 | 0.193 |
| blur | dynamic_1d | 2 | 8 | victus | 58.034 | 4.528 | 1.845 | 0.184 |
