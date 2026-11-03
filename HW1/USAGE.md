# HW1 — Utilizare

[Prezentarea temei](README.md) · [Experimente și rezultate](EXPERIMENTS.md)

## Cerințe și compilare

Sunt necesare un compilator C, Open MPI (`mpicc`, `mpirun`) și imagini PPM binare (P6). Benchmark-urile Python folosesc NumPy și Matplotlib; comenzile de mai jos le încarcă prin `uv`.

Din rădăcina repository-ului:

```bash
cd HW1
mpicc -O3 -Wall mpi_image_proc.c -o mpi_image_proc
```

Toate comenzile următoare se execută din `HW1`.

## Rulare

```text
mpirun -np <procese> ./mpi_image_proc <intrare.ppm> <ieșire.ppm|NONE> <strategie> <operații>
```

Strategia este `seq`, `static_1d`, `static_2d` sau `dynamic_1d`. Pentru execuție paralelă, numărul de procese include coordonatorul: `-np 4` înseamnă un coordonator și trei workeri. `--oversubscribe` permite rulări locale cu mai multe procese decât sloturile disponibile.

Referință secvențială și execuție paralelă:

```bash
mpirun -np 1 ./mpi_image_proc test_images/sample_1.5MP.ppm test_images/out_grayscale.ppm seq grayscale
mpirun --oversubscribe -np 4 ./mpi_image_proc test_images/sample_1.5MP.ppm test_images/out_blur.ppm static_1d blur
mpirun --oversubscribe -np 5 ./mpi_image_proc test_images/sample_1.5MP.ppm test_images/out_blur.ppm static_2d blur:13
```

Operațiile disponibile sunt `grayscale`, `invert`, `sepia`, `blur`, `flip` și `rotate90`. `blur:N` folosește un nucleu N×N, cu N pozitiv și impar; `blur` simplu folosește 9×9. `rotate90` rotește imaginea în sens orar și inversează lățimea cu înălțimea.

Operațiile separate prin virgulă se execută în ordine:

```bash
mpirun --oversubscribe -np 4 ./mpi_image_proc test_images/sample_1.5MP.ppm test_images/out_grayscale_blur_flip.ppm dynamic_1d grayscale,blur,flip
```

Pentru măsurare fără salvarea imaginii, folosește `NONE` ca ieșire. Timpii raportați acoperă calculul și comunicația MPI, excluzând citirea și scrierea imaginii.

## Două calculatoare

Configurarea SSH și NFS este descrisă în [HW0/setup.md](../HW0/setup.md). Executabilul și fișierele trebuie să fie accesibile la aceleași căi pe ambele calculatoare. Exemplul pornește 5 procese pe Victus (inclusiv coordonatorul) și 2 workeri pe HP-Laptop:

```bash
mpirun --oversubscribe --bind-to none --host victus:5,HP-Laptop:2 -np 7 ./mpi_image_proc test_images/sample_1.5MP.ppm NONE dynamic_1d grayscale,blur,flip
```

## Benchmark-uri și rapoarte

Suita generală compilează programul, generează imaginile necesare, măsoară configurațiile și verifică rezultatele față de referința secvențială:

```bash
uv run --with numpy --with matplotlib python benchmark.py
# Alternativ, folosind clusterul:
uv run --with numpy --with matplotlib python benchmark.py --hosts victus:5,HP-Laptop:2
```

Produce `benchmark_results.csv`, `benchmark_runs.csv`, raportul `experimental_study.md` și grafice în `figures/benchmark/`. Raportul este generat la rulare.

Scriptul pentru două calculatoare este configurat în prezent pentru **64MP și pipeline-ul `grayscale,blur,flip`**, cu 3 repetări. Imaginea de 64MP este ignorată de Git; dacă lipsește, genereaz-o înainte de măsurători:

```bash
uv run --with numpy --with matplotlib python -c "import benchmark as b; b.generate_ppm_image('test_images/sample_64MP.ppm', 10667, 6000)"
```

Scriptul necesită ambele calculatoare și reia măsurătorile lipsă din jurnal:

```bash
uv run --with numpy --with matplotlib python benchmark_two_machines_small.py
# Regenerează raportul și graficele de 64MP din măsurătorile salvate:
uv run --with numpy --with matplotlib python benchmark_two_machines_small.py --plot-only
```

Datele rămân în `benchmark_two_machines/64MP/`, graficele în `figures/benchmark_two_machines/64MP/`, iar raportul este `experimental_study_two_machines_64MP.md`. Pentru alte rezoluții sau operații trebuie adaptate constantele `RESOLUTIONS` și `OPS` din script înainte de rulare.

Comparația între toate rezoluțiile se poate regenera din CSV-urile existente, fără lansarea MPI:

```bash
uv run --with numpy --with matplotlib python benchmark_two_machines_combined.py
```

Produce raportul `experimental_study_two_machines_combined.md`, datele agregate din `benchmark_two_machines/combined/` și graficele din `figures/benchmark_two_machines/combined/`.

## Verificări Python

```bash
uv run --with numpy --with matplotlib python -m unittest -v test_benchmark.py test_benchmark_two_machines.py
```

Testul dimensiunilor verifică și imaginea de 64MP, ignorată de Git din cauza dimensiunii. Dacă lipsește, folosește comanda de generare de mai sus înainte de teste.
