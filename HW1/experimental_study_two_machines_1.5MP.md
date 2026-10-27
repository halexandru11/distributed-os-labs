# Studiu pe două calculatoare, 1.5MP

Imaginea `test_images/sample_1.5MP.ppm` are 1600×900 pixeli. Rezultatele sunt separate de studiile anterioare.

## Metodologie

Am măsurat 320 de configurații, cu câte 3 repetări, în total 960 de rulări măsurate. Operațiile sunt grayscale, blur 9×9, rotate90 și pipeline-ul grayscale,blur,flip. Strategiile sunt static_1d, static_2d și dynamic_1d.

HP-Laptop are un Intel Core i7-7500U, cu 2 nuclee și 4 fire hardware. Victus are un Intel Core i5-12500H și 16 fire hardware. Am folosit Open MPI 4.1.6, compilare `mpicc -O3 -Wall` și `--bind-to none`. Procesele rulează fără fixare pe nuclee. Coordonatorul este un proces suplimentar față de numărul de workeri.

Rangul 0 rulează pe HP-Laptop pentru testele exclusiv pe HP-Laptop și pe Victus pentru celelalte teste. Graficul HP-Laptop include 1 proces secvențial, 2 procese cu un worker și 3 procese cu doi workeri. Rangurile 1 până la numărul de workeri HP-Laptop rulează pe HP-Laptop, iar workerii rămași rulează pe Victus. Limitele de 2 și 8 se referă la workeri, fără coordonator.

Speedup = media timpului secvențial / media timpului paralel. Referința secvențială rulează pe HP-Laptop pentru testele exclusiv pe HP-Laptop și pe Victus pentru celelalte teste. Eficiența este speedup / numărul total de workeri. Pe calculatoare diferite, acest raport depinde de performanța referinței secvențiale.

Timpii provin din instrumentarea C și exclud lansarea MPI, citirea imaginii, scrierea rezultatului și verificarea pixelilor. Prima repetare a fiecărei configurații salvează rezultatul pentru comparație integrală cu referința secvențială. Celelalte repetări folosesc ieșirea NONE. Timpii sunt afișați ca medie și abatere standard. Trei repetări oferă o verificare pilot, cu precizie limitată pentru operațiile scurte.

Toate graficele de timp folosesc aceeași limită verticală, inclusiv graficele strategiilor. Graficele de speedup folosesc o limită comună. Valorile extreme ridică limita verticală, astfel că unele curbe și bare sunt aproape de zero pe această scară. Tabelele păstrează valorile numerice. Datele brute includ timpii fiecărui worker, distribuția pe calculatoare și datele necesare eficienței. Suita măsoară aceleași configurații la 1.5MP, 4MP și 8MP. Datele pentru eficiență și variația cu rezoluția sunt în CSV-urile fiecărei rezoluții.

## grayscale

![Timp total (ms), grayscale](benchmark_two_machines/1.5MP/execution_time_grayscale.png)

![Speedup, grayscale](benchmark_two_machines/1.5MP/speedup_grayscale.png)

![Strategii, grayscale](benchmark_two_machines/1.5MP/partition_strategies_grayscale.png)

Cel mai mic timp paralel mediu este 4.485 ms, cu dynamic_1d, 0 workeri HP-Laptop și 6 workeri Victus. Speedup față de referința de pe victus este 1.28.

## blur

![Timp total (ms), blur](benchmark_two_machines/1.5MP/execution_time_blur.png)

![Speedup, blur](benchmark_two_machines/1.5MP/speedup_blur.png)

![Strategii, blur](benchmark_two_machines/1.5MP/partition_strategies_blur.png)

Cel mai mic timp paralel mediu este 20.527 ms, cu dynamic_1d, 0 workeri HP-Laptop și 7 workeri Victus. Speedup față de referința de pe victus este 5.24.

## rotate90

![Timp total (ms), rotate90](benchmark_two_machines/1.5MP/execution_time_rotate90.png)

![Speedup, rotate90](benchmark_two_machines/1.5MP/speedup_rotate90.png)

![Strategii, rotate90](benchmark_two_machines/1.5MP/partition_strategies_rotate90.png)

Cel mai mic timp paralel mediu este 4.557 ms, cu dynamic_1d, 0 workeri HP-Laptop și 7 workeri Victus. Speedup față de referința de pe victus este 1.56.

## grayscale,blur,flip

![Timp total (ms), grayscale,blur,flip](benchmark_two_machines/1.5MP/execution_time_grayscale_blur_flip.png)

![Speedup, grayscale,blur,flip](benchmark_two_machines/1.5MP/speedup_grayscale_blur_flip.png)

![Strategii, grayscale,blur,flip](benchmark_two_machines/1.5MP/partition_strategies_grayscale_blur_flip.png)

Cel mai mic timp paralel mediu este 23.181 ms, cu dynamic_1d, 0 workeri HP-Laptop și 8 workeri Victus. Speedup față de referința de pe victus este 5.13.

## Verificare și interpretare

Cea mai lentă repetare a durat 290.853 ms, pentru grayscale,blur,flip, dynamic_1d, cu 2 workeri HP-Laptop și 8 workeri Victus. Cea mai mare abatere standard relativă este 78.5%, pentru grayscale,blur,flip, dynamic_1d, HP=2, Victus=8. Am păstrat toate repetările. Acest pilot verifică matricea și graficele, dar variația limitează concluziile despre ordinea strategiilor. Nu am măsurat separat rețeaua sau încărcarea de fond, deci nu pot atribui variația unei singure cauze.

Toate cele 320 de configurații au rezultate identice pixel cu pixel cu referința secvențială în prima repetare.

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

Datele sunt în [results.csv](benchmark_two_machines/1.5MP/results.csv), [runs.csv](benchmark_two_machines/1.5MP/runs.csv) și [runs.jsonl](benchmark_two_machines/1.5MP/runs.jsonl). Fișierul [metadata.json](benchmark_two_machines/1.5MP/metadata.json) păstrează informațiile calculatoarelor și hash-urile imaginii și sursei. Câmpurile hp și victus reprezintă numărul de workeri. În CSV, modul seq are zero workeri și coloana coordinator identifică laptopul. În jurnalul JSONL, hp=1 selectează referința secvențială HP-Laptop, iar hp=0 selectează Victus.

| Operație | Strategie | HP workeri | Victus workeri | Coordonator | Total ms | Abatere ms | Speedup | Eficiență |
| --- | --- | ---: | ---: | --- | ---: | ---: | ---: | ---: |
| grayscale | seq | 0 | 0 | HP-Laptop | 19.827 | 5.610 | 1.000 | 1.000 |
| grayscale | seq | 0 | 0 | victus | 5.743 | 0.490 | 1.000 | 1.000 |
| blur | seq | 0 | 0 | HP-Laptop | 128.590 | 10.036 | 1.000 | 1.000 |
| blur | seq | 0 | 0 | victus | 107.532 | 1.039 | 1.000 | 1.000 |
| rotate90 | seq | 0 | 0 | HP-Laptop | 22.457 | 2.575 | 1.000 | 1.000 |
| rotate90 | seq | 0 | 0 | victus | 7.098 | 0.890 | 1.000 | 1.000 |
| grayscale,blur,flip | seq | 0 | 0 | HP-Laptop | 152.937 | 7.441 | 1.000 | 1.000 |
| grayscale,blur,flip | seq | 0 | 0 | victus | 118.958 | 6.405 | 1.000 | 1.000 |
| grayscale | static_1d | 1 | 0 | HP-Laptop | 17.523 | 0.949 | 1.132 | 1.132 |
| grayscale | static_1d | 2 | 0 | HP-Laptop | 18.042 | 3.106 | 1.099 | 0.549 |
| grayscale | static_1d | 0 | 1 | victus | 10.092 | 1.883 | 0.569 | 0.569 |
| grayscale | static_1d | 0 | 2 | victus | 6.847 | 1.455 | 0.839 | 0.419 |
| grayscale | static_1d | 0 | 3 | victus | 5.579 | 0.323 | 1.029 | 0.343 |
| grayscale | static_1d | 0 | 4 | victus | 5.761 | 0.714 | 0.997 | 0.249 |
| grayscale | static_1d | 0 | 5 | victus | 5.365 | 0.643 | 1.070 | 0.214 |
| grayscale | static_1d | 0 | 6 | victus | 8.942 | 2.959 | 0.642 | 0.107 |
| grayscale | static_1d | 0 | 7 | victus | 7.454 | 2.320 | 0.770 | 0.110 |
| grayscale | static_1d | 0 | 8 | victus | 6.636 | 2.788 | 0.865 | 0.108 |
| grayscale | static_1d | 1 | 1 | victus | 59.463 | 0.519 | 0.097 | 0.048 |
| grayscale | static_1d | 1 | 2 | victus | 49.321 | 1.515 | 0.116 | 0.039 |
| grayscale | static_1d | 1 | 3 | victus | 41.678 | 0.637 | 0.138 | 0.034 |
| grayscale | static_1d | 1 | 4 | victus | 37.677 | 1.329 | 0.152 | 0.030 |
| grayscale | static_1d | 1 | 5 | victus | 34.663 | 1.082 | 0.166 | 0.028 |
| grayscale | static_1d | 1 | 6 | victus | 34.423 | 1.798 | 0.167 | 0.024 |
| grayscale | static_1d | 1 | 7 | victus | 30.643 | 1.175 | 0.187 | 0.023 |
| grayscale | static_1d | 1 | 8 | victus | 28.864 | 1.439 | 0.199 | 0.022 |
| grayscale | static_1d | 2 | 1 | victus | 65.973 | 3.360 | 0.087 | 0.029 |
| grayscale | static_1d | 2 | 2 | victus | 53.065 | 0.862 | 0.108 | 0.027 |
| grayscale | static_1d | 2 | 3 | victus | 50.746 | 0.480 | 0.113 | 0.023 |
| grayscale | static_1d | 2 | 4 | victus | 47.116 | 0.734 | 0.122 | 0.020 |
| grayscale | static_1d | 2 | 5 | victus | 44.669 | 0.770 | 0.129 | 0.018 |
| grayscale | static_1d | 2 | 6 | victus | 42.775 | 1.464 | 0.134 | 0.017 |
| grayscale | static_1d | 2 | 7 | victus | 41.061 | 0.634 | 0.140 | 0.016 |
| grayscale | static_1d | 2 | 8 | victus | 40.085 | 0.368 | 0.143 | 0.014 |
| grayscale | static_2d | 1 | 0 | HP-Laptop | 26.485 | 7.480 | 0.749 | 0.749 |
| grayscale | static_2d | 2 | 0 | HP-Laptop | 15.974 | 1.421 | 1.241 | 0.621 |
| grayscale | static_2d | 0 | 1 | victus | 9.285 | 0.601 | 0.619 | 0.619 |
| grayscale | static_2d | 0 | 2 | victus | 6.941 | 1.213 | 0.827 | 0.414 |
| grayscale | static_2d | 0 | 3 | victus | 6.124 | 0.285 | 0.938 | 0.313 |
| grayscale | static_2d | 0 | 4 | victus | 6.619 | 0.581 | 0.868 | 0.217 |
| grayscale | static_2d | 0 | 5 | victus | 5.327 | 0.169 | 1.078 | 0.216 |
| grayscale | static_2d | 0 | 6 | victus | 7.085 | 0.247 | 0.811 | 0.135 |
| grayscale | static_2d | 0 | 7 | victus | 6.610 | 2.298 | 0.869 | 0.124 |
| grayscale | static_2d | 0 | 8 | victus | 9.007 | 3.562 | 0.638 | 0.080 |
| grayscale | static_2d | 1 | 1 | victus | 60.219 | 1.123 | 0.095 | 0.048 |
| grayscale | static_2d | 1 | 2 | victus | 48.690 | 0.843 | 0.118 | 0.039 |
| grayscale | static_2d | 1 | 3 | victus | 43.401 | 1.918 | 0.132 | 0.033 |
| grayscale | static_2d | 1 | 4 | victus | 39.246 | 0.786 | 0.146 | 0.029 |
| grayscale | static_2d | 1 | 5 | victus | 36.854 | 2.020 | 0.156 | 0.026 |
| grayscale | static_2d | 1 | 6 | victus | 32.189 | 1.673 | 0.178 | 0.025 |
| grayscale | static_2d | 1 | 7 | victus | 33.627 | 0.356 | 0.171 | 0.021 |
| grayscale | static_2d | 1 | 8 | victus | 30.576 | 1.260 | 0.188 | 0.021 |
| grayscale | static_2d | 2 | 1 | victus | 71.129 | 1.766 | 0.081 | 0.027 |
| grayscale | static_2d | 2 | 2 | victus | 55.451 | 0.165 | 0.104 | 0.026 |
| grayscale | static_2d | 2 | 3 | victus | 50.264 | 0.562 | 0.114 | 0.023 |
| grayscale | static_2d | 2 | 4 | victus | 49.032 | 0.124 | 0.117 | 0.020 |
| grayscale | static_2d | 2 | 5 | victus | 45.817 | 0.376 | 0.125 | 0.018 |
| grayscale | static_2d | 2 | 6 | victus | 50.215 | 11.592 | 0.114 | 0.014 |
| grayscale | static_2d | 2 | 7 | victus | 41.563 | 0.277 | 0.138 | 0.015 |
| grayscale | static_2d | 2 | 8 | victus | 40.426 | 0.238 | 0.142 | 0.014 |
| grayscale | dynamic_1d | 1 | 0 | HP-Laptop | 18.711 | 0.412 | 1.060 | 1.060 |
| grayscale | dynamic_1d | 2 | 0 | HP-Laptop | 14.006 | 1.013 | 1.416 | 0.708 |
| grayscale | dynamic_1d | 0 | 1 | victus | 9.326 | 0.063 | 0.616 | 0.616 |
| grayscale | dynamic_1d | 0 | 2 | victus | 6.190 | 0.849 | 0.928 | 0.464 |
| grayscale | dynamic_1d | 0 | 3 | victus | 4.801 | 0.015 | 1.196 | 0.399 |
| grayscale | dynamic_1d | 0 | 4 | victus | 4.682 | 0.134 | 1.227 | 0.307 |
| grayscale | dynamic_1d | 0 | 5 | victus | 5.050 | 0.363 | 1.137 | 0.227 |
| grayscale | dynamic_1d | 0 | 6 | victus | 4.485 | 0.072 | 1.281 | 0.213 |
| grayscale | dynamic_1d | 0 | 7 | victus | 5.229 | 1.723 | 1.098 | 0.157 |
| grayscale | dynamic_1d | 0 | 8 | victus | 5.653 | 1.844 | 1.016 | 0.127 |
| grayscale | dynamic_1d | 1 | 1 | victus | 36.645 | 5.753 | 0.157 | 0.078 |
| grayscale | dynamic_1d | 1 | 2 | victus | 29.147 | 1.770 | 0.197 | 0.066 |
| grayscale | dynamic_1d | 1 | 3 | victus | 27.073 | 1.702 | 0.212 | 0.053 |
| grayscale | dynamic_1d | 1 | 4 | victus | 26.149 | 0.331 | 0.220 | 0.044 |
| grayscale | dynamic_1d | 1 | 5 | victus | 25.711 | 0.352 | 0.223 | 0.037 |
| grayscale | dynamic_1d | 1 | 6 | victus | 29.410 | 8.786 | 0.195 | 0.028 |
| grayscale | dynamic_1d | 1 | 7 | victus | 29.969 | 8.459 | 0.192 | 0.024 |
| grayscale | dynamic_1d | 1 | 8 | victus | 26.992 | 2.740 | 0.213 | 0.024 |
| grayscale | dynamic_1d | 2 | 1 | victus | 67.265 | 2.729 | 0.085 | 0.028 |
| grayscale | dynamic_1d | 2 | 2 | victus | 60.054 | 1.227 | 0.096 | 0.024 |
| grayscale | dynamic_1d | 2 | 3 | victus | 56.355 | 0.247 | 0.102 | 0.020 |
| grayscale | dynamic_1d | 2 | 4 | victus | 50.898 | 6.188 | 0.113 | 0.019 |
| grayscale | dynamic_1d | 2 | 5 | victus | 62.162 | 23.945 | 0.092 | 0.013 |
| grayscale | dynamic_1d | 2 | 6 | victus | 49.267 | 4.194 | 0.117 | 0.015 |
| grayscale | dynamic_1d | 2 | 7 | victus | 57.758 | 23.296 | 0.099 | 0.011 |
| grayscale | dynamic_1d | 2 | 8 | victus | 45.801 | 3.597 | 0.125 | 0.013 |
| blur | static_1d | 1 | 0 | HP-Laptop | 130.341 | 3.375 | 0.987 | 0.987 |
| blur | static_1d | 2 | 0 | HP-Laptop | 191.323 | 3.491 | 0.672 | 0.336 |
| blur | static_1d | 0 | 1 | victus | 112.165 | 3.958 | 0.959 | 0.959 |
| blur | static_1d | 0 | 2 | victus | 56.760 | 0.635 | 1.894 | 0.947 |
| blur | static_1d | 0 | 3 | victus | 39.553 | 1.266 | 2.719 | 0.906 |
| blur | static_1d | 0 | 4 | victus | 30.950 | 1.340 | 3.474 | 0.869 |
| blur | static_1d | 0 | 5 | victus | 26.730 | 0.530 | 4.023 | 0.805 |
| blur | static_1d | 0 | 6 | victus | 23.927 | 1.669 | 4.494 | 0.749 |
| blur | static_1d | 0 | 7 | victus | 20.834 | 1.376 | 5.161 | 0.737 |
| blur | static_1d | 0 | 8 | victus | 21.997 | 5.285 | 4.888 | 0.611 |
| blur | static_1d | 1 | 1 | victus | 115.986 | 1.106 | 0.927 | 0.464 |
| blur | static_1d | 1 | 2 | victus | 88.183 | 1.659 | 1.219 | 0.406 |
| blur | static_1d | 1 | 3 | victus | 77.168 | 2.278 | 1.393 | 0.348 |
| blur | static_1d | 1 | 4 | victus | 66.005 | 3.404 | 1.629 | 0.326 |
| blur | static_1d | 1 | 5 | victus | 55.387 | 3.133 | 1.941 | 0.324 |
| blur | static_1d | 1 | 6 | victus | 56.530 | 1.867 | 1.902 | 0.272 |
| blur | static_1d | 1 | 7 | victus | 46.819 | 3.596 | 2.297 | 0.287 |
| blur | static_1d | 1 | 8 | victus | 42.073 | 4.396 | 2.556 | 0.284 |
| blur | static_1d | 2 | 1 | victus | 102.294 | 2.895 | 1.051 | 0.350 |
| blur | static_1d | 2 | 2 | victus | 79.917 | 0.860 | 1.346 | 0.336 |
| blur | static_1d | 2 | 3 | victus | 72.710 | 4.974 | 1.479 | 0.296 |
| blur | static_1d | 2 | 4 | victus | 64.387 | 2.140 | 1.670 | 0.278 |
| blur | static_1d | 2 | 5 | victus | 60.618 | 0.610 | 1.774 | 0.253 |
| blur | static_1d | 2 | 6 | victus | 62.284 | 13.294 | 1.726 | 0.216 |
| blur | static_1d | 2 | 7 | victus | 55.408 | 5.797 | 1.941 | 0.216 |
| blur | static_1d | 2 | 8 | victus | 49.946 | 0.741 | 2.153 | 0.215 |
| blur | static_2d | 1 | 0 | HP-Laptop | 136.176 | 5.301 | 0.944 | 0.944 |
| blur | static_2d | 2 | 0 | HP-Laptop | 154.212 | 26.564 | 0.834 | 0.417 |
| blur | static_2d | 0 | 1 | victus | 110.290 | 0.880 | 0.975 | 0.975 |
| blur | static_2d | 0 | 2 | victus | 57.186 | 0.524 | 1.880 | 0.940 |
| blur | static_2d | 0 | 3 | victus | 40.021 | 1.586 | 2.687 | 0.896 |
| blur | static_2d | 0 | 4 | victus | 33.500 | 0.483 | 3.210 | 0.802 |
| blur | static_2d | 0 | 5 | victus | 27.600 | 2.086 | 3.896 | 0.779 |
| blur | static_2d | 0 | 6 | victus | 23.758 | 0.161 | 4.526 | 0.754 |
| blur | static_2d | 0 | 7 | victus | 21.809 | 2.321 | 4.931 | 0.704 |
| blur | static_2d | 0 | 8 | victus | 26.691 | 1.286 | 4.029 | 0.504 |
| blur | static_2d | 1 | 1 | victus | 116.283 | 0.392 | 0.925 | 0.462 |
| blur | static_2d | 1 | 2 | victus | 86.503 | 2.086 | 1.243 | 0.414 |
| blur | static_2d | 1 | 3 | victus | 74.820 | 1.542 | 1.437 | 0.359 |
| blur | static_2d | 1 | 4 | victus | 67.745 | 2.818 | 1.587 | 0.317 |
| blur | static_2d | 1 | 5 | victus | 61.383 | 1.264 | 1.752 | 0.292 |
| blur | static_2d | 1 | 6 | victus | 56.454 | 1.830 | 1.905 | 0.272 |
| blur | static_2d | 1 | 7 | victus | 51.937 | 2.929 | 2.070 | 0.259 |
| blur | static_2d | 1 | 8 | victus | 47.639 | 3.622 | 2.257 | 0.251 |
| blur | static_2d | 2 | 1 | victus | 102.154 | 1.784 | 1.053 | 0.351 |
| blur | static_2d | 2 | 2 | victus | 81.953 | 1.656 | 1.312 | 0.328 |
| blur | static_2d | 2 | 3 | victus | 71.114 | 3.214 | 1.512 | 0.302 |
| blur | static_2d | 2 | 4 | victus | 61.587 | 2.104 | 1.746 | 0.291 |
| blur | static_2d | 2 | 5 | victus | 61.976 | 6.955 | 1.735 | 0.248 |
| blur | static_2d | 2 | 6 | victus | 58.398 | 0.664 | 1.841 | 0.230 |
| blur | static_2d | 2 | 7 | victus | 52.524 | 1.127 | 2.047 | 0.227 |
| blur | static_2d | 2 | 8 | victus | 50.976 | 1.890 | 2.109 | 0.211 |
| blur | dynamic_1d | 1 | 0 | HP-Laptop | 145.345 | 28.668 | 0.885 | 0.885 |
| blur | dynamic_1d | 2 | 0 | HP-Laptop | 106.953 | 9.704 | 1.202 | 0.601 |
| blur | dynamic_1d | 0 | 1 | victus | 111.191 | 1.246 | 0.967 | 0.967 |
| blur | dynamic_1d | 0 | 2 | victus | 56.462 | 0.427 | 1.905 | 0.952 |
| blur | dynamic_1d | 0 | 3 | victus | 38.877 | 1.632 | 2.766 | 0.922 |
| blur | dynamic_1d | 0 | 4 | victus | 32.317 | 2.457 | 3.327 | 0.832 |
| blur | dynamic_1d | 0 | 5 | victus | 25.215 | 0.482 | 4.265 | 0.853 |
| blur | dynamic_1d | 0 | 6 | victus | 21.400 | 0.413 | 5.025 | 0.837 |
| blur | dynamic_1d | 0 | 7 | victus | 20.527 | 2.113 | 5.238 | 0.748 |
| blur | dynamic_1d | 0 | 8 | victus | 21.831 | 8.957 | 4.926 | 0.616 |
| blur | dynamic_1d | 1 | 1 | victus | 108.867 | 22.443 | 0.988 | 0.494 |
| blur | dynamic_1d | 1 | 2 | victus | 96.184 | 49.384 | 1.118 | 0.373 |
| blur | dynamic_1d | 1 | 3 | victus | 52.617 | 0.212 | 2.044 | 0.511 |
| blur | dynamic_1d | 1 | 4 | victus | 47.883 | 3.227 | 2.246 | 0.449 |
| blur | dynamic_1d | 1 | 5 | victus | 43.372 | 1.292 | 2.479 | 0.413 |
| blur | dynamic_1d | 1 | 6 | victus | 40.850 | 1.938 | 2.632 | 0.376 |
| blur | dynamic_1d | 1 | 7 | victus | 37.550 | 1.990 | 2.864 | 0.358 |
| blur | dynamic_1d | 1 | 8 | victus | 35.686 | 4.977 | 3.013 | 0.335 |
| blur | dynamic_1d | 2 | 1 | victus | 90.712 | 4.386 | 1.185 | 0.395 |
| blur | dynamic_1d | 2 | 2 | victus | 69.895 | 4.350 | 1.538 | 0.385 |
| blur | dynamic_1d | 2 | 3 | victus | 62.216 | 0.377 | 1.728 | 0.346 |
| blur | dynamic_1d | 2 | 4 | victus | 56.813 | 1.854 | 1.893 | 0.315 |
| blur | dynamic_1d | 2 | 5 | victus | 53.100 | 4.559 | 2.025 | 0.289 |
| blur | dynamic_1d | 2 | 6 | victus | 49.219 | 2.077 | 2.185 | 0.273 |
| blur | dynamic_1d | 2 | 7 | victus | 46.754 | 3.178 | 2.300 | 0.256 |
| blur | dynamic_1d | 2 | 8 | victus | 44.314 | 2.297 | 2.427 | 0.243 |
| rotate90 | static_1d | 1 | 0 | HP-Laptop | 28.822 | 3.700 | 0.779 | 0.779 |
| rotate90 | static_1d | 2 | 0 | HP-Laptop | 22.063 | 2.582 | 1.018 | 0.509 |
| rotate90 | static_1d | 0 | 1 | victus | 10.353 | 0.596 | 0.686 | 0.686 |
| rotate90 | static_1d | 0 | 2 | victus | 8.385 | 0.238 | 0.847 | 0.423 |
| rotate90 | static_1d | 0 | 3 | victus | 7.292 | 1.346 | 0.973 | 0.324 |
| rotate90 | static_1d | 0 | 4 | victus | 5.888 | 0.344 | 1.206 | 0.301 |
| rotate90 | static_1d | 0 | 5 | victus | 6.485 | 0.402 | 1.095 | 0.219 |
| rotate90 | static_1d | 0 | 6 | victus | 6.308 | 0.575 | 1.125 | 0.188 |
| rotate90 | static_1d | 0 | 7 | victus | 6.795 | 0.421 | 1.045 | 0.149 |
| rotate90 | static_1d | 0 | 8 | victus | 8.443 | 2.776 | 0.841 | 0.105 |
| rotate90 | static_1d | 1 | 1 | victus | 59.920 | 1.036 | 0.118 | 0.059 |
| rotate90 | static_1d | 1 | 2 | victus | 48.046 | 0.947 | 0.148 | 0.049 |
| rotate90 | static_1d | 1 | 3 | victus | 41.882 | 1.869 | 0.169 | 0.042 |
| rotate90 | static_1d | 1 | 4 | victus | 37.215 | 1.320 | 0.191 | 0.038 |
| rotate90 | static_1d | 1 | 5 | victus | 36.985 | 2.729 | 0.192 | 0.032 |
| rotate90 | static_1d | 1 | 6 | victus | 34.062 | 3.210 | 0.208 | 0.030 |
| rotate90 | static_1d | 1 | 7 | victus | 30.007 | 1.665 | 0.237 | 0.030 |
| rotate90 | static_1d | 1 | 8 | victus | 31.263 | 0.618 | 0.227 | 0.025 |
| rotate90 | static_1d | 2 | 1 | victus | 68.818 | 4.161 | 0.103 | 0.034 |
| rotate90 | static_1d | 2 | 2 | victus | 54.438 | 1.336 | 0.130 | 0.033 |
| rotate90 | static_1d | 2 | 3 | victus | 49.542 | 0.578 | 0.143 | 0.029 |
| rotate90 | static_1d | 2 | 4 | victus | 48.179 | 0.450 | 0.147 | 0.025 |
| rotate90 | static_1d | 2 | 5 | victus | 45.229 | 0.803 | 0.157 | 0.022 |
| rotate90 | static_1d | 2 | 6 | victus | 45.160 | 2.842 | 0.157 | 0.020 |
| rotate90 | static_1d | 2 | 7 | victus | 41.709 | 0.987 | 0.170 | 0.019 |
| rotate90 | static_1d | 2 | 8 | victus | 40.545 | 0.947 | 0.175 | 0.018 |
| rotate90 | static_2d | 1 | 0 | HP-Laptop | 18.455 | 1.303 | 1.217 | 1.217 |
| rotate90 | static_2d | 2 | 0 | HP-Laptop | 21.056 | 2.092 | 1.067 | 0.533 |
| rotate90 | static_2d | 0 | 1 | victus | 10.551 | 1.062 | 0.673 | 0.673 |
| rotate90 | static_2d | 0 | 2 | victus | 9.078 | 0.386 | 0.782 | 0.391 |
| rotate90 | static_2d | 0 | 3 | victus | 6.732 | 1.040 | 1.054 | 0.351 |
| rotate90 | static_2d | 0 | 4 | victus | 6.530 | 0.123 | 1.087 | 0.272 |
| rotate90 | static_2d | 0 | 5 | victus | 6.294 | 0.438 | 1.128 | 0.226 |
| rotate90 | static_2d | 0 | 6 | victus | 8.529 | 2.728 | 0.832 | 0.139 |
| rotate90 | static_2d | 0 | 7 | victus | 6.412 | 0.770 | 1.107 | 0.158 |
| rotate90 | static_2d | 0 | 8 | victus | 7.281 | 0.142 | 0.975 | 0.122 |
| rotate90 | static_2d | 1 | 1 | victus | 59.998 | 1.423 | 0.118 | 0.059 |
| rotate90 | static_2d | 1 | 2 | victus | 48.637 | 1.183 | 0.146 | 0.049 |
| rotate90 | static_2d | 1 | 3 | victus | 41.535 | 0.473 | 0.171 | 0.043 |
| rotate90 | static_2d | 1 | 4 | victus | 39.671 | 1.298 | 0.179 | 0.036 |
| rotate90 | static_2d | 1 | 5 | victus | 36.759 | 3.697 | 0.193 | 0.032 |
| rotate90 | static_2d | 1 | 6 | victus | 31.935 | 0.774 | 0.222 | 0.032 |
| rotate90 | static_2d | 1 | 7 | victus | 31.901 | 0.984 | 0.223 | 0.028 |
| rotate90 | static_2d | 1 | 8 | victus | 29.928 | 2.721 | 0.237 | 0.026 |
| rotate90 | static_2d | 2 | 1 | victus | 72.033 | 0.953 | 0.099 | 0.033 |
| rotate90 | static_2d | 2 | 2 | victus | 61.526 | 10.792 | 0.115 | 0.029 |
| rotate90 | static_2d | 2 | 3 | victus | 49.641 | 0.574 | 0.143 | 0.029 |
| rotate90 | static_2d | 2 | 4 | victus | 54.803 | 10.741 | 0.130 | 0.022 |
| rotate90 | static_2d | 2 | 5 | victus | 45.413 | 0.228 | 0.156 | 0.022 |
| rotate90 | static_2d | 2 | 6 | victus | 43.734 | 1.235 | 0.162 | 0.020 |
| rotate90 | static_2d | 2 | 7 | victus | 42.494 | 0.739 | 0.167 | 0.019 |
| rotate90 | static_2d | 2 | 8 | victus | 40.424 | 0.251 | 0.176 | 0.018 |
| rotate90 | dynamic_1d | 1 | 0 | HP-Laptop | 30.649 | 9.687 | 0.733 | 0.733 |
| rotate90 | dynamic_1d | 2 | 0 | HP-Laptop | 13.800 | 0.993 | 1.627 | 0.814 |
| rotate90 | dynamic_1d | 0 | 1 | victus | 9.697 | 0.095 | 0.732 | 0.732 |
| rotate90 | dynamic_1d | 0 | 2 | victus | 5.509 | 0.064 | 1.289 | 0.644 |
| rotate90 | dynamic_1d | 0 | 3 | victus | 5.612 | 0.275 | 1.265 | 0.422 |
| rotate90 | dynamic_1d | 0 | 4 | victus | 5.186 | 0.200 | 1.369 | 0.342 |
| rotate90 | dynamic_1d | 0 | 5 | victus | 5.631 | 0.315 | 1.261 | 0.252 |
| rotate90 | dynamic_1d | 0 | 6 | victus | 5.065 | 0.443 | 1.401 | 0.234 |
| rotate90 | dynamic_1d | 0 | 7 | victus | 4.557 | 0.150 | 1.558 | 0.223 |
| rotate90 | dynamic_1d | 0 | 8 | victus | 5.405 | 0.099 | 1.313 | 0.164 |
| rotate90 | dynamic_1d | 1 | 1 | victus | 34.715 | 0.692 | 0.204 | 0.102 |
| rotate90 | dynamic_1d | 1 | 2 | victus | 27.799 | 0.911 | 0.255 | 0.085 |
| rotate90 | dynamic_1d | 1 | 3 | victus | 26.779 | 0.333 | 0.265 | 0.066 |
| rotate90 | dynamic_1d | 1 | 4 | victus | 27.506 | 1.290 | 0.258 | 0.052 |
| rotate90 | dynamic_1d | 1 | 5 | victus | 26.608 | 1.172 | 0.267 | 0.044 |
| rotate90 | dynamic_1d | 1 | 6 | victus | 25.896 | 1.105 | 0.274 | 0.039 |
| rotate90 | dynamic_1d | 1 | 7 | victus | 26.090 | 1.245 | 0.272 | 0.034 |
| rotate90 | dynamic_1d | 1 | 8 | victus | 27.021 | 1.846 | 0.263 | 0.029 |
| rotate90 | dynamic_1d | 2 | 1 | victus | 65.848 | 6.638 | 0.108 | 0.036 |
| rotate90 | dynamic_1d | 2 | 2 | victus | 61.728 | 0.999 | 0.115 | 0.029 |
| rotate90 | dynamic_1d | 2 | 3 | victus | 57.084 | 1.881 | 0.124 | 0.025 |
| rotate90 | dynamic_1d | 2 | 4 | victus | 52.308 | 0.712 | 0.136 | 0.023 |
| rotate90 | dynamic_1d | 2 | 5 | victus | 47.623 | 4.579 | 0.149 | 0.021 |
| rotate90 | dynamic_1d | 2 | 6 | victus | 54.123 | 11.651 | 0.131 | 0.016 |
| rotate90 | dynamic_1d | 2 | 7 | victus | 45.122 | 0.994 | 0.157 | 0.017 |
| rotate90 | dynamic_1d | 2 | 8 | victus | 50.427 | 11.047 | 0.141 | 0.014 |
| grayscale,blur,flip | static_1d | 1 | 0 | HP-Laptop | 160.721 | 15.611 | 0.952 | 0.952 |
| grayscale,blur,flip | static_1d | 2 | 0 | HP-Laptop | 198.331 | 19.096 | 0.771 | 0.386 |
| grayscale,blur,flip | static_1d | 0 | 1 | victus | 131.698 | 9.521 | 0.903 | 0.903 |
| grayscale,blur,flip | static_1d | 0 | 2 | victus | 67.659 | 1.929 | 1.758 | 0.879 |
| grayscale,blur,flip | static_1d | 0 | 3 | victus | 50.877 | 3.922 | 2.338 | 0.779 |
| grayscale,blur,flip | static_1d | 0 | 4 | victus | 38.571 | 0.926 | 3.084 | 0.771 |
| grayscale,blur,flip | static_1d | 0 | 5 | victus | 33.877 | 0.512 | 3.512 | 0.702 |
| grayscale,blur,flip | static_1d | 0 | 6 | victus | 31.034 | 0.183 | 3.833 | 0.639 |
| grayscale,blur,flip | static_1d | 0 | 7 | victus | 34.858 | 5.543 | 3.413 | 0.488 |
| grayscale,blur,flip | static_1d | 0 | 8 | victus | 33.793 | 7.388 | 3.520 | 0.440 |
| grayscale,blur,flip | static_1d | 1 | 1 | victus | 198.591 | 3.391 | 0.599 | 0.300 |
| grayscale,blur,flip | static_1d | 1 | 2 | victus | 142.822 | 1.952 | 0.833 | 0.278 |
| grayscale,blur,flip | static_1d | 1 | 3 | victus | 112.298 | 0.885 | 1.059 | 0.265 |
| grayscale,blur,flip | static_1d | 1 | 4 | victus | 97.005 | 1.870 | 1.226 | 0.245 |
| grayscale,blur,flip | static_1d | 1 | 5 | victus | 86.645 | 2.630 | 1.373 | 0.229 |
| grayscale,blur,flip | static_1d | 1 | 6 | victus | 77.652 | 4.395 | 1.532 | 0.219 |
| grayscale,blur,flip | static_1d | 1 | 7 | victus | 70.230 | 3.136 | 1.694 | 0.212 |
| grayscale,blur,flip | static_1d | 1 | 8 | victus | 63.839 | 2.075 | 1.863 | 0.207 |
| grayscale,blur,flip | static_1d | 2 | 1 | victus | 201.785 | 1.492 | 0.590 | 0.197 |
| grayscale,blur,flip | static_1d | 2 | 2 | victus | 153.914 | 3.530 | 0.773 | 0.193 |
| grayscale,blur,flip | static_1d | 2 | 3 | victus | 131.942 | 0.708 | 0.902 | 0.180 |
| grayscale,blur,flip | static_1d | 2 | 4 | victus | 115.475 | 1.761 | 1.030 | 0.172 |
| grayscale,blur,flip | static_1d | 2 | 5 | victus | 105.716 | 0.799 | 1.125 | 0.161 |
| grayscale,blur,flip | static_1d | 2 | 6 | victus | 99.814 | 8.144 | 1.192 | 0.149 |
| grayscale,blur,flip | static_1d | 2 | 7 | victus | 88.853 | 3.497 | 1.339 | 0.149 |
| grayscale,blur,flip | static_1d | 2 | 8 | victus | 82.358 | 0.573 | 1.444 | 0.144 |
| grayscale,blur,flip | static_2d | 1 | 0 | HP-Laptop | 149.994 | 3.263 | 1.020 | 1.020 |
| grayscale,blur,flip | static_2d | 2 | 0 | HP-Laptop | 197.484 | 27.881 | 0.774 | 0.387 |
| grayscale,blur,flip | static_2d | 0 | 1 | victus | 126.882 | 0.545 | 0.938 | 0.938 |
| grayscale,blur,flip | static_2d | 0 | 2 | victus | 68.116 | 2.351 | 1.746 | 0.873 |
| grayscale,blur,flip | static_2d | 0 | 3 | victus | 48.896 | 2.120 | 2.433 | 0.811 |
| grayscale,blur,flip | static_2d | 0 | 4 | victus | 42.289 | 0.760 | 2.813 | 0.703 |
| grayscale,blur,flip | static_2d | 0 | 5 | victus | 33.892 | 0.718 | 3.510 | 0.702 |
| grayscale,blur,flip | static_2d | 0 | 6 | victus | 36.352 | 4.338 | 3.272 | 0.545 |
| grayscale,blur,flip | static_2d | 0 | 7 | victus | 28.071 | 0.152 | 4.238 | 0.605 |
| grayscale,blur,flip | static_2d | 0 | 8 | victus | 35.569 | 7.761 | 3.344 | 0.418 |
| grayscale,blur,flip | static_2d | 1 | 1 | victus | 198.907 | 3.028 | 0.598 | 0.299 |
| grayscale,blur,flip | static_2d | 1 | 2 | victus | 141.050 | 0.278 | 0.843 | 0.281 |
| grayscale,blur,flip | static_2d | 1 | 3 | victus | 115.249 | 2.035 | 1.032 | 0.258 |
| grayscale,blur,flip | static_2d | 1 | 4 | victus | 97.102 | 2.774 | 1.225 | 0.245 |
| grayscale,blur,flip | static_2d | 1 | 5 | victus | 88.254 | 3.286 | 1.348 | 0.225 |
| grayscale,blur,flip | static_2d | 1 | 6 | victus | 76.946 | 1.261 | 1.546 | 0.221 |
| grayscale,blur,flip | static_2d | 1 | 7 | victus | 73.842 | 0.836 | 1.611 | 0.201 |
| grayscale,blur,flip | static_2d | 1 | 8 | victus | 69.570 | 4.551 | 1.710 | 0.190 |
| grayscale,blur,flip | static_2d | 2 | 1 | victus | 199.060 | 2.963 | 0.598 | 0.199 |
| grayscale,blur,flip | static_2d | 2 | 2 | victus | 160.095 | 4.952 | 0.743 | 0.186 |
| grayscale,blur,flip | static_2d | 2 | 3 | victus | 129.921 | 1.902 | 0.916 | 0.183 |
| grayscale,blur,flip | static_2d | 2 | 4 | victus | 121.472 | 4.510 | 0.979 | 0.163 |
| grayscale,blur,flip | static_2d | 2 | 5 | victus | 104.337 | 0.646 | 1.140 | 0.163 |
| grayscale,blur,flip | static_2d | 2 | 6 | victus | 98.517 | 2.093 | 1.207 | 0.151 |
| grayscale,blur,flip | static_2d | 2 | 7 | victus | 89.478 | 0.880 | 1.329 | 0.148 |
| grayscale,blur,flip | static_2d | 2 | 8 | victus | 85.199 | 1.178 | 1.396 | 0.140 |
| grayscale,blur,flip | dynamic_1d | 1 | 0 | HP-Laptop | 147.830 | 11.032 | 1.035 | 1.035 |
| grayscale,blur,flip | dynamic_1d | 2 | 0 | HP-Laptop | 163.049 | 10.148 | 0.938 | 0.469 |
| grayscale,blur,flip | dynamic_1d | 0 | 1 | victus | 127.476 | 2.068 | 0.933 | 0.933 |
| grayscale,blur,flip | dynamic_1d | 0 | 2 | victus | 64.835 | 1.183 | 1.835 | 0.917 |
| grayscale,blur,flip | dynamic_1d | 0 | 3 | victus | 46.150 | 0.780 | 2.578 | 0.859 |
| grayscale,blur,flip | dynamic_1d | 0 | 4 | victus | 38.800 | 0.243 | 3.066 | 0.766 |
| grayscale,blur,flip | dynamic_1d | 0 | 5 | victus | 32.138 | 0.269 | 3.701 | 0.740 |
| grayscale,blur,flip | dynamic_1d | 0 | 6 | victus | 27.429 | 0.236 | 4.337 | 0.723 |
| grayscale,blur,flip | dynamic_1d | 0 | 7 | victus | 27.093 | 4.458 | 4.391 | 0.627 |
| grayscale,blur,flip | dynamic_1d | 0 | 8 | victus | 23.181 | 0.773 | 5.132 | 0.641 |
| grayscale,blur,flip | dynamic_1d | 1 | 1 | victus | 154.261 | 51.286 | 0.771 | 0.386 |
| grayscale,blur,flip | dynamic_1d | 1 | 2 | victus | 85.097 | 3.640 | 1.398 | 0.466 |
| grayscale,blur,flip | dynamic_1d | 1 | 3 | victus | 82.745 | 25.895 | 1.438 | 0.359 |
| grayscale,blur,flip | dynamic_1d | 1 | 4 | victus | 59.479 | 0.922 | 2.000 | 0.400 |
| grayscale,blur,flip | dynamic_1d | 1 | 5 | victus | 58.272 | 9.620 | 2.041 | 0.340 |
| grayscale,blur,flip | dynamic_1d | 1 | 6 | victus | 50.408 | 0.242 | 2.360 | 0.337 |
| grayscale,blur,flip | dynamic_1d | 1 | 7 | victus | 49.717 | 3.057 | 2.393 | 0.299 |
| grayscale,blur,flip | dynamic_1d | 1 | 8 | victus | 46.339 | 0.747 | 2.567 | 0.285 |
| grayscale,blur,flip | dynamic_1d | 2 | 1 | victus | 176.825 | 2.415 | 0.673 | 0.224 |
| grayscale,blur,flip | dynamic_1d | 2 | 2 | victus | 153.738 | 23.906 | 0.774 | 0.193 |
| grayscale,blur,flip | dynamic_1d | 2 | 3 | victus | 120.453 | 1.229 | 0.988 | 0.198 |
| grayscale,blur,flip | dynamic_1d | 2 | 4 | victus | 146.221 | 42.331 | 0.814 | 0.136 |
| grayscale,blur,flip | dynamic_1d | 2 | 5 | victus | 114.172 | 20.936 | 1.042 | 0.149 |
| grayscale,blur,flip | dynamic_1d | 2 | 6 | victus | 158.214 | 50.767 | 0.752 | 0.094 |
| grayscale,blur,flip | dynamic_1d | 2 | 7 | victus | 97.774 | 28.213 | 1.217 | 0.135 |
| grayscale,blur,flip | dynamic_1d | 2 | 8 | victus | 152.663 | 119.880 | 0.779 | 0.078 |
