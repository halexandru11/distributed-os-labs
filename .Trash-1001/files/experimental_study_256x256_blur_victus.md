# Studiu pilot pe două calculatoare, 256×256

Imaginea `test_images/sample_small.ppm` are 65.536 pixeli. Acest raport păstrează studiul original și folosește numai imaginea de 256×256.

## Metodologie

Am măsurat 79 de configurații, cu câte 3 repetări, în total 237 de rulări măsurate. În această etapă măsurăm numai blur 9×9. Strategiile sunt static_1d, static_2d și dynamic_1d.

HP-Laptop are un Intel Core i7-7500U, cu 2 nuclee și 4 fire hardware. Victus are un Intel Core i5-12500H și 16 fire hardware. Am folosit Open MPI 4.1.6, compilare `mpicc -O3 -Wall` și `--bind-to none`. Procesele rulează fără fixare pe nuclee. Coordonatorul este un proces suplimentar față de numărul de workeri.

Rangul 0 este întotdeauna pe Victus, inclusiv când toți workerii sunt pe HP-Laptop. Rangurile 1 până la numărul de workeri HP-Laptop rulează pe HP-Laptop, iar workerii rămași rulează pe Victus. Limitele de 2 și 8 se referă la workeri, fără coordonator.

Speedup = media timpului secvențial / media timpului paralel. Referința secvențială rulează întotdeauna pe Victus. Eficiența este speedup / numărul total de workeri. Pe calculatoare diferite, acest raport depinde de performanța referinței secvențiale.

Timpii provin din instrumentarea C și exclud lansarea MPI, citirea imaginii, scrierea rezultatului și verificarea pixelilor. Prima repetare a fiecărei configurații salvează rezultatul pentru comparație integrală cu referința secvențială. Celelalte repetări folosesc ieșirea NONE. Timpii sunt afișați ca medie și abatere standard. Trei repetări oferă o verificare pilot, cu precizie limitată pentru operațiile scurte.

Toate graficele de timp folosesc aceeași limită verticală, inclusiv graficele strategiilor. Graficele de speedup folosesc o limită comună. Valorile extreme ridică limita verticală, astfel că unele curbe și bare sunt aproape de zero pe această scară. Tabelele păstrează valorile numerice. Datele brute includ timpii fiecărui worker, distribuția pe calculatoare și datele necesare eficienței. Variația cu rezoluția necesită măsurători la alte dimensiuni și nu poate fi evaluată cu această singură imagine.

## blur

![Timp total (ms), blur](benchmark_small_two_machines_blur_victus/execution_time_blur.png)

![Speedup, blur](benchmark_small_two_machines_blur_victus/speedup_blur.png)

![Strategii, blur](benchmark_small_two_machines_blur_victus/partition_strategies_blur.png)

Cel mai mic timp paralel mediu este 1.476 ms, cu static_1d, 0 workeri HP-Laptop și 5 workeri Victus. Speedup față de referința de pe victus este 4.57.

## Verificare și interpretare

Cea mai lentă repetare a durat 41.190 ms, pentru blur, static_2d, cu 1 workeri HP-Laptop și 0 workeri Victus. Cea mai mare abatere standard relativă este 32.1%, pentru blur, static_2d, HP=0, Victus=2. Am păstrat toate repetările. Acest pilot verifică matricea și graficele, dar variația limitează concluziile despre ordinea strategiilor. Nu am măsurat separat rețeaua sau încărcarea de fond, deci nu pot atribui variația unei singure cauze.

Toate cele 79 de configurații au rezultate identice pixel cu pixel cu referința secvențială în prima repetare.

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

Datele sunt în [results.csv](benchmark_small_two_machines_blur_victus/results.csv), [runs.csv](benchmark_small_two_machines_blur_victus/runs.csv) și [runs.jsonl](benchmark_small_two_machines_blur_victus/runs.jsonl). Fișierul [metadata.json](benchmark_small_two_machines_blur_victus/metadata.json) păstrează informațiile calculatoarelor și hash-urile imaginii și sursei. Câmpurile hp și victus reprezintă numărul de workeri. În modul seq, ambele sunt zero, iar singurul proces rulează pe Victus.

| Operație | Strategie | HP workeri | Victus workeri | Coordonator | Total ms | Abatere ms | Speedup | Eficiență |
| --- | --- | ---: | ---: | --- | ---: | ---: | ---: | ---: |
| blur | seq | 0 | 0 | victus | 6.750 | 0.331 | 1.000 | 1.000 |
| blur | static_1d | 1 | 0 | victus | 36.206 | 1.570 | 0.186 | 0.186 |
| blur | static_1d | 2 | 0 | victus | 34.383 | 0.582 | 0.196 | 0.098 |
| blur | static_1d | 0 | 1 | victus | 6.560 | 2.004 | 1.029 | 1.029 |
| blur | static_1d | 0 | 2 | victus | 2.904 | 0.485 | 2.324 | 1.162 |
| blur | static_1d | 0 | 3 | victus | 2.519 | 0.389 | 2.680 | 0.893 |
| blur | static_1d | 0 | 4 | victus | 1.921 | 0.318 | 3.514 | 0.878 |
| blur | static_1d | 0 | 5 | victus | 1.476 | 0.121 | 4.573 | 0.915 |
| blur | static_1d | 0 | 6 | victus | 1.696 | 0.147 | 3.979 | 0.663 |
| blur | static_1d | 0 | 7 | victus | 1.797 | 0.136 | 3.757 | 0.537 |
| blur | static_1d | 0 | 8 | victus | 2.020 | 0.417 | 3.342 | 0.418 |
| blur | static_1d | 1 | 1 | victus | 28.394 | 5.023 | 0.238 | 0.119 |
| blur | static_1d | 1 | 2 | victus | 28.846 | 0.864 | 0.234 | 0.078 |
| blur | static_1d | 1 | 3 | victus | 26.395 | 1.441 | 0.256 | 0.064 |
| blur | static_1d | 1 | 4 | victus | 25.128 | 0.415 | 0.269 | 0.054 |
| blur | static_1d | 1 | 5 | victus | 24.915 | 1.255 | 0.271 | 0.045 |
| blur | static_1d | 1 | 6 | victus | 24.072 | 2.147 | 0.280 | 0.040 |
| blur | static_1d | 1 | 7 | victus | 23.183 | 1.416 | 0.291 | 0.036 |
| blur | static_1d | 1 | 8 | victus | 22.691 | 1.255 | 0.297 | 0.033 |
| blur | static_1d | 2 | 1 | victus | 33.954 | 0.292 | 0.199 | 0.066 |
| blur | static_1d | 2 | 2 | victus | 32.550 | 0.672 | 0.207 | 0.052 |
| blur | static_1d | 2 | 3 | victus | 33.038 | 2.070 | 0.204 | 0.041 |
| blur | static_1d | 2 | 4 | victus | 32.317 | 0.289 | 0.209 | 0.035 |
| blur | static_1d | 2 | 5 | victus | 31.988 | 0.556 | 0.211 | 0.030 |
| blur | static_1d | 2 | 6 | victus | 31.869 | 0.463 | 0.212 | 0.026 |
| blur | static_1d | 2 | 7 | victus | 31.286 | 0.497 | 0.216 | 0.024 |
| blur | static_1d | 2 | 8 | victus | 30.945 | 0.344 | 0.218 | 0.022 |
| blur | static_2d | 1 | 0 | victus | 37.459 | 3.284 | 0.180 | 0.180 |
| blur | static_2d | 2 | 0 | victus | 34.781 | 0.543 | 0.194 | 0.097 |
| blur | static_2d | 0 | 1 | victus | 6.010 | 0.903 | 1.123 | 1.123 |
| blur | static_2d | 0 | 2 | victus | 4.359 | 1.399 | 1.548 | 0.774 |
| blur | static_2d | 0 | 3 | victus | 2.347 | 0.466 | 2.876 | 0.959 |
| blur | static_2d | 0 | 4 | victus | 2.168 | 0.494 | 3.113 | 0.778 |
| blur | static_2d | 0 | 5 | victus | 1.719 | 0.277 | 3.927 | 0.785 |
| blur | static_2d | 0 | 6 | victus | 1.650 | 0.162 | 4.091 | 0.682 |
| blur | static_2d | 0 | 7 | victus | 2.123 | 0.486 | 3.180 | 0.454 |
| blur | static_2d | 0 | 8 | victus | 1.830 | 0.209 | 3.689 | 0.461 |
| blur | static_2d | 1 | 1 | victus | 30.647 | 1.693 | 0.220 | 0.110 |
| blur | static_2d | 1 | 2 | victus | 29.285 | 1.111 | 0.231 | 0.077 |
| blur | static_2d | 1 | 3 | victus | 26.680 | 0.796 | 0.253 | 0.063 |
| blur | static_2d | 1 | 4 | victus | 24.226 | 2.285 | 0.279 | 0.056 |
| blur | static_2d | 1 | 5 | victus | 23.696 | 2.066 | 0.285 | 0.047 |
| blur | static_2d | 1 | 6 | victus | 23.594 | 0.164 | 0.286 | 0.041 |
| blur | static_2d | 1 | 7 | victus | 24.044 | 0.906 | 0.281 | 0.035 |
| blur | static_2d | 1 | 8 | victus | 22.610 | 1.291 | 0.299 | 0.033 |
| blur | static_2d | 2 | 1 | victus | 32.868 | 0.840 | 0.205 | 0.068 |
| blur | static_2d | 2 | 2 | victus | 33.105 | 0.574 | 0.204 | 0.051 |
| blur | static_2d | 2 | 3 | victus | 32.457 | 0.465 | 0.208 | 0.042 |
| blur | static_2d | 2 | 4 | victus | 33.283 | 1.194 | 0.203 | 0.034 |
| blur | static_2d | 2 | 5 | victus | 31.438 | 0.498 | 0.215 | 0.031 |
| blur | static_2d | 2 | 6 | victus | 31.814 | 0.549 | 0.212 | 0.027 |
| blur | static_2d | 2 | 7 | victus | 32.098 | 0.395 | 0.210 | 0.023 |
| blur | static_2d | 2 | 8 | victus | 31.385 | 0.342 | 0.215 | 0.022 |
| blur | dynamic_1d | 1 | 0 | victus | 37.052 | 1.179 | 0.182 | 0.182 |
| blur | dynamic_1d | 2 | 0 | victus | 35.070 | 0.122 | 0.192 | 0.096 |
| blur | dynamic_1d | 0 | 1 | victus | 5.435 | 0.150 | 1.242 | 1.242 |
| blur | dynamic_1d | 0 | 2 | victus | 3.718 | 0.390 | 1.815 | 0.908 |
| blur | dynamic_1d | 0 | 3 | victus | 2.001 | 0.072 | 3.374 | 1.125 |
| blur | dynamic_1d | 0 | 4 | victus | 1.792 | 0.243 | 3.766 | 0.942 |
| blur | dynamic_1d | 0 | 5 | victus | 1.690 | 0.412 | 3.993 | 0.799 |
| blur | dynamic_1d | 0 | 6 | victus | 1.479 | 0.439 | 4.565 | 0.761 |
| blur | dynamic_1d | 0 | 7 | victus | 1.755 | 0.133 | 3.846 | 0.549 |
| blur | dynamic_1d | 0 | 8 | victus | 1.848 | 0.202 | 3.652 | 0.457 |
| blur | dynamic_1d | 1 | 1 | victus | 24.203 | 1.023 | 0.279 | 0.139 |
| blur | dynamic_1d | 1 | 2 | victus | 23.187 | 0.868 | 0.291 | 0.097 |
| blur | dynamic_1d | 1 | 3 | victus | 22.813 | 0.174 | 0.296 | 0.074 |
| blur | dynamic_1d | 1 | 4 | victus | 22.597 | 0.263 | 0.299 | 0.060 |
| blur | dynamic_1d | 1 | 5 | victus | 21.652 | 0.532 | 0.312 | 0.052 |
| blur | dynamic_1d | 1 | 6 | victus | 22.176 | 0.724 | 0.304 | 0.043 |
| blur | dynamic_1d | 1 | 7 | victus | 21.584 | 0.543 | 0.313 | 0.039 |
| blur | dynamic_1d | 1 | 8 | victus | 21.210 | 0.231 | 0.318 | 0.035 |
| blur | dynamic_1d | 2 | 1 | victus | 32.296 | 0.270 | 0.209 | 0.070 |
| blur | dynamic_1d | 2 | 2 | victus | 31.577 | 0.753 | 0.214 | 0.053 |
| blur | dynamic_1d | 2 | 3 | victus | 31.832 | 0.446 | 0.212 | 0.042 |
| blur | dynamic_1d | 2 | 4 | victus | 31.685 | 0.097 | 0.213 | 0.036 |
| blur | dynamic_1d | 2 | 5 | victus | 31.431 | 0.241 | 0.215 | 0.031 |
| blur | dynamic_1d | 2 | 6 | victus | 27.070 | 3.937 | 0.249 | 0.031 |
| blur | dynamic_1d | 2 | 7 | victus | 31.461 | 0.464 | 0.215 | 0.024 |
| blur | dynamic_1d | 2 | 8 | victus | 31.824 | 0.431 | 0.212 | 0.021 |
