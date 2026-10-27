# Studiu pe două calculatoare, 4MP

Imaginea `test_images/sample_4MP.ppm` are 2400×1600 pixeli. Rezultatele sunt separate de studiile anterioare.

## Metodologie

Am măsurat 320 de configurații, cu câte 3 repetări, în total 960 de rulări măsurate. Operațiile sunt grayscale, blur 9×9, rotate90 și pipeline-ul grayscale,blur,flip. Strategiile sunt static_1d, static_2d și dynamic_1d.

HP-Laptop are un Intel Core i7-7500U, cu 2 nuclee și 4 fire hardware. Victus are un Intel Core i5-12500H și 16 fire hardware. Am folosit Open MPI 4.1.6, compilare `mpicc -O3 -Wall` și `--bind-to none`. Procesele rulează fără fixare pe nuclee. Coordonatorul este un proces suplimentar față de numărul de workeri.

Rangul 0 rulează pe HP-Laptop pentru testele exclusiv pe HP-Laptop și pe Victus pentru celelalte teste. Graficul HP-Laptop include 1 proces secvențial, 2 procese cu un worker și 3 procese cu doi workeri. Rangurile 1 până la numărul de workeri HP-Laptop rulează pe HP-Laptop, iar workerii rămași rulează pe Victus. Limitele de 2 și 8 se referă la workeri, fără coordonator.

Speedup = media timpului secvențial / media timpului paralel. Referința secvențială rulează pe HP-Laptop pentru testele exclusiv pe HP-Laptop și pe Victus pentru celelalte teste. Eficiența este speedup / numărul total de workeri. Pe calculatoare diferite, acest raport depinde de performanța referinței secvențiale.

Timpii provin din instrumentarea C și exclud lansarea MPI, citirea imaginii, scrierea rezultatului și verificarea pixelilor. Prima repetare a fiecărei configurații salvează rezultatul pentru comparație integrală cu referința secvențială. Celelalte repetări folosesc ieșirea NONE. Timpii sunt afișați ca medie și abatere standard. Trei repetări oferă o verificare pilot, cu precizie limitată pentru operațiile scurte.

Toate graficele de timp folosesc aceeași limită verticală, inclusiv graficele strategiilor. Graficele de speedup folosesc o limită comună. Valorile extreme ridică limita verticală, astfel că unele curbe și bare sunt aproape de zero pe această scară. Tabelele păstrează valorile numerice. Datele brute includ timpii fiecărui worker, distribuția pe calculatoare și datele necesare eficienței. Suita măsoară aceleași configurații la 1.5MP, 4MP și 8MP. Datele pentru eficiență și variația cu rezoluția sunt în CSV-urile fiecărei rezoluții.

## grayscale

![Timp total (ms), grayscale](benchmark_two_machines/4MP/execution_time_grayscale.png)

![Speedup, grayscale](benchmark_two_machines/4MP/speedup_grayscale.png)

![Strategii, grayscale](benchmark_two_machines/4MP/partition_strategies_grayscale.png)

Cel mai mic timp paralel mediu este 11.893 ms, cu static_2d, 0 workeri HP-Laptop și 5 workeri Victus. Speedup față de referința de pe victus este 1.11.

## blur

![Timp total (ms), blur](benchmark_two_machines/4MP/execution_time_blur.png)

![Speedup, blur](benchmark_two_machines/4MP/speedup_blur.png)

![Strategii, blur](benchmark_two_machines/4MP/partition_strategies_blur.png)

Cel mai mic timp paralel mediu este 48.776 ms, cu dynamic_1d, 0 workeri HP-Laptop și 8 workeri Victus. Speedup față de referința de pe victus este 5.94.

## rotate90

![Timp total (ms), rotate90](benchmark_two_machines/4MP/execution_time_rotate90.png)

![Speedup, rotate90](benchmark_two_machines/4MP/speedup_rotate90.png)

![Strategii, rotate90](benchmark_two_machines/4MP/partition_strategies_rotate90.png)

Cel mai mic timp paralel mediu este 12.824 ms, cu dynamic_1d, 0 workeri HP-Laptop și 3 workeri Victus. Speedup față de referința de pe victus este 1.22.

## grayscale,blur,flip

![Timp total (ms), grayscale,blur,flip](benchmark_two_machines/4MP/execution_time_grayscale_blur_flip.png)

![Speedup, grayscale,blur,flip](benchmark_two_machines/4MP/speedup_grayscale_blur_flip.png)

![Strategii, grayscale,blur,flip](benchmark_two_machines/4MP/partition_strategies_grayscale_blur_flip.png)

Cel mai mic timp paralel mediu este 66.473 ms, cu dynamic_1d, 0 workeri HP-Laptop și 8 workeri Victus. Speedup față de referința de pe victus este 4.72.

## Verificare și interpretare

Cea mai lentă repetare a durat 507.170 ms, pentru grayscale,blur,flip, static_2d, cu 2 workeri HP-Laptop și 0 workeri Victus. Cea mai mare abatere standard relativă este 54.1%, pentru grayscale, dynamic_1d, HP=1, Victus=8. Am păstrat toate repetările. Acest pilot verifică matricea și graficele, dar variația limitează concluziile despre ordinea strategiilor. Nu am măsurat separat rețeaua sau încărcarea de fond, deci nu pot atribui variația unei singure cauze.

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

Datele sunt în [results.csv](benchmark_two_machines/4MP/results.csv), [runs.csv](benchmark_two_machines/4MP/runs.csv) și [runs.jsonl](benchmark_two_machines/4MP/runs.jsonl). Fișierul [metadata.json](benchmark_two_machines/4MP/metadata.json) păstrează informațiile calculatoarelor și hash-urile imaginii și sursei. Câmpurile hp și victus reprezintă numărul de workeri. În CSV, modul seq are zero workeri și coloana coordinator identifică laptopul. În jurnalul JSONL, hp=1 selectează referința secvențială HP-Laptop, iar hp=0 selectează Victus.

| Operație | Strategie | HP workeri | Victus workeri | Coordonator | Total ms | Abatere ms | Speedup | Eficiență |
| --- | --- | ---: | ---: | --- | ---: | ---: | ---: | ---: |
| grayscale | seq | 0 | 0 | HP-Laptop | 26.390 | 0.214 | 1.000 | 1.000 |
| grayscale | seq | 0 | 0 | victus | 13.233 | 0.073 | 1.000 | 1.000 |
| blur | seq | 0 | 0 | HP-Laptop | 318.071 | 1.794 | 1.000 | 1.000 |
| blur | seq | 0 | 0 | victus | 289.828 | 8.464 | 1.000 | 1.000 |
| rotate90 | seq | 0 | 0 | HP-Laptop | 33.367 | 2.038 | 1.000 | 1.000 |
| rotate90 | seq | 0 | 0 | victus | 15.706 | 0.198 | 1.000 | 1.000 |
| grayscale,blur,flip | seq | 0 | 0 | HP-Laptop | 347.422 | 1.033 | 1.000 | 1.000 |
| grayscale,blur,flip | seq | 0 | 0 | victus | 313.910 | 5.079 | 1.000 | 1.000 |
| grayscale | static_1d | 1 | 0 | HP-Laptop | 33.446 | 1.140 | 0.789 | 0.789 |
| grayscale | static_1d | 2 | 0 | HP-Laptop | 36.166 | 7.448 | 0.730 | 0.365 |
| grayscale | static_1d | 0 | 1 | victus | 23.953 | 0.570 | 0.552 | 0.552 |
| grayscale | static_1d | 0 | 2 | victus | 16.654 | 1.780 | 0.795 | 0.397 |
| grayscale | static_1d | 0 | 3 | victus | 13.342 | 1.082 | 0.992 | 0.331 |
| grayscale | static_1d | 0 | 4 | victus | 13.424 | 1.558 | 0.986 | 0.246 |
| grayscale | static_1d | 0 | 5 | victus | 12.418 | 0.631 | 1.066 | 0.213 |
| grayscale | static_1d | 0 | 6 | victus | 12.907 | 0.518 | 1.025 | 0.171 |
| grayscale | static_1d | 0 | 7 | victus | 13.094 | 0.139 | 1.011 | 0.144 |
| grayscale | static_1d | 0 | 8 | victus | 13.425 | 0.215 | 0.986 | 0.123 |
| grayscale | static_1d | 1 | 1 | victus | 123.072 | 0.284 | 0.108 | 0.054 |
| grayscale | static_1d | 1 | 2 | victus | 89.234 | 0.884 | 0.148 | 0.049 |
| grayscale | static_1d | 1 | 3 | victus | 72.956 | 1.649 | 0.181 | 0.045 |
| grayscale | static_1d | 1 | 4 | victus | 63.230 | 0.716 | 0.209 | 0.042 |
| grayscale | static_1d | 1 | 5 | victus | 57.242 | 2.493 | 0.231 | 0.039 |
| grayscale | static_1d | 1 | 6 | victus | 52.331 | 1.433 | 0.253 | 0.036 |
| grayscale | static_1d | 1 | 7 | victus | 48.484 | 3.398 | 0.273 | 0.034 |
| grayscale | static_1d | 1 | 8 | victus | 44.522 | 2.200 | 0.297 | 0.033 |
| grayscale | static_1d | 2 | 1 | victus | 144.184 | 0.761 | 0.092 | 0.031 |
| grayscale | static_1d | 2 | 2 | victus | 115.338 | 4.166 | 0.115 | 0.029 |
| grayscale | static_1d | 2 | 3 | victus | 94.436 | 1.272 | 0.140 | 0.028 |
| grayscale | static_1d | 2 | 4 | victus | 86.193 | 1.063 | 0.154 | 0.026 |
| grayscale | static_1d | 2 | 5 | victus | 81.322 | 0.758 | 0.163 | 0.023 |
| grayscale | static_1d | 2 | 6 | victus | 68.949 | 4.307 | 0.192 | 0.024 |
| grayscale | static_1d | 2 | 7 | victus | 63.099 | 3.067 | 0.210 | 0.023 |
| grayscale | static_1d | 2 | 8 | victus | 62.243 | 4.227 | 0.213 | 0.021 |
| grayscale | static_2d | 1 | 0 | HP-Laptop | 33.109 | 3.665 | 0.797 | 0.797 |
| grayscale | static_2d | 2 | 0 | HP-Laptop | 40.220 | 7.075 | 0.656 | 0.328 |
| grayscale | static_2d | 0 | 1 | victus | 24.880 | 2.124 | 0.532 | 0.532 |
| grayscale | static_2d | 0 | 2 | victus | 15.194 | 0.607 | 0.871 | 0.435 |
| grayscale | static_2d | 0 | 3 | victus | 13.542 | 1.476 | 0.977 | 0.326 |
| grayscale | static_2d | 0 | 4 | victus | 17.554 | 1.067 | 0.754 | 0.188 |
| grayscale | static_2d | 0 | 5 | victus | 11.893 | 0.809 | 1.113 | 0.223 |
| grayscale | static_2d | 0 | 6 | victus | 17.333 | 0.959 | 0.763 | 0.127 |
| grayscale | static_2d | 0 | 7 | victus | 15.774 | 4.300 | 0.839 | 0.120 |
| grayscale | static_2d | 0 | 8 | victus | 15.887 | 1.114 | 0.833 | 0.104 |
| grayscale | static_2d | 1 | 1 | victus | 124.467 | 1.015 | 0.106 | 0.053 |
| grayscale | static_2d | 1 | 2 | victus | 88.697 | 0.792 | 0.149 | 0.050 |
| grayscale | static_2d | 1 | 3 | victus | 75.070 | 1.202 | 0.176 | 0.044 |
| grayscale | static_2d | 1 | 4 | victus | 62.339 | 1.836 | 0.212 | 0.042 |
| grayscale | static_2d | 1 | 5 | victus | 66.065 | 10.059 | 0.200 | 0.033 |
| grayscale | static_2d | 1 | 6 | victus | 51.470 | 0.998 | 0.257 | 0.037 |
| grayscale | static_2d | 1 | 7 | victus | 54.566 | 4.202 | 0.243 | 0.030 |
| grayscale | static_2d | 1 | 8 | victus | 47.160 | 1.383 | 0.281 | 0.031 |
| grayscale | static_2d | 2 | 1 | victus | 143.495 | 1.590 | 0.092 | 0.031 |
| grayscale | static_2d | 2 | 2 | victus | 122.945 | 7.982 | 0.108 | 0.027 |
| grayscale | static_2d | 2 | 3 | victus | 94.887 | 0.418 | 0.139 | 0.028 |
| grayscale | static_2d | 2 | 4 | victus | 90.768 | 0.889 | 0.146 | 0.024 |
| grayscale | static_2d | 2 | 5 | victus | 79.380 | 0.606 | 0.167 | 0.024 |
| grayscale | static_2d | 2 | 6 | victus | 77.354 | 1.444 | 0.171 | 0.021 |
| grayscale | static_2d | 2 | 7 | victus | 73.131 | 9.364 | 0.181 | 0.020 |
| grayscale | static_2d | 2 | 8 | victus | 61.374 | 2.495 | 0.216 | 0.022 |
| grayscale | dynamic_1d | 1 | 0 | HP-Laptop | 35.020 | 1.568 | 0.754 | 0.754 |
| grayscale | dynamic_1d | 2 | 0 | HP-Laptop | 30.605 | 4.654 | 0.862 | 0.431 |
| grayscale | dynamic_1d | 0 | 1 | victus | 25.027 | 0.582 | 0.529 | 0.529 |
| grayscale | dynamic_1d | 0 | 2 | victus | 14.517 | 1.285 | 0.912 | 0.456 |
| grayscale | dynamic_1d | 0 | 3 | victus | 13.190 | 1.578 | 1.003 | 0.334 |
| grayscale | dynamic_1d | 0 | 4 | victus | 12.525 | 0.299 | 1.056 | 0.264 |
| grayscale | dynamic_1d | 0 | 5 | victus | 13.097 | 0.298 | 1.010 | 0.202 |
| grayscale | dynamic_1d | 0 | 6 | victus | 13.696 | 0.843 | 0.966 | 0.161 |
| grayscale | dynamic_1d | 0 | 7 | victus | 13.108 | 0.082 | 1.010 | 0.144 |
| grayscale | dynamic_1d | 0 | 8 | victus | 18.832 | 5.008 | 0.703 | 0.088 |
| grayscale | dynamic_1d | 1 | 1 | victus | 59.182 | 9.305 | 0.224 | 0.112 |
| grayscale | dynamic_1d | 1 | 2 | victus | 41.047 | 0.832 | 0.322 | 0.107 |
| grayscale | dynamic_1d | 1 | 3 | victus | 39.890 | 4.273 | 0.332 | 0.083 |
| grayscale | dynamic_1d | 1 | 4 | victus | 37.865 | 1.799 | 0.349 | 0.070 |
| grayscale | dynamic_1d | 1 | 5 | victus | 43.666 | 9.383 | 0.303 | 0.051 |
| grayscale | dynamic_1d | 1 | 6 | victus | 38.310 | 1.603 | 0.345 | 0.049 |
| grayscale | dynamic_1d | 1 | 7 | victus | 35.727 | 1.055 | 0.370 | 0.046 |
| grayscale | dynamic_1d | 1 | 8 | victus | 51.861 | 28.046 | 0.255 | 0.028 |
| grayscale | dynamic_1d | 2 | 1 | victus | 105.569 | 1.653 | 0.125 | 0.042 |
| grayscale | dynamic_1d | 2 | 2 | victus | 110.263 | 28.948 | 0.120 | 0.030 |
| grayscale | dynamic_1d | 2 | 3 | victus | 157.405 | 60.201 | 0.084 | 0.017 |
| grayscale | dynamic_1d | 2 | 4 | victus | 110.560 | 27.052 | 0.120 | 0.020 |
| grayscale | dynamic_1d | 2 | 5 | victus | 75.834 | 1.123 | 0.174 | 0.025 |
| grayscale | dynamic_1d | 2 | 6 | victus | 72.614 | 0.809 | 0.182 | 0.023 |
| grayscale | dynamic_1d | 2 | 7 | victus | 65.017 | 2.721 | 0.204 | 0.023 |
| grayscale | dynamic_1d | 2 | 8 | victus | 104.450 | 41.219 | 0.127 | 0.013 |
| blur | static_1d | 1 | 0 | HP-Laptop | 342.255 | 34.541 | 0.929 | 0.929 |
| blur | static_1d | 2 | 0 | HP-Laptop | 391.202 | 61.757 | 0.813 | 0.407 |
| blur | static_1d | 0 | 1 | victus | 295.384 | 1.528 | 0.981 | 0.981 |
| blur | static_1d | 0 | 2 | victus | 151.726 | 0.694 | 1.910 | 0.955 |
| blur | static_1d | 0 | 3 | victus | 106.164 | 4.011 | 2.730 | 0.910 |
| blur | static_1d | 0 | 4 | victus | 84.180 | 3.332 | 3.443 | 0.861 |
| blur | static_1d | 0 | 5 | victus | 69.802 | 0.943 | 4.152 | 0.830 |
| blur | static_1d | 0 | 6 | victus | 59.422 | 0.334 | 4.877 | 0.813 |
| blur | static_1d | 0 | 7 | victus | 51.852 | 0.481 | 5.590 | 0.799 |
| blur | static_1d | 0 | 8 | victus | 53.058 | 5.932 | 5.462 | 0.683 |
| blur | static_1d | 1 | 1 | victus | 268.355 | 1.414 | 1.080 | 0.540 |
| blur | static_1d | 1 | 2 | victus | 186.261 | 0.465 | 1.556 | 0.519 |
| blur | static_1d | 1 | 3 | victus | 146.149 | 0.356 | 1.983 | 0.496 |
| blur | static_1d | 1 | 4 | victus | 120.489 | 0.979 | 2.405 | 0.481 |
| blur | static_1d | 1 | 5 | victus | 106.228 | 1.928 | 2.728 | 0.455 |
| blur | static_1d | 1 | 6 | victus | 94.047 | 3.908 | 3.082 | 0.440 |
| blur | static_1d | 1 | 7 | victus | 85.934 | 3.748 | 3.373 | 0.422 |
| blur | static_1d | 1 | 8 | victus | 77.219 | 6.035 | 3.753 | 0.417 |
| blur | static_1d | 2 | 1 | victus | 225.667 | 5.083 | 1.284 | 0.428 |
| blur | static_1d | 2 | 2 | victus | 176.865 | 4.494 | 1.639 | 0.410 |
| blur | static_1d | 2 | 3 | victus | 142.465 | 0.610 | 2.034 | 0.407 |
| blur | static_1d | 2 | 4 | victus | 127.095 | 3.551 | 2.280 | 0.380 |
| blur | static_1d | 2 | 5 | victus | 112.266 | 3.784 | 2.582 | 0.369 |
| blur | static_1d | 2 | 6 | victus | 103.885 | 2.640 | 2.790 | 0.349 |
| blur | static_1d | 2 | 7 | victus | 91.667 | 3.375 | 3.162 | 0.351 |
| blur | static_1d | 2 | 8 | victus | 81.946 | 1.234 | 3.537 | 0.354 |
| blur | static_2d | 1 | 0 | HP-Laptop | 347.283 | 38.584 | 0.916 | 0.916 |
| blur | static_2d | 2 | 0 | HP-Laptop | 397.719 | 23.109 | 0.800 | 0.400 |
| blur | static_2d | 0 | 1 | victus | 297.073 | 0.568 | 0.976 | 0.976 |
| blur | static_2d | 0 | 2 | victus | 152.096 | 1.696 | 1.906 | 0.953 |
| blur | static_2d | 0 | 3 | victus | 104.924 | 2.204 | 2.762 | 0.921 |
| blur | static_2d | 0 | 4 | victus | 87.878 | 0.977 | 3.298 | 0.825 |
| blur | static_2d | 0 | 5 | victus | 69.604 | 0.582 | 4.164 | 0.833 |
| blur | static_2d | 0 | 6 | victus | 64.148 | 2.864 | 4.518 | 0.753 |
| blur | static_2d | 0 | 7 | victus | 54.195 | 3.564 | 5.348 | 0.764 |
| blur | static_2d | 0 | 8 | victus | 51.326 | 4.278 | 5.647 | 0.706 |
| blur | static_2d | 1 | 1 | victus | 268.347 | 1.273 | 1.080 | 0.540 |
| blur | static_2d | 1 | 2 | victus | 185.783 | 0.900 | 1.560 | 0.520 |
| blur | static_2d | 1 | 3 | victus | 148.417 | 0.939 | 1.953 | 0.488 |
| blur | static_2d | 1 | 4 | victus | 120.749 | 1.230 | 2.400 | 0.480 |
| blur | static_2d | 1 | 5 | victus | 108.767 | 2.167 | 2.665 | 0.444 |
| blur | static_2d | 1 | 6 | victus | 99.960 | 11.821 | 2.899 | 0.414 |
| blur | static_2d | 1 | 7 | victus | 89.153 | 1.298 | 3.251 | 0.406 |
| blur | static_2d | 1 | 8 | victus | 79.909 | 6.605 | 3.627 | 0.403 |
| blur | static_2d | 2 | 1 | victus | 222.651 | 4.139 | 1.302 | 0.434 |
| blur | static_2d | 2 | 2 | victus | 182.112 | 5.680 | 1.591 | 0.398 |
| blur | static_2d | 2 | 3 | victus | 142.970 | 1.116 | 2.027 | 0.405 |
| blur | static_2d | 2 | 4 | victus | 129.028 | 3.019 | 2.246 | 0.374 |
| blur | static_2d | 2 | 5 | victus | 114.025 | 3.590 | 2.542 | 0.363 |
| blur | static_2d | 2 | 6 | victus | 107.556 | 5.233 | 2.695 | 0.337 |
| blur | static_2d | 2 | 7 | victus | 93.794 | 3.905 | 3.090 | 0.343 |
| blur | static_2d | 2 | 8 | victus | 88.890 | 6.318 | 3.261 | 0.326 |
| blur | dynamic_1d | 1 | 0 | HP-Laptop | 335.853 | 15.758 | 0.947 | 0.947 |
| blur | dynamic_1d | 2 | 0 | HP-Laptop | 291.892 | 7.006 | 1.090 | 0.545 |
| blur | dynamic_1d | 0 | 1 | victus | 298.880 | 1.109 | 0.970 | 0.970 |
| blur | dynamic_1d | 0 | 2 | victus | 150.024 | 0.392 | 1.932 | 0.966 |
| blur | dynamic_1d | 0 | 3 | victus | 101.843 | 0.116 | 2.846 | 0.949 |
| blur | dynamic_1d | 0 | 4 | victus | 82.344 | 2.512 | 3.520 | 0.880 |
| blur | dynamic_1d | 0 | 5 | victus | 65.433 | 0.677 | 4.429 | 0.886 |
| blur | dynamic_1d | 0 | 6 | victus | 55.731 | 0.196 | 5.200 | 0.867 |
| blur | dynamic_1d | 0 | 7 | victus | 51.490 | 5.258 | 5.629 | 0.804 |
| blur | dynamic_1d | 0 | 8 | victus | 48.776 | 5.769 | 5.942 | 0.743 |
| blur | dynamic_1d | 1 | 1 | victus | 237.422 | 4.235 | 1.221 | 0.610 |
| blur | dynamic_1d | 1 | 2 | victus | 139.039 | 3.847 | 2.085 | 0.695 |
| blur | dynamic_1d | 1 | 3 | victus | 110.843 | 2.218 | 2.615 | 0.654 |
| blur | dynamic_1d | 1 | 4 | victus | 104.022 | 21.323 | 2.786 | 0.557 |
| blur | dynamic_1d | 1 | 5 | victus | 95.188 | 19.612 | 3.045 | 0.507 |
| blur | dynamic_1d | 1 | 6 | victus | 69.557 | 1.012 | 4.167 | 0.595 |
| blur | dynamic_1d | 1 | 7 | victus | 65.619 | 2.341 | 4.417 | 0.552 |
| blur | dynamic_1d | 1 | 8 | victus | 63.304 | 3.211 | 4.578 | 0.509 |
| blur | dynamic_1d | 2 | 1 | victus | 191.653 | 23.865 | 1.512 | 0.504 |
| blur | dynamic_1d | 2 | 2 | victus | 141.181 | 4.006 | 2.053 | 0.513 |
| blur | dynamic_1d | 2 | 3 | victus | 111.662 | 3.780 | 2.596 | 0.519 |
| blur | dynamic_1d | 2 | 4 | victus | 95.217 | 3.326 | 3.044 | 0.507 |
| blur | dynamic_1d | 2 | 5 | victus | 85.463 | 4.100 | 3.391 | 0.484 |
| blur | dynamic_1d | 2 | 6 | victus | 77.989 | 3.014 | 3.716 | 0.465 |
| blur | dynamic_1d | 2 | 7 | victus | 80.522 | 5.762 | 3.599 | 0.400 |
| blur | dynamic_1d | 2 | 8 | victus | 70.653 | 5.143 | 4.102 | 0.410 |
| rotate90 | static_1d | 1 | 0 | HP-Laptop | 38.965 | 5.400 | 0.856 | 0.856 |
| rotate90 | static_1d | 2 | 0 | HP-Laptop | 51.883 | 3.550 | 0.643 | 0.322 |
| rotate90 | static_1d | 0 | 1 | victus | 26.352 | 0.071 | 0.596 | 0.596 |
| rotate90 | static_1d | 0 | 2 | victus | 22.264 | 0.773 | 0.705 | 0.353 |
| rotate90 | static_1d | 0 | 3 | victus | 16.632 | 0.694 | 0.944 | 0.315 |
| rotate90 | static_1d | 0 | 4 | victus | 16.570 | 0.329 | 0.948 | 0.237 |
| rotate90 | static_1d | 0 | 5 | victus | 15.446 | 1.211 | 1.017 | 0.203 |
| rotate90 | static_1d | 0 | 6 | victus | 15.503 | 1.201 | 1.013 | 0.169 |
| rotate90 | static_1d | 0 | 7 | victus | 15.933 | 0.129 | 0.986 | 0.141 |
| rotate90 | static_1d | 0 | 8 | victus | 18.912 | 5.186 | 0.830 | 0.104 |
| rotate90 | static_1d | 1 | 1 | victus | 133.611 | 1.083 | 0.118 | 0.059 |
| rotate90 | static_1d | 1 | 2 | victus | 92.884 | 3.931 | 0.169 | 0.056 |
| rotate90 | static_1d | 1 | 3 | victus | 74.168 | 0.936 | 0.212 | 0.053 |
| rotate90 | static_1d | 1 | 4 | victus | 63.265 | 0.838 | 0.248 | 0.050 |
| rotate90 | static_1d | 1 | 5 | victus | 56.445 | 2.147 | 0.278 | 0.046 |
| rotate90 | static_1d | 1 | 6 | victus | 51.175 | 1.643 | 0.307 | 0.044 |
| rotate90 | static_1d | 1 | 7 | victus | 49.272 | 3.657 | 0.319 | 0.040 |
| rotate90 | static_1d | 1 | 8 | victus | 46.706 | 5.060 | 0.336 | 0.037 |
| rotate90 | static_1d | 2 | 1 | victus | 151.969 | 0.801 | 0.103 | 0.034 |
| rotate90 | static_1d | 2 | 2 | victus | 123.845 | 5.368 | 0.127 | 0.032 |
| rotate90 | static_1d | 2 | 3 | victus | 96.010 | 0.378 | 0.164 | 0.033 |
| rotate90 | static_1d | 2 | 4 | victus | 92.841 | 11.740 | 0.169 | 0.028 |
| rotate90 | static_1d | 2 | 5 | victus | 80.188 | 0.941 | 0.196 | 0.028 |
| rotate90 | static_1d | 2 | 6 | victus | 72.400 | 4.902 | 0.217 | 0.027 |
| rotate90 | static_1d | 2 | 7 | victus | 65.810 | 3.208 | 0.239 | 0.027 |
| rotate90 | static_1d | 2 | 8 | victus | 63.611 | 8.766 | 0.247 | 0.025 |
| rotate90 | static_2d | 1 | 0 | HP-Laptop | 39.702 | 3.626 | 0.840 | 0.840 |
| rotate90 | static_2d | 2 | 0 | HP-Laptop | 50.139 | 5.271 | 0.665 | 0.333 |
| rotate90 | static_2d | 0 | 1 | victus | 27.778 | 2.384 | 0.565 | 0.565 |
| rotate90 | static_2d | 0 | 2 | victus | 22.679 | 1.107 | 0.693 | 0.346 |
| rotate90 | static_2d | 0 | 3 | victus | 16.968 | 0.786 | 0.926 | 0.309 |
| rotate90 | static_2d | 0 | 4 | victus | 16.512 | 0.574 | 0.951 | 0.238 |
| rotate90 | static_2d | 0 | 5 | victus | 16.259 | 0.457 | 0.966 | 0.193 |
| rotate90 | static_2d | 0 | 6 | victus | 17.783 | 0.106 | 0.883 | 0.147 |
| rotate90 | static_2d | 0 | 7 | victus | 15.995 | 0.897 | 0.982 | 0.140 |
| rotate90 | static_2d | 0 | 8 | victus | 24.618 | 7.692 | 0.638 | 0.080 |
| rotate90 | static_2d | 1 | 1 | victus | 132.149 | 0.275 | 0.119 | 0.059 |
| rotate90 | static_2d | 1 | 2 | victus | 94.904 | 5.133 | 0.165 | 0.055 |
| rotate90 | static_2d | 1 | 3 | victus | 84.762 | 8.660 | 0.185 | 0.046 |
| rotate90 | static_2d | 1 | 4 | victus | 64.608 | 1.178 | 0.243 | 0.049 |
| rotate90 | static_2d | 1 | 5 | victus | 58.126 | 1.547 | 0.270 | 0.045 |
| rotate90 | static_2d | 1 | 6 | victus | 54.097 | 2.003 | 0.290 | 0.041 |
| rotate90 | static_2d | 1 | 7 | victus | 49.192 | 0.287 | 0.319 | 0.040 |
| rotate90 | static_2d | 1 | 8 | victus | 48.093 | 4.076 | 0.327 | 0.036 |
| rotate90 | static_2d | 2 | 1 | victus | 151.642 | 1.097 | 0.104 | 0.035 |
| rotate90 | static_2d | 2 | 2 | victus | 127.697 | 4.459 | 0.123 | 0.031 |
| rotate90 | static_2d | 2 | 3 | victus | 98.583 | 4.727 | 0.159 | 0.032 |
| rotate90 | static_2d | 2 | 4 | victus | 88.873 | 1.221 | 0.177 | 0.029 |
| rotate90 | static_2d | 2 | 5 | victus | 80.647 | 0.160 | 0.195 | 0.028 |
| rotate90 | static_2d | 2 | 6 | victus | 74.359 | 3.483 | 0.211 | 0.026 |
| rotate90 | static_2d | 2 | 7 | victus | 72.017 | 11.203 | 0.218 | 0.024 |
| rotate90 | static_2d | 2 | 8 | victus | 61.377 | 2.491 | 0.256 | 0.026 |
| rotate90 | dynamic_1d | 1 | 0 | HP-Laptop | 40.109 | 5.520 | 0.832 | 0.832 |
| rotate90 | dynamic_1d | 2 | 0 | HP-Laptop | 31.665 | 5.162 | 1.054 | 0.527 |
| rotate90 | dynamic_1d | 0 | 1 | victus | 26.222 | 1.229 | 0.599 | 0.599 |
| rotate90 | dynamic_1d | 0 | 2 | victus | 13.348 | 0.108 | 1.177 | 0.588 |
| rotate90 | dynamic_1d | 0 | 3 | victus | 12.824 | 0.595 | 1.225 | 0.408 |
| rotate90 | dynamic_1d | 0 | 4 | victus | 13.180 | 0.484 | 1.192 | 0.298 |
| rotate90 | dynamic_1d | 0 | 5 | victus | 13.309 | 0.896 | 1.180 | 0.236 |
| rotate90 | dynamic_1d | 0 | 6 | victus | 13.315 | 0.496 | 1.180 | 0.197 |
| rotate90 | dynamic_1d | 0 | 7 | victus | 13.826 | 0.806 | 1.136 | 0.162 |
| rotate90 | dynamic_1d | 0 | 8 | victus | 17.336 | 4.000 | 0.906 | 0.113 |
| rotate90 | dynamic_1d | 1 | 1 | victus | 64.254 | 10.166 | 0.244 | 0.122 |
| rotate90 | dynamic_1d | 1 | 2 | victus | 41.760 | 2.529 | 0.376 | 0.125 |
| rotate90 | dynamic_1d | 1 | 3 | victus | 39.157 | 4.878 | 0.401 | 0.100 |
| rotate90 | dynamic_1d | 1 | 4 | victus | 36.453 | 3.061 | 0.431 | 0.086 |
| rotate90 | dynamic_1d | 1 | 5 | victus | 37.605 | 2.867 | 0.418 | 0.070 |
| rotate90 | dynamic_1d | 1 | 6 | victus | 45.061 | 12.797 | 0.349 | 0.050 |
| rotate90 | dynamic_1d | 1 | 7 | victus | 37.567 | 1.044 | 0.418 | 0.052 |
| rotate90 | dynamic_1d | 1 | 8 | victus | 37.227 | 1.038 | 0.422 | 0.047 |
| rotate90 | dynamic_1d | 2 | 1 | victus | 114.545 | 2.808 | 0.137 | 0.046 |
| rotate90 | dynamic_1d | 2 | 2 | victus | 98.228 | 9.294 | 0.160 | 0.040 |
| rotate90 | dynamic_1d | 2 | 3 | victus | 94.213 | 0.185 | 0.167 | 0.033 |
| rotate90 | dynamic_1d | 2 | 4 | victus | 84.603 | 1.676 | 0.186 | 0.031 |
| rotate90 | dynamic_1d | 2 | 5 | victus | 77.017 | 1.576 | 0.204 | 0.029 |
| rotate90 | dynamic_1d | 2 | 6 | victus | 76.776 | 11.822 | 0.205 | 0.026 |
| rotate90 | dynamic_1d | 2 | 7 | victus | 66.374 | 3.312 | 0.237 | 0.026 |
| rotate90 | dynamic_1d | 2 | 8 | victus | 65.050 | 4.121 | 0.241 | 0.024 |
| grayscale,blur,flip | static_1d | 1 | 0 | HP-Laptop | 385.964 | 13.900 | 0.900 | 0.900 |
| grayscale,blur,flip | static_1d | 2 | 0 | HP-Laptop | 459.992 | 24.020 | 0.755 | 0.378 |
| grayscale,blur,flip | static_1d | 0 | 1 | victus | 342.990 | 1.813 | 0.915 | 0.915 |
| grayscale,blur,flip | static_1d | 0 | 2 | victus | 178.790 | 0.406 | 1.756 | 0.878 |
| grayscale,blur,flip | static_1d | 0 | 3 | victus | 126.352 | 1.253 | 2.484 | 0.828 |
| grayscale,blur,flip | static_1d | 0 | 4 | victus | 103.566 | 3.258 | 3.031 | 0.758 |
| grayscale,blur,flip | static_1d | 0 | 5 | victus | 90.676 | 1.544 | 3.462 | 0.692 |
| grayscale,blur,flip | static_1d | 0 | 6 | victus | 81.193 | 0.934 | 3.866 | 0.644 |
| grayscale,blur,flip | static_1d | 0 | 7 | victus | 73.031 | 1.997 | 4.298 | 0.614 |
| grayscale,blur,flip | static_1d | 0 | 8 | victus | 71.804 | 6.674 | 4.372 | 0.546 |
| grayscale,blur,flip | static_1d | 1 | 1 | victus | 487.843 | 1.217 | 0.643 | 0.322 |
| grayscale,blur,flip | static_1d | 1 | 2 | victus | 338.980 | 1.042 | 0.926 | 0.309 |
| grayscale,blur,flip | static_1d | 1 | 3 | victus | 261.785 | 2.949 | 1.199 | 0.300 |
| grayscale,blur,flip | static_1d | 1 | 4 | victus | 217.829 | 0.836 | 1.441 | 0.288 |
| grayscale,blur,flip | static_1d | 1 | 5 | victus | 186.398 | 2.693 | 1.684 | 0.281 |
| grayscale,blur,flip | static_1d | 1 | 6 | victus | 166.992 | 1.424 | 1.880 | 0.269 |
| grayscale,blur,flip | static_1d | 1 | 7 | victus | 151.346 | 2.546 | 2.074 | 0.259 |
| grayscale,blur,flip | static_1d | 1 | 8 | victus | 137.730 | 4.197 | 2.279 | 0.253 |
| grayscale,blur,flip | static_1d | 2 | 1 | victus | 490.676 | 4.762 | 0.640 | 0.213 |
| grayscale,blur,flip | static_1d | 2 | 2 | victus | 381.404 | 6.712 | 0.823 | 0.206 |
| grayscale,blur,flip | static_1d | 2 | 3 | victus | 309.792 | 5.848 | 1.013 | 0.203 |
| grayscale,blur,flip | static_1d | 2 | 4 | victus | 264.696 | 4.336 | 1.186 | 0.198 |
| grayscale,blur,flip | static_1d | 2 | 5 | victus | 233.755 | 3.859 | 1.343 | 0.192 |
| grayscale,blur,flip | static_1d | 2 | 6 | victus | 205.803 | 3.120 | 1.525 | 0.191 |
| grayscale,blur,flip | static_1d | 2 | 7 | victus | 189.872 | 1.176 | 1.653 | 0.184 |
| grayscale,blur,flip | static_1d | 2 | 8 | victus | 182.117 | 12.415 | 1.724 | 0.172 |
| grayscale,blur,flip | static_2d | 1 | 0 | HP-Laptop | 403.705 | 40.501 | 0.861 | 0.861 |
| grayscale,blur,flip | static_2d | 2 | 0 | HP-Laptop | 445.620 | 63.206 | 0.780 | 0.390 |
| grayscale,blur,flip | static_2d | 0 | 1 | victus | 344.766 | 1.163 | 0.911 | 0.911 |
| grayscale,blur,flip | static_2d | 0 | 2 | victus | 178.309 | 1.042 | 1.760 | 0.880 |
| grayscale,blur,flip | static_2d | 0 | 3 | victus | 126.246 | 1.251 | 2.487 | 0.829 |
| grayscale,blur,flip | static_2d | 0 | 4 | victus | 113.052 | 2.380 | 2.777 | 0.694 |
| grayscale,blur,flip | static_2d | 0 | 5 | victus | 89.660 | 1.142 | 3.501 | 0.700 |
| grayscale,blur,flip | static_2d | 0 | 6 | victus | 85.792 | 1.480 | 3.659 | 0.610 |
| grayscale,blur,flip | static_2d | 0 | 7 | victus | 76.393 | 6.079 | 4.109 | 0.587 |
| grayscale,blur,flip | static_2d | 0 | 8 | victus | 75.553 | 2.857 | 4.155 | 0.519 |
| grayscale,blur,flip | static_2d | 1 | 1 | victus | 486.095 | 0.617 | 0.646 | 0.323 |
| grayscale,blur,flip | static_2d | 1 | 2 | victus | 337.102 | 1.596 | 0.931 | 0.310 |
| grayscale,blur,flip | static_2d | 1 | 3 | victus | 275.023 | 6.134 | 1.141 | 0.285 |
| grayscale,blur,flip | static_2d | 1 | 4 | victus | 219.135 | 1.544 | 1.432 | 0.286 |
| grayscale,blur,flip | static_2d | 1 | 5 | victus | 193.341 | 2.509 | 1.624 | 0.271 |
| grayscale,blur,flip | static_2d | 1 | 6 | victus | 164.060 | 1.537 | 1.913 | 0.273 |
| grayscale,blur,flip | static_2d | 1 | 7 | victus | 157.152 | 5.591 | 1.997 | 0.250 |
| grayscale,blur,flip | static_2d | 1 | 8 | victus | 144.047 | 4.859 | 2.179 | 0.242 |
| grayscale,blur,flip | static_2d | 2 | 1 | victus | 480.796 | 4.597 | 0.653 | 0.218 |
| grayscale,blur,flip | static_2d | 2 | 2 | victus | 387.153 | 3.804 | 0.811 | 0.203 |
| grayscale,blur,flip | static_2d | 2 | 3 | victus | 311.472 | 5.696 | 1.008 | 0.202 |
| grayscale,blur,flip | static_2d | 2 | 4 | victus | 274.656 | 9.835 | 1.143 | 0.190 |
| grayscale,blur,flip | static_2d | 2 | 5 | victus | 231.715 | 6.713 | 1.355 | 0.194 |
| grayscale,blur,flip | static_2d | 2 | 6 | victus | 226.055 | 4.704 | 1.389 | 0.174 |
| grayscale,blur,flip | static_2d | 2 | 7 | victus | 196.396 | 6.178 | 1.598 | 0.178 |
| grayscale,blur,flip | static_2d | 2 | 8 | victus | 199.731 | 14.452 | 1.572 | 0.157 |
| grayscale,blur,flip | dynamic_1d | 1 | 0 | HP-Laptop | 383.829 | 27.726 | 0.905 | 0.905 |
| grayscale,blur,flip | dynamic_1d | 2 | 0 | HP-Laptop | 337.173 | 38.284 | 1.030 | 0.515 |
| grayscale,blur,flip | dynamic_1d | 0 | 1 | victus | 339.727 | 5.182 | 0.924 | 0.924 |
| grayscale,blur,flip | dynamic_1d | 0 | 2 | victus | 173.225 | 0.952 | 1.812 | 0.906 |
| grayscale,blur,flip | dynamic_1d | 0 | 3 | victus | 123.222 | 2.315 | 2.548 | 0.849 |
| grayscale,blur,flip | dynamic_1d | 0 | 4 | victus | 103.182 | 0.551 | 3.042 | 0.761 |
| grayscale,blur,flip | dynamic_1d | 0 | 5 | victus | 88.328 | 0.712 | 3.554 | 0.711 |
| grayscale,blur,flip | dynamic_1d | 0 | 6 | victus | 75.613 | 1.074 | 4.152 | 0.692 |
| grayscale,blur,flip | dynamic_1d | 0 | 7 | victus | 76.386 | 5.591 | 4.110 | 0.587 |
| grayscale,blur,flip | dynamic_1d | 0 | 8 | victus | 66.473 | 0.126 | 4.722 | 0.590 |
| grayscale,blur,flip | dynamic_1d | 1 | 1 | victus | 311.960 | 4.982 | 1.006 | 0.503 |
| grayscale,blur,flip | dynamic_1d | 1 | 2 | victus | 183.281 | 1.988 | 1.713 | 0.571 |
| grayscale,blur,flip | dynamic_1d | 1 | 3 | victus | 147.932 | 3.304 | 2.122 | 0.530 |
| grayscale,blur,flip | dynamic_1d | 1 | 4 | victus | 130.299 | 3.136 | 2.409 | 0.482 |
| grayscale,blur,flip | dynamic_1d | 1 | 5 | victus | 112.438 | 2.516 | 2.792 | 0.465 |
| grayscale,blur,flip | dynamic_1d | 1 | 6 | victus | 112.739 | 9.459 | 2.784 | 0.398 |
| grayscale,blur,flip | dynamic_1d | 1 | 7 | victus | 98.734 | 0.274 | 3.179 | 0.397 |
| grayscale,blur,flip | dynamic_1d | 1 | 8 | victus | 94.615 | 5.402 | 3.318 | 0.369 |
| grayscale,blur,flip | dynamic_1d | 2 | 1 | victus | 383.421 | 32.881 | 0.819 | 0.273 |
| grayscale,blur,flip | dynamic_1d | 2 | 2 | victus | 331.049 | 36.953 | 0.948 | 0.237 |
| grayscale,blur,flip | dynamic_1d | 2 | 3 | victus | 249.047 | 11.052 | 1.260 | 0.252 |
| grayscale,blur,flip | dynamic_1d | 2 | 4 | victus | 247.752 | 21.823 | 1.267 | 0.211 |
| grayscale,blur,flip | dynamic_1d | 2 | 5 | victus | 243.000 | 42.144 | 1.292 | 0.185 |
| grayscale,blur,flip | dynamic_1d | 2 | 6 | victus | 182.288 | 3.753 | 1.722 | 0.215 |
| grayscale,blur,flip | dynamic_1d | 2 | 7 | victus | 179.366 | 18.639 | 1.750 | 0.194 |
| grayscale,blur,flip | dynamic_1d | 2 | 8 | victus | 209.300 | 49.935 | 1.500 | 0.150 |
