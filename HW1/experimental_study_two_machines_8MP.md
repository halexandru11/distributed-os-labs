# Studiu pe două calculatoare, 8MP

Imaginea `test_images/sample_8MP.ppm` are 3840×2160 pixeli. Rezultatele sunt separate de studiile anterioare.

## Metodologie

Am măsurat 320 de configurații, cu câte 3 repetări, în total 960 de rulări măsurate. Operațiile sunt grayscale, blur 9×9, rotate90 și pipeline-ul grayscale,blur,flip. Strategiile sunt static_1d, static_2d și dynamic_1d.

HP-Laptop are un Intel Core i7-7500U, cu 2 nuclee și 4 fire hardware. Victus are un Intel Core i5-12500H și 16 fire hardware. Am folosit Open MPI 4.1.6, compilare `mpicc -O3 -Wall` și `--bind-to none`. Procesele rulează fără fixare pe nuclee. Coordonatorul este un proces suplimentar față de numărul de workeri.

Rangul 0 rulează pe HP-Laptop pentru testele exclusiv pe HP-Laptop și pe Victus pentru celelalte teste. Graficul HP-Laptop include 1 proces secvențial, 2 procese cu un worker și 3 procese cu doi workeri. Rangurile 1 până la numărul de workeri HP-Laptop rulează pe HP-Laptop, iar workerii rămași rulează pe Victus. Limitele de 2 și 8 se referă la workeri, fără coordonator.

Speedup = media timpului secvențial / media timpului paralel. Referința secvențială rulează pe HP-Laptop pentru testele exclusiv pe HP-Laptop și pe Victus pentru celelalte teste. Eficiența este speedup / numărul total de workeri. Pe calculatoare diferite, acest raport depinde de performanța referinței secvențiale.

Timpii provin din instrumentarea C și exclud lansarea MPI, citirea imaginii, scrierea rezultatului și verificarea pixelilor. Prima repetare a fiecărei configurații salvează rezultatul pentru comparație integrală cu referința secvențială. Celelalte repetări folosesc ieșirea NONE. Timpii sunt afișați ca medie și abatere standard. Trei repetări oferă o verificare pilot, cu precizie limitată pentru operațiile scurte.

Toate graficele de timp folosesc aceeași limită verticală, inclusiv graficele strategiilor. Graficele de speedup folosesc o limită comună. Valorile extreme ridică limita verticală, astfel că unele curbe și bare sunt aproape de zero pe această scară. Tabelele păstrează valorile numerice. Datele brute includ timpii fiecărui worker, distribuția pe calculatoare și datele necesare eficienței. Suita măsoară aceleași configurații la 1.5MP, 4MP și 8MP. Datele pentru eficiență și variația cu rezoluția sunt în CSV-urile fiecărei rezoluții.

## grayscale

![Timp total (ms), grayscale](benchmark_two_machines/8MP/execution_time_grayscale.png)

![Speedup, grayscale](benchmark_two_machines/8MP/speedup_grayscale.png)

![Strategii, grayscale](benchmark_two_machines/8MP/partition_strategies_grayscale.png)

Cel mai mic timp paralel mediu este 23.827 ms, cu static_1d, 0 workeri HP-Laptop și 5 workeri Victus. Speedup față de referința de pe victus este 1.21.

## blur

![Timp total (ms), blur](benchmark_two_machines/8MP/execution_time_blur.png)

![Speedup, blur](benchmark_two_machines/8MP/speedup_blur.png)

![Strategii, blur](benchmark_two_machines/8MP/partition_strategies_blur.png)

Cel mai mic timp paralel mediu este 92.041 ms, cu dynamic_1d, 0 workeri HP-Laptop și 8 workeri Victus. Speedup față de referința de pe victus este 6.76.

## rotate90

![Timp total (ms), rotate90](benchmark_two_machines/8MP/execution_time_rotate90.png)

![Speedup, rotate90](benchmark_two_machines/8MP/speedup_rotate90.png)

![Strategii, rotate90](benchmark_two_machines/8MP/partition_strategies_rotate90.png)

Cel mai mic timp paralel mediu este 27.107 ms, cu dynamic_1d, 0 workeri HP-Laptop și 5 workeri Victus. Speedup față de referința de pe victus este 1.44.

## grayscale,blur,flip

![Timp total (ms), grayscale,blur,flip](benchmark_two_machines/8MP/execution_time_grayscale_blur_flip.png)

![Speedup, grayscale,blur,flip](benchmark_two_machines/8MP/speedup_grayscale_blur_flip.png)

![Strategii, grayscale,blur,flip](benchmark_two_machines/8MP/partition_strategies_grayscale_blur_flip.png)

Cel mai mic timp paralel mediu este 136.916 ms, cu dynamic_1d, 0 workeri HP-Laptop și 8 workeri Victus. Speedup față de referința de pe victus este 4.92.

## Verificare și interpretare

Cea mai lentă repetare a durat 1042.464 ms, pentru grayscale,blur,flip, static_2d, cu 1 workeri HP-Laptop și 1 workeri Victus. Cea mai mare abatere standard relativă este 38.1%, pentru grayscale, dynamic_1d, HP=1, Victus=5. Am păstrat toate repetările. Acest pilot verifică matricea și graficele, dar variația limitează concluziile despre ordinea strategiilor. Nu am măsurat separat rețeaua sau încărcarea de fond, deci nu pot atribui variația unei singure cauze.

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

Datele sunt în [results.csv](benchmark_two_machines/8MP/results.csv), [runs.csv](benchmark_two_machines/8MP/runs.csv) și [runs.jsonl](benchmark_two_machines/8MP/runs.jsonl). Fișierul [metadata.json](benchmark_two_machines/8MP/metadata.json) păstrează informațiile calculatoarelor și hash-urile imaginii și sursei. Câmpurile hp și victus reprezintă numărul de workeri. În CSV, modul seq are zero workeri și coloana coordinator identifică laptopul. În jurnalul JSONL, hp=1 selectează referința secvențială HP-Laptop, iar hp=0 selectează Victus.

| Operație | Strategie | HP workeri | Victus workeri | Coordonator | Total ms | Abatere ms | Speedup | Eficiență |
| --- | --- | ---: | ---: | --- | ---: | ---: | ---: | ---: |
| grayscale | seq | 0 | 0 | HP-Laptop | 40.210 | 0.255 | 1.000 | 1.000 |
| grayscale | seq | 0 | 0 | victus | 28.919 | 0.322 | 1.000 | 1.000 |
| blur | seq | 0 | 0 | HP-Laptop | 672.133 | 8.683 | 1.000 | 1.000 |
| blur | seq | 0 | 0 | victus | 622.525 | 1.109 | 1.000 | 1.000 |
| rotate90 | seq | 0 | 0 | HP-Laptop | 61.000 | 0.214 | 1.000 | 1.000 |
| rotate90 | seq | 0 | 0 | victus | 39.117 | 0.220 | 1.000 | 1.000 |
| grayscale,blur,flip | seq | 0 | 0 | HP-Laptop | 734.250 | 0.665 | 1.000 | 1.000 |
| grayscale,blur,flip | seq | 0 | 0 | victus | 673.317 | 0.516 | 1.000 | 1.000 |
| grayscale | static_1d | 1 | 0 | HP-Laptop | 59.544 | 0.810 | 0.675 | 0.675 |
| grayscale | static_1d | 2 | 0 | HP-Laptop | 93.908 | 2.907 | 0.428 | 0.214 |
| grayscale | static_1d | 0 | 1 | victus | 50.747 | 0.091 | 0.570 | 0.570 |
| grayscale | static_1d | 0 | 2 | victus | 32.554 | 0.345 | 0.888 | 0.444 |
| grayscale | static_1d | 0 | 3 | victus | 25.496 | 0.968 | 1.134 | 0.378 |
| grayscale | static_1d | 0 | 4 | victus | 25.938 | 1.046 | 1.115 | 0.279 |
| grayscale | static_1d | 0 | 5 | victus | 23.827 | 0.259 | 1.214 | 0.243 |
| grayscale | static_1d | 0 | 6 | victus | 27.110 | 0.288 | 1.067 | 0.178 |
| grayscale | static_1d | 0 | 7 | victus | 27.261 | 1.689 | 1.061 | 0.152 |
| grayscale | static_1d | 0 | 8 | victus | 29.654 | 3.080 | 0.975 | 0.122 |
| grayscale | static_1d | 1 | 1 | victus | 253.546 | 0.650 | 0.114 | 0.057 |
| grayscale | static_1d | 1 | 2 | victus | 178.696 | 1.558 | 0.162 | 0.054 |
| grayscale | static_1d | 1 | 3 | victus | 142.787 | 0.964 | 0.203 | 0.051 |
| grayscale | static_1d | 1 | 4 | victus | 119.321 | 1.352 | 0.242 | 0.048 |
| grayscale | static_1d | 1 | 5 | victus | 106.825 | 1.466 | 0.271 | 0.045 |
| grayscale | static_1d | 1 | 6 | victus | 96.317 | 0.505 | 0.300 | 0.043 |
| grayscale | static_1d | 1 | 7 | victus | 85.491 | 0.110 | 0.338 | 0.042 |
| grayscale | static_1d | 1 | 8 | victus | 77.879 | 2.103 | 0.371 | 0.041 |
| grayscale | static_1d | 2 | 1 | victus | 297.534 | 1.589 | 0.097 | 0.032 |
| grayscale | static_1d | 2 | 2 | victus | 233.641 | 0.453 | 0.124 | 0.031 |
| grayscale | static_1d | 2 | 3 | victus | 190.205 | 2.132 | 0.152 | 0.030 |
| grayscale | static_1d | 2 | 4 | victus | 165.397 | 2.050 | 0.175 | 0.029 |
| grayscale | static_1d | 2 | 5 | victus | 147.941 | 1.184 | 0.195 | 0.028 |
| grayscale | static_1d | 2 | 6 | victus | 135.281 | 2.240 | 0.214 | 0.027 |
| grayscale | static_1d | 2 | 7 | victus | 121.361 | 1.018 | 0.238 | 0.026 |
| grayscale | static_1d | 2 | 8 | victus | 118.532 | 6.525 | 0.244 | 0.024 |
| grayscale | static_2d | 1 | 0 | HP-Laptop | 60.309 | 1.866 | 0.667 | 0.667 |
| grayscale | static_2d | 2 | 0 | HP-Laptop | 82.455 | 13.941 | 0.488 | 0.244 |
| grayscale | static_2d | 0 | 1 | victus | 51.471 | 0.516 | 0.562 | 0.562 |
| grayscale | static_2d | 0 | 2 | victus | 33.053 | 0.560 | 0.875 | 0.437 |
| grayscale | static_2d | 0 | 3 | victus | 25.250 | 1.080 | 1.145 | 0.382 |
| grayscale | static_2d | 0 | 4 | victus | 36.862 | 2.532 | 0.785 | 0.196 |
| grayscale | static_2d | 0 | 5 | victus | 24.447 | 1.380 | 1.183 | 0.237 |
| grayscale | static_2d | 0 | 6 | victus | 36.108 | 2.599 | 0.801 | 0.133 |
| grayscale | static_2d | 0 | 7 | victus | 26.990 | 0.944 | 1.071 | 0.153 |
| grayscale | static_2d | 0 | 8 | victus | 36.961 | 4.511 | 0.782 | 0.098 |
| grayscale | static_2d | 1 | 1 | victus | 254.072 | 1.343 | 0.114 | 0.057 |
| grayscale | static_2d | 1 | 2 | victus | 179.669 | 3.369 | 0.161 | 0.054 |
| grayscale | static_2d | 1 | 3 | victus | 148.296 | 3.126 | 0.195 | 0.049 |
| grayscale | static_2d | 1 | 4 | victus | 119.107 | 1.991 | 0.243 | 0.049 |
| grayscale | static_2d | 1 | 5 | victus | 109.807 | 0.888 | 0.263 | 0.044 |
| grayscale | static_2d | 1 | 6 | victus | 94.086 | 1.378 | 0.307 | 0.044 |
| grayscale | static_2d | 1 | 7 | victus | 92.499 | 4.692 | 0.313 | 0.039 |
| grayscale | static_2d | 1 | 8 | victus | 86.154 | 1.896 | 0.336 | 0.037 |
| grayscale | static_2d | 2 | 1 | victus | 300.304 | 6.388 | 0.096 | 0.032 |
| grayscale | static_2d | 2 | 2 | victus | 252.962 | 3.793 | 0.114 | 0.029 |
| grayscale | static_2d | 2 | 3 | victus | 190.974 | 1.705 | 0.151 | 0.030 |
| grayscale | static_2d | 2 | 4 | victus | 176.212 | 1.127 | 0.164 | 0.027 |
| grayscale | static_2d | 2 | 5 | victus | 148.774 | 1.048 | 0.194 | 0.028 |
| grayscale | static_2d | 2 | 6 | victus | 142.472 | 1.924 | 0.203 | 0.025 |
| grayscale | static_2d | 2 | 7 | victus | 137.299 | 0.325 | 0.211 | 0.023 |
| grayscale | static_2d | 2 | 8 | victus | 118.848 | 3.332 | 0.243 | 0.024 |
| grayscale | dynamic_1d | 1 | 0 | HP-Laptop | 62.917 | 0.732 | 0.639 | 0.639 |
| grayscale | dynamic_1d | 2 | 0 | HP-Laptop | 61.198 | 2.466 | 0.657 | 0.329 |
| grayscale | dynamic_1d | 0 | 1 | victus | 53.985 | 0.796 | 0.536 | 0.536 |
| grayscale | dynamic_1d | 0 | 2 | victus | 30.778 | 2.318 | 0.940 | 0.470 |
| grayscale | dynamic_1d | 0 | 3 | victus | 25.448 | 0.320 | 1.136 | 0.379 |
| grayscale | dynamic_1d | 0 | 4 | victus | 26.634 | 1.080 | 1.086 | 0.271 |
| grayscale | dynamic_1d | 0 | 5 | victus | 26.080 | 0.235 | 1.109 | 0.222 |
| grayscale | dynamic_1d | 0 | 6 | victus | 28.161 | 1.491 | 1.027 | 0.171 |
| grayscale | dynamic_1d | 0 | 7 | victus | 27.743 | 0.995 | 1.042 | 0.149 |
| grayscale | dynamic_1d | 0 | 8 | victus | 29.731 | 1.598 | 0.973 | 0.122 |
| grayscale | dynamic_1d | 1 | 1 | victus | 135.295 | 2.723 | 0.214 | 0.107 |
| grayscale | dynamic_1d | 1 | 2 | victus | 74.936 | 2.109 | 0.386 | 0.129 |
| grayscale | dynamic_1d | 1 | 3 | victus | 82.461 | 3.060 | 0.351 | 0.088 |
| grayscale | dynamic_1d | 1 | 4 | victus | 69.996 | 2.591 | 0.413 | 0.083 |
| grayscale | dynamic_1d | 1 | 5 | victus | 80.919 | 30.854 | 0.357 | 0.060 |
| grayscale | dynamic_1d | 1 | 6 | victus | 81.638 | 26.533 | 0.354 | 0.051 |
| grayscale | dynamic_1d | 1 | 7 | victus | 69.513 | 7.910 | 0.416 | 0.052 |
| grayscale | dynamic_1d | 1 | 8 | victus | 76.745 | 22.357 | 0.377 | 0.042 |
| grayscale | dynamic_1d | 2 | 1 | victus | 218.835 | 22.309 | 0.132 | 0.044 |
| grayscale | dynamic_1d | 2 | 2 | victus | 159.192 | 1.453 | 0.182 | 0.045 |
| grayscale | dynamic_1d | 2 | 3 | victus | 162.667 | 32.710 | 0.178 | 0.036 |
| grayscale | dynamic_1d | 2 | 4 | victus | 157.310 | 23.307 | 0.184 | 0.031 |
| grayscale | dynamic_1d | 2 | 5 | victus | 130.398 | 0.972 | 0.222 | 0.032 |
| grayscale | dynamic_1d | 2 | 6 | victus | 133.829 | 24.921 | 0.216 | 0.027 |
| grayscale | dynamic_1d | 2 | 7 | victus | 125.786 | 24.128 | 0.230 | 0.026 |
| grayscale | dynamic_1d | 2 | 8 | victus | 142.113 | 43.937 | 0.203 | 0.020 |
| blur | static_1d | 1 | 0 | HP-Laptop | 707.357 | 28.187 | 0.950 | 0.950 |
| blur | static_1d | 2 | 0 | HP-Laptop | 764.622 | 127.280 | 0.879 | 0.440 |
| blur | static_1d | 0 | 1 | victus | 646.693 | 3.504 | 0.963 | 0.963 |
| blur | static_1d | 0 | 2 | victus | 329.913 | 1.401 | 1.887 | 0.943 |
| blur | static_1d | 0 | 3 | victus | 226.540 | 2.927 | 2.748 | 0.916 |
| blur | static_1d | 0 | 4 | victus | 182.083 | 0.138 | 3.419 | 0.855 |
| blur | static_1d | 0 | 5 | victus | 149.304 | 1.654 | 4.170 | 0.834 |
| blur | static_1d | 0 | 6 | victus | 126.920 | 0.791 | 4.905 | 0.817 |
| blur | static_1d | 0 | 7 | victus | 111.717 | 0.366 | 5.572 | 0.796 |
| blur | static_1d | 0 | 8 | victus | 101.403 | 2.689 | 6.139 | 0.767 |
| blur | static_1d | 1 | 1 | victus | 567.561 | 1.527 | 1.097 | 0.548 |
| blur | static_1d | 1 | 2 | victus | 387.295 | 1.997 | 1.607 | 0.536 |
| blur | static_1d | 1 | 3 | victus | 299.924 | 2.222 | 2.076 | 0.519 |
| blur | static_1d | 1 | 4 | victus | 244.935 | 1.459 | 2.542 | 0.508 |
| blur | static_1d | 1 | 5 | victus | 213.761 | 6.140 | 2.912 | 0.485 |
| blur | static_1d | 1 | 6 | victus | 185.518 | 0.803 | 3.356 | 0.479 |
| blur | static_1d | 1 | 7 | victus | 166.239 | 1.897 | 3.745 | 0.468 |
| blur | static_1d | 1 | 8 | victus | 148.161 | 2.557 | 4.202 | 0.467 |
| blur | static_1d | 2 | 1 | victus | 467.688 | 3.615 | 1.331 | 0.444 |
| blur | static_1d | 2 | 2 | victus | 357.520 | 2.836 | 1.741 | 0.435 |
| blur | static_1d | 2 | 3 | victus | 300.792 | 8.278 | 2.070 | 0.414 |
| blur | static_1d | 2 | 4 | victus | 254.907 | 5.057 | 2.442 | 0.407 |
| blur | static_1d | 2 | 5 | victus | 226.854 | 1.935 | 2.744 | 0.392 |
| blur | static_1d | 2 | 6 | victus | 199.135 | 2.961 | 3.126 | 0.391 |
| blur | static_1d | 2 | 7 | victus | 181.922 | 4.162 | 3.422 | 0.380 |
| blur | static_1d | 2 | 8 | victus | 159.836 | 3.540 | 3.895 | 0.389 |
| blur | static_2d | 1 | 0 | HP-Laptop | 707.919 | 35.165 | 0.949 | 0.949 |
| blur | static_2d | 2 | 0 | HP-Laptop | 821.009 | 24.395 | 0.819 | 0.409 |
| blur | static_2d | 0 | 1 | victus | 646.356 | 3.360 | 0.963 | 0.963 |
| blur | static_2d | 0 | 2 | victus | 331.977 | 2.166 | 1.875 | 0.938 |
| blur | static_2d | 0 | 3 | victus | 224.156 | 0.655 | 2.777 | 0.926 |
| blur | static_2d | 0 | 4 | victus | 187.700 | 3.232 | 3.317 | 0.829 |
| blur | static_2d | 0 | 5 | victus | 149.409 | 0.783 | 4.167 | 0.833 |
| blur | static_2d | 0 | 6 | victus | 131.580 | 0.669 | 4.731 | 0.789 |
| blur | static_2d | 0 | 7 | victus | 110.814 | 0.344 | 5.618 | 0.803 |
| blur | static_2d | 0 | 8 | victus | 108.610 | 3.358 | 5.732 | 0.716 |
| blur | static_2d | 1 | 1 | victus | 567.936 | 0.845 | 1.096 | 0.548 |
| blur | static_2d | 1 | 2 | victus | 389.195 | 0.756 | 1.600 | 0.533 |
| blur | static_2d | 1 | 3 | victus | 305.871 | 1.933 | 2.035 | 0.509 |
| blur | static_2d | 1 | 4 | victus | 245.645 | 0.505 | 2.534 | 0.507 |
| blur | static_2d | 1 | 5 | victus | 215.627 | 1.074 | 2.887 | 0.481 |
| blur | static_2d | 1 | 6 | victus | 183.328 | 1.234 | 3.396 | 0.485 |
| blur | static_2d | 1 | 7 | victus | 169.907 | 0.865 | 3.664 | 0.458 |
| blur | static_2d | 1 | 8 | victus | 152.705 | 2.358 | 4.077 | 0.453 |
| blur | static_2d | 2 | 1 | victus | 473.578 | 4.302 | 1.315 | 0.438 |
| blur | static_2d | 2 | 2 | victus | 371.010 | 7.449 | 1.678 | 0.419 |
| blur | static_2d | 2 | 3 | victus | 293.172 | 0.864 | 2.123 | 0.425 |
| blur | static_2d | 2 | 4 | victus | 259.215 | 4.396 | 2.402 | 0.400 |
| blur | static_2d | 2 | 5 | victus | 225.062 | 1.077 | 2.766 | 0.395 |
| blur | static_2d | 2 | 6 | victus | 202.328 | 2.735 | 3.077 | 0.385 |
| blur | static_2d | 2 | 7 | victus | 183.202 | 2.454 | 3.398 | 0.378 |
| blur | static_2d | 2 | 8 | victus | 167.140 | 1.548 | 3.725 | 0.372 |
| blur | dynamic_1d | 1 | 0 | HP-Laptop | 710.344 | 31.608 | 0.946 | 0.946 |
| blur | dynamic_1d | 2 | 0 | HP-Laptop | 614.996 | 50.479 | 1.093 | 0.546 |
| blur | dynamic_1d | 0 | 1 | victus | 649.277 | 3.114 | 0.959 | 0.959 |
| blur | dynamic_1d | 0 | 2 | victus | 327.846 | 0.717 | 1.899 | 0.949 |
| blur | dynamic_1d | 0 | 3 | victus | 222.105 | 3.422 | 2.803 | 0.934 |
| blur | dynamic_1d | 0 | 4 | victus | 174.577 | 0.159 | 3.566 | 0.891 |
| blur | dynamic_1d | 0 | 5 | victus | 140.741 | 0.791 | 4.423 | 0.885 |
| blur | dynamic_1d | 0 | 6 | victus | 120.075 | 1.334 | 5.184 | 0.864 |
| blur | dynamic_1d | 0 | 7 | victus | 104.345 | 0.411 | 5.966 | 0.852 |
| blur | dynamic_1d | 0 | 8 | victus | 92.041 | 0.965 | 6.764 | 0.845 |
| blur | dynamic_1d | 1 | 1 | victus | 478.116 | 1.456 | 1.302 | 0.651 |
| blur | dynamic_1d | 1 | 2 | victus | 326.566 | 1.200 | 1.906 | 0.635 |
| blur | dynamic_1d | 1 | 3 | victus | 221.620 | 4.378 | 2.809 | 0.702 |
| blur | dynamic_1d | 1 | 4 | victus | 180.068 | 4.661 | 3.457 | 0.691 |
| blur | dynamic_1d | 1 | 5 | victus | 152.208 | 0.689 | 4.090 | 0.682 |
| blur | dynamic_1d | 1 | 6 | victus | 130.340 | 0.434 | 4.776 | 0.682 |
| blur | dynamic_1d | 1 | 7 | victus | 122.298 | 4.715 | 5.090 | 0.636 |
| blur | dynamic_1d | 1 | 8 | victus | 109.648 | 6.227 | 5.678 | 0.631 |
| blur | dynamic_1d | 2 | 1 | victus | 381.881 | 27.549 | 1.630 | 0.543 |
| blur | dynamic_1d | 2 | 2 | victus | 270.881 | 16.001 | 2.298 | 0.575 |
| blur | dynamic_1d | 2 | 3 | victus | 220.402 | 22.338 | 2.824 | 0.565 |
| blur | dynamic_1d | 2 | 4 | victus | 182.631 | 11.790 | 3.409 | 0.568 |
| blur | dynamic_1d | 2 | 5 | victus | 160.868 | 13.017 | 3.870 | 0.553 |
| blur | dynamic_1d | 2 | 6 | victus | 150.351 | 4.575 | 4.140 | 0.518 |
| blur | dynamic_1d | 2 | 7 | victus | 129.737 | 6.785 | 4.798 | 0.533 |
| blur | dynamic_1d | 2 | 8 | victus | 124.684 | 6.988 | 4.993 | 0.499 |
| rotate90 | static_1d | 1 | 0 | HP-Laptop | 82.928 | 2.597 | 0.736 | 0.736 |
| rotate90 | static_1d | 2 | 0 | HP-Laptop | 123.235 | 15.918 | 0.495 | 0.247 |
| rotate90 | static_1d | 0 | 1 | victus | 61.884 | 1.609 | 0.632 | 0.632 |
| rotate90 | static_1d | 0 | 2 | victus | 49.891 | 0.402 | 0.784 | 0.392 |
| rotate90 | static_1d | 0 | 3 | victus | 36.277 | 0.434 | 1.078 | 0.359 |
| rotate90 | static_1d | 0 | 4 | victus | 32.861 | 0.255 | 1.190 | 0.298 |
| rotate90 | static_1d | 0 | 5 | victus | 32.699 | 3.003 | 1.196 | 0.239 |
| rotate90 | static_1d | 0 | 6 | victus | 33.985 | 3.561 | 1.151 | 0.192 |
| rotate90 | static_1d | 0 | 7 | victus | 33.328 | 1.769 | 1.174 | 0.168 |
| rotate90 | static_1d | 0 | 8 | victus | 34.955 | 4.625 | 1.119 | 0.140 |
| rotate90 | static_1d | 1 | 1 | victus | 269.806 | 5.455 | 0.145 | 0.072 |
| rotate90 | static_1d | 1 | 2 | victus | 184.230 | 0.545 | 0.212 | 0.071 |
| rotate90 | static_1d | 1 | 3 | victus | 146.196 | 5.794 | 0.268 | 0.067 |
| rotate90 | static_1d | 1 | 4 | victus | 120.316 | 1.285 | 0.325 | 0.065 |
| rotate90 | static_1d | 1 | 5 | victus | 104.708 | 1.800 | 0.374 | 0.062 |
| rotate90 | static_1d | 1 | 6 | victus | 95.824 | 1.714 | 0.408 | 0.058 |
| rotate90 | static_1d | 1 | 7 | victus | 91.705 | 2.117 | 0.427 | 0.053 |
| rotate90 | static_1d | 1 | 8 | victus | 85.049 | 3.022 | 0.460 | 0.051 |
| rotate90 | static_1d | 2 | 1 | victus | 302.071 | 4.902 | 0.129 | 0.043 |
| rotate90 | static_1d | 2 | 2 | victus | 234.214 | 1.061 | 0.167 | 0.042 |
| rotate90 | static_1d | 2 | 3 | victus | 191.828 | 1.003 | 0.204 | 0.041 |
| rotate90 | static_1d | 2 | 4 | victus | 170.427 | 3.104 | 0.230 | 0.038 |
| rotate90 | static_1d | 2 | 5 | victus | 150.216 | 2.611 | 0.260 | 0.037 |
| rotate90 | static_1d | 2 | 6 | victus | 138.592 | 1.703 | 0.282 | 0.035 |
| rotate90 | static_1d | 2 | 7 | victus | 131.477 | 0.828 | 0.298 | 0.033 |
| rotate90 | static_1d | 2 | 8 | victus | 116.567 | 1.135 | 0.336 | 0.034 |
| rotate90 | static_2d | 1 | 0 | HP-Laptop | 80.875 | 1.263 | 0.754 | 0.754 |
| rotate90 | static_2d | 2 | 0 | HP-Laptop | 115.028 | 6.879 | 0.530 | 0.265 |
| rotate90 | static_2d | 0 | 1 | victus | 61.620 | 0.915 | 0.635 | 0.635 |
| rotate90 | static_2d | 0 | 2 | victus | 48.811 | 0.851 | 0.801 | 0.401 |
| rotate90 | static_2d | 0 | 3 | victus | 36.969 | 0.299 | 1.058 | 0.353 |
| rotate90 | static_2d | 0 | 4 | victus | 35.515 | 0.091 | 1.101 | 0.275 |
| rotate90 | static_2d | 0 | 5 | victus | 33.442 | 2.240 | 1.170 | 0.234 |
| rotate90 | static_2d | 0 | 6 | victus | 35.122 | 2.299 | 1.114 | 0.186 |
| rotate90 | static_2d | 0 | 7 | victus | 36.599 | 0.986 | 1.069 | 0.153 |
| rotate90 | static_2d | 0 | 8 | victus | 38.357 | 4.596 | 1.020 | 0.127 |
| rotate90 | static_2d | 1 | 1 | victus | 273.108 | 1.826 | 0.143 | 0.072 |
| rotate90 | static_2d | 1 | 2 | victus | 187.544 | 3.971 | 0.209 | 0.070 |
| rotate90 | static_2d | 1 | 3 | victus | 146.869 | 1.462 | 0.266 | 0.067 |
| rotate90 | static_2d | 1 | 4 | victus | 121.503 | 1.093 | 0.322 | 0.064 |
| rotate90 | static_2d | 1 | 5 | victus | 110.992 | 1.268 | 0.352 | 0.059 |
| rotate90 | static_2d | 1 | 6 | victus | 100.268 | 6.953 | 0.390 | 0.056 |
| rotate90 | static_2d | 1 | 7 | victus | 94.359 | 1.661 | 0.415 | 0.052 |
| rotate90 | static_2d | 1 | 8 | victus | 90.279 | 5.265 | 0.433 | 0.048 |
| rotate90 | static_2d | 2 | 1 | victus | 303.945 | 3.867 | 0.129 | 0.043 |
| rotate90 | static_2d | 2 | 2 | victus | 241.182 | 1.529 | 0.162 | 0.041 |
| rotate90 | static_2d | 2 | 3 | victus | 196.334 | 1.861 | 0.199 | 0.040 |
| rotate90 | static_2d | 2 | 4 | victus | 175.211 | 2.500 | 0.223 | 0.037 |
| rotate90 | static_2d | 2 | 5 | victus | 150.077 | 1.254 | 0.261 | 0.037 |
| rotate90 | static_2d | 2 | 6 | victus | 144.654 | 2.328 | 0.270 | 0.034 |
| rotate90 | static_2d | 2 | 7 | victus | 136.786 | 1.491 | 0.286 | 0.032 |
| rotate90 | static_2d | 2 | 8 | victus | 135.453 | 26.895 | 0.289 | 0.029 |
| rotate90 | dynamic_1d | 1 | 0 | HP-Laptop | 75.856 | 4.704 | 0.804 | 0.804 |
| rotate90 | dynamic_1d | 2 | 0 | HP-Laptop | 64.269 | 3.730 | 0.949 | 0.475 |
| rotate90 | dynamic_1d | 0 | 1 | victus | 58.058 | 0.830 | 0.674 | 0.674 |
| rotate90 | dynamic_1d | 0 | 2 | victus | 29.630 | 0.107 | 1.320 | 0.660 |
| rotate90 | dynamic_1d | 0 | 3 | victus | 27.965 | 2.294 | 1.399 | 0.466 |
| rotate90 | dynamic_1d | 0 | 4 | victus | 28.024 | 1.842 | 1.396 | 0.349 |
| rotate90 | dynamic_1d | 0 | 5 | victus | 27.107 | 0.720 | 1.443 | 0.289 |
| rotate90 | dynamic_1d | 0 | 6 | victus | 29.339 | 1.954 | 1.333 | 0.222 |
| rotate90 | dynamic_1d | 0 | 7 | victus | 30.502 | 0.318 | 1.282 | 0.183 |
| rotate90 | dynamic_1d | 0 | 8 | victus | 28.491 | 1.710 | 1.373 | 0.172 |
| rotate90 | dynamic_1d | 1 | 1 | victus | 136.828 | 2.935 | 0.286 | 0.143 |
| rotate90 | dynamic_1d | 1 | 2 | victus | 81.036 | 12.136 | 0.483 | 0.161 |
| rotate90 | dynamic_1d | 1 | 3 | victus | 82.657 | 2.728 | 0.473 | 0.118 |
| rotate90 | dynamic_1d | 1 | 4 | victus | 75.624 | 7.355 | 0.517 | 0.103 |
| rotate90 | dynamic_1d | 1 | 5 | victus | 69.383 | 5.613 | 0.564 | 0.094 |
| rotate90 | dynamic_1d | 1 | 6 | victus | 70.621 | 1.766 | 0.554 | 0.079 |
| rotate90 | dynamic_1d | 1 | 7 | victus | 65.723 | 1.607 | 0.595 | 0.074 |
| rotate90 | dynamic_1d | 1 | 8 | victus | 72.373 | 12.454 | 0.540 | 0.060 |
| rotate90 | dynamic_1d | 2 | 1 | victus | 223.646 | 7.175 | 0.175 | 0.058 |
| rotate90 | dynamic_1d | 2 | 2 | victus | 175.187 | 14.926 | 0.223 | 0.056 |
| rotate90 | dynamic_1d | 2 | 3 | victus | 160.241 | 3.657 | 0.244 | 0.049 |
| rotate90 | dynamic_1d | 2 | 4 | victus | 143.320 | 1.202 | 0.273 | 0.045 |
| rotate90 | dynamic_1d | 2 | 5 | victus | 131.487 | 1.218 | 0.298 | 0.043 |
| rotate90 | dynamic_1d | 2 | 6 | victus | 119.863 | 0.697 | 0.326 | 0.041 |
| rotate90 | dynamic_1d | 2 | 7 | victus | 113.789 | 3.045 | 0.344 | 0.038 |
| rotate90 | dynamic_1d | 2 | 8 | victus | 102.472 | 4.549 | 0.382 | 0.038 |
| grayscale,blur,flip | static_1d | 1 | 0 | HP-Laptop | 827.460 | 39.615 | 0.887 | 0.887 |
| grayscale,blur,flip | static_1d | 2 | 0 | HP-Laptop | 832.259 | 145.140 | 0.882 | 0.441 |
| grayscale,blur,flip | static_1d | 0 | 1 | victus | 747.294 | 0.766 | 0.901 | 0.901 |
| grayscale,blur,flip | static_1d | 0 | 2 | victus | 387.699 | 0.763 | 1.737 | 0.868 |
| grayscale,blur,flip | static_1d | 0 | 3 | victus | 273.858 | 5.382 | 2.459 | 0.820 |
| grayscale,blur,flip | static_1d | 0 | 4 | victus | 228.090 | 2.366 | 2.952 | 0.738 |
| grayscale,blur,flip | static_1d | 0 | 5 | victus | 191.118 | 1.382 | 3.523 | 0.705 |
| grayscale,blur,flip | static_1d | 0 | 6 | victus | 171.948 | 3.992 | 3.916 | 0.653 |
| grayscale,blur,flip | static_1d | 0 | 7 | victus | 158.586 | 2.517 | 4.246 | 0.607 |
| grayscale,blur,flip | static_1d | 0 | 8 | victus | 147.103 | 1.233 | 4.577 | 0.572 |
| grayscale,blur,flip | static_1d | 1 | 1 | victus | 1037.733 | 1.148 | 0.649 | 0.324 |
| grayscale,blur,flip | static_1d | 1 | 2 | victus | 712.213 | 2.623 | 0.945 | 0.315 |
| grayscale,blur,flip | static_1d | 1 | 3 | victus | 548.607 | 0.954 | 1.227 | 0.307 |
| grayscale,blur,flip | static_1d | 1 | 4 | victus | 450.922 | 3.221 | 1.493 | 0.299 |
| grayscale,blur,flip | static_1d | 1 | 5 | victus | 392.104 | 2.467 | 1.717 | 0.286 |
| grayscale,blur,flip | static_1d | 1 | 6 | victus | 339.533 | 2.668 | 1.983 | 0.283 |
| grayscale,blur,flip | static_1d | 1 | 7 | victus | 301.466 | 0.507 | 2.233 | 0.279 |
| grayscale,blur,flip | static_1d | 1 | 8 | victus | 274.574 | 4.213 | 2.452 | 0.272 |
| grayscale,blur,flip | static_1d | 2 | 1 | victus | 1033.783 | 1.638 | 0.651 | 0.217 |
| grayscale,blur,flip | static_1d | 2 | 2 | victus | 783.299 | 3.250 | 0.860 | 0.215 |
| grayscale,blur,flip | static_1d | 2 | 3 | victus | 644.874 | 9.943 | 1.044 | 0.209 |
| grayscale,blur,flip | static_1d | 2 | 4 | victus | 548.780 | 5.358 | 1.227 | 0.204 |
| grayscale,blur,flip | static_1d | 2 | 5 | victus | 478.549 | 2.204 | 1.407 | 0.201 |
| grayscale,blur,flip | static_1d | 2 | 6 | victus | 426.178 | 8.784 | 1.580 | 0.197 |
| grayscale,blur,flip | static_1d | 2 | 7 | victus | 396.137 | 5.165 | 1.700 | 0.189 |
| grayscale,blur,flip | static_1d | 2 | 8 | victus | 356.753 | 7.523 | 1.887 | 0.189 |
| grayscale,blur,flip | static_2d | 1 | 0 | HP-Laptop | 833.999 | 29.759 | 0.880 | 0.880 |
| grayscale,blur,flip | static_2d | 2 | 0 | HP-Laptop | 872.309 | 116.737 | 0.842 | 0.421 |
| grayscale,blur,flip | static_2d | 0 | 1 | victus | 749.283 | 4.354 | 0.899 | 0.899 |
| grayscale,blur,flip | static_2d | 0 | 2 | victus | 386.610 | 2.491 | 1.742 | 0.871 |
| grayscale,blur,flip | static_2d | 0 | 3 | victus | 271.031 | 1.042 | 2.484 | 0.828 |
| grayscale,blur,flip | static_2d | 0 | 4 | victus | 244.408 | 0.176 | 2.755 | 0.689 |
| grayscale,blur,flip | static_2d | 0 | 5 | victus | 192.950 | 0.535 | 3.490 | 0.698 |
| grayscale,blur,flip | static_2d | 0 | 6 | victus | 186.869 | 6.152 | 3.603 | 0.601 |
| grayscale,blur,flip | static_2d | 0 | 7 | victus | 156.460 | 1.188 | 4.303 | 0.615 |
| grayscale,blur,flip | static_2d | 0 | 8 | victus | 159.368 | 5.275 | 4.225 | 0.528 |
| grayscale,blur,flip | static_2d | 1 | 1 | victus | 1039.485 | 4.113 | 0.648 | 0.324 |
| grayscale,blur,flip | static_2d | 1 | 2 | victus | 714.550 | 3.377 | 0.942 | 0.314 |
| grayscale,blur,flip | static_2d | 1 | 3 | victus | 566.148 | 1.691 | 1.189 | 0.297 |
| grayscale,blur,flip | static_2d | 1 | 4 | victus | 452.430 | 1.992 | 1.488 | 0.298 |
| grayscale,blur,flip | static_2d | 1 | 5 | victus | 405.977 | 2.309 | 1.659 | 0.276 |
| grayscale,blur,flip | static_2d | 1 | 6 | victus | 339.421 | 1.780 | 1.984 | 0.283 |
| grayscale,blur,flip | static_2d | 1 | 7 | victus | 323.633 | 2.600 | 2.080 | 0.260 |
| grayscale,blur,flip | static_2d | 1 | 8 | victus | 296.475 | 0.823 | 2.271 | 0.252 |
| grayscale,blur,flip | static_2d | 2 | 1 | victus | 1024.271 | 2.463 | 0.657 | 0.219 |
| grayscale,blur,flip | static_2d | 2 | 2 | victus | 816.993 | 5.905 | 0.824 | 0.206 |
| grayscale,blur,flip | static_2d | 2 | 3 | victus | 641.335 | 3.868 | 1.050 | 0.210 |
| grayscale,blur,flip | static_2d | 2 | 4 | victus | 570.700 | 5.835 | 1.180 | 0.197 |
| grayscale,blur,flip | static_2d | 2 | 5 | victus | 473.992 | 2.211 | 1.421 | 0.203 |
| grayscale,blur,flip | static_2d | 2 | 6 | victus | 447.257 | 1.506 | 1.505 | 0.188 |
| grayscale,blur,flip | static_2d | 2 | 7 | victus | 411.646 | 7.779 | 1.636 | 0.182 |
| grayscale,blur,flip | static_2d | 2 | 8 | victus | 369.250 | 5.665 | 1.823 | 0.182 |
| grayscale,blur,flip | dynamic_1d | 1 | 0 | HP-Laptop | 772.920 | 2.653 | 0.950 | 0.950 |
| grayscale,blur,flip | dynamic_1d | 2 | 0 | HP-Laptop | 634.675 | 16.584 | 1.157 | 0.578 |
| grayscale,blur,flip | dynamic_1d | 0 | 1 | victus | 722.273 | 0.625 | 0.932 | 0.932 |
| grayscale,blur,flip | dynamic_1d | 0 | 2 | victus | 370.973 | 1.425 | 1.815 | 0.908 |
| grayscale,blur,flip | dynamic_1d | 0 | 3 | victus | 259.974 | 0.532 | 2.590 | 0.863 |
| grayscale,blur,flip | dynamic_1d | 0 | 4 | victus | 212.135 | 3.133 | 3.174 | 0.794 |
| grayscale,blur,flip | dynamic_1d | 0 | 5 | victus | 183.532 | 2.876 | 3.669 | 0.734 |
| grayscale,blur,flip | dynamic_1d | 0 | 6 | victus | 164.163 | 1.344 | 4.102 | 0.684 |
| grayscale,blur,flip | dynamic_1d | 0 | 7 | victus | 147.353 | 2.282 | 4.569 | 0.653 |
| grayscale,blur,flip | dynamic_1d | 0 | 8 | victus | 136.916 | 3.803 | 4.918 | 0.615 |
| grayscale,blur,flip | dynamic_1d | 1 | 1 | victus | 649.971 | 38.624 | 1.036 | 0.518 |
| grayscale,blur,flip | dynamic_1d | 1 | 2 | victus | 360.187 | 5.728 | 1.869 | 0.623 |
| grayscale,blur,flip | dynamic_1d | 1 | 3 | victus | 340.796 | 19.662 | 1.976 | 0.494 |
| grayscale,blur,flip | dynamic_1d | 1 | 4 | victus | 287.278 | 48.042 | 2.344 | 0.469 |
| grayscale,blur,flip | dynamic_1d | 1 | 5 | victus | 223.499 | 2.617 | 3.013 | 0.502 |
| grayscale,blur,flip | dynamic_1d | 1 | 6 | victus | 216.041 | 10.293 | 3.117 | 0.445 |
| grayscale,blur,flip | dynamic_1d | 1 | 7 | victus | 196.850 | 3.358 | 3.420 | 0.428 |
| grayscale,blur,flip | dynamic_1d | 1 | 8 | victus | 193.906 | 26.883 | 3.472 | 0.386 |
| grayscale,blur,flip | dynamic_1d | 2 | 1 | victus | 656.188 | 15.169 | 1.026 | 0.342 |
| grayscale,blur,flip | dynamic_1d | 2 | 2 | victus | 547.973 | 35.059 | 1.229 | 0.307 |
| grayscale,blur,flip | dynamic_1d | 2 | 3 | victus | 471.259 | 24.692 | 1.429 | 0.286 |
| grayscale,blur,flip | dynamic_1d | 2 | 4 | victus | 433.269 | 1.217 | 1.554 | 0.259 |
| grayscale,blur,flip | dynamic_1d | 2 | 5 | victus | 382.657 | 29.503 | 1.760 | 0.251 |
| grayscale,blur,flip | dynamic_1d | 2 | 6 | victus | 384.914 | 47.839 | 1.749 | 0.219 |
| grayscale,blur,flip | dynamic_1d | 2 | 7 | victus | 387.973 | 66.002 | 1.735 | 0.193 |
| grayscale,blur,flip | dynamic_1d | 2 | 8 | victus | 286.460 | 2.831 | 2.350 | 0.235 |
