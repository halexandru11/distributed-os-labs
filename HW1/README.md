# MPI Image Processing — Command-Line Execution Guide

Toate comenzile de mai jos folosesc calea directă către fișiere, fără variabile de mediu (`$INPUT`).

---

## 1. Compilare

```bash
cd /home/mpiuser/sod/nfs-cloud/HW1
mpicc -O3 -Wall mpi_image_proc.c -o mpi_image_proc
```

---

## 2. Operații Individuale

### A. Categoria 1: Modificări de Culoare (In-Place)
* **Grayscale (Static 1D, 4 procese: 1 Coordonator + 3 Workeri):**
  ```bash
  mpirun --oversubscribe -np 4 ./mpi_image_proc test_images/sample_1.5MP.ppm test_images/out_grayscale.ppm static_1d grayscale
  ```
* **Color Inversion (Dynamic Load Balancing, 6 procese):**
  ```bash
  mpirun --oversubscribe -np 6 ./mpi_image_proc test_images/sample_1.5MP.ppm test_images/out_grayscale.ppm dynamic_1d invert
  ```
* **Sepia Filter (Secvențial, 1 proces):**
  ```bash
  mpirun -np 1 ./mpi_image_proc test_images/sample_1.5MP.ppm test_images/out_grayscale.ppm seq sepia
  ```

### B. Categoria 2: Convoluții pe Vecinătate

`blur` folosește implicit 9x9; `blur:N` selectează un nucleu NxN, cu N pozitiv și impar.

* **9x9 Box Blur (Static 1D, 4 procese):**
  ```bash
  mpirun --oversubscribe -np 4 ./mpi_image_proc test_images/sample_1.5MP.ppm test_images/out_blur.ppm static_1d blur
  ```
* **13x13 Box Blur (Static 2D Grid, 5 procese -> grilă 2x2):**
  ```bash
  mpirun --oversubscribe -np 5 ./mpi_image_proc test_images/sample_1.5MP.ppm test_images/out_blur.ppm static_2d blur:13
  ```
* **5x5 Box Blur (Dynamic Task Pool, 4 procese):**
  ```bash
  mpirun --oversubscribe -np 4 ./mpi_image_proc test_images/sample_1.5MP.ppm test_images/out_blur.ppm dynamic_1d blur:5
  ```

### C. Categoria 3: Mutare Pixeli & Schimbare Dimensiuni
* **Horizontal Flip (Static 1D, 4 procese):**
  ```bash
  mpirun --oversubscribe -np 4 ./mpi_image_proc test_images/sample_1.5MP.ppm test_images/out_rotate90.ppm static_1d flip
  ```
* **Rotate 90 deg Clockwise (W x H -> H x W, Dynamic 1D, 4 procese):**
  ```bash
  mpirun --oversubscribe -np 4 ./mpi_image_proc test_images/sample_1.5MP.ppm test_images/out_rotate90.ppm dynamic_1d rotate90
  ```

---

## 3. Pipeline Multi-Stage (Operații Înseriate)

* **Grayscale -> Blur -> Flip (Dynamic 1D, 4 procese):**
  ```bash
  mpirun --oversubscribe -np 4 ./mpi_image_proc test_images/sample_1.5MP.ppm test_images/out_grayscale_blur_flip.ppm dynamic_1d grayscale,blur:13,flip
  ```
* **Grayscale -> Rotate 90 deg CW -> Blur (Static 1D, 4 procese):**
  ```bash
  mpirun --oversubscribe -np 4 ./mpi_image_proc test_images/sample_1.5MP.ppm test_images/out_grayscale_blur_flip.ppm static_1d grayscale,rotate90,blur:5
  ```
* **Double Blur -> Invert (Dynamic 1D, 6 procese):**
  ```bash
  mpirun --oversubscribe -np 6 ./mpi_image_proc test_images/sample_1.5MP.ppm test_images/out_blur.ppm dynamic_1d blur:13,blur:5,invert
  ```

* Blur cu dimensiuni diferite și un blur implicit de 9x9 la final:

  ```bash
  mpirun --oversubscribe -np 5 ./mpi_image_proc test_images/sample_1.5MP.ppm output.ppm static_2d 'blur:13,grayscale,blur:5,blur:21,blur'
  ```

---

## 4. Mod Benchmark (Fără Scriere pe Disc)

Trimițând ```NONE``` ca fișier de ieșire, programul măsoară strict calculul și comunicația MPI:

```bash
mpirun --oversubscribe -np 4 ./mpi_image_proc test_images/sample_1.5MP.ppm NONE dynamic_1d blur:13
```

---

## 5. Rulare pe Cluster (Două Laptopuri)

```bash
mpirun --oversubscribe --host victus:4,HP-Laptop:4 ./mpi_image_proc test_images/sample_1.5MP.ppm test_images/out_grayscale_blur_flip.ppm dynamic_1d grayscale,blur:13,flip
```


## 6. Raportul benchmark

Cu `uv` instalat, rulează suita de măsurători și generează raportul:

```bash
uv run --with numpy --with matplotlib benchmark.py
```

`uv` instalează automat dependențele Python într-un mediu izolat.

Pentru cluster:

```bash
uv run --with numpy --with matplotlib benchmark.py --hosts victus:4,HP-Laptop:4
```

Programul necesită `mpicc` și `mpirun` și salvează rezultatele în
`benchmark_results.csv`. Raportul [experimental_study.md](experimental_study.md)
conține tabele și imagini PNG din `benchmark_figures/`. Include raportul și
acest director în commit pentru ca GitHub să afișeze graficele.

Suita folosește aceeași matrice pentru grayscale, blur, rotate90 și pipeline:

- Pe imaginea de 8MP, fiecare strategie paralelă rulează cu `np=2,3,4,5,6,8,9`.
- La `np=5`, fiecare strategie rulează pe imagini de 256×256, 1600×900,
  2400×1600 și 3840×2160 pixeli.
- Fiecare pereche imagine/operație are o referință secvențială.

Configurațiile comune sunt măsurate o singură dată. Cele 136 de configurații
rulează de cinci ori fiecare, în total 680 de rulări MPI. `static_2d` folosește
o grilă 2×2 la `np=5` și 4×2 la `np=9`.

`benchmark_runs.csv` păstrează timpii fiecărei repetări în secunde.
`benchmark_results.csv` conține mediile, abaterea standard a timpului total,
speedup-ul, eficiența și rezultatele verificării pixelilor. Prima repetare
a fiecărei configurații paralele este comparată integral cu referința
secvențială. Scrierea imaginilor și compararea pixelilor nu intră în timpii
măsurați. Raportul semnalează diferențele, iar programul încheie cu eroare
dacă găsește rezultate incorecte.

Raportul grupează graficele după întrebarea analizată. Tabelele complete
sunt în acordeoane pentru fiecare rezoluție. Timpii sunt afișați în ms,
ca medie ± abatere standard pentru timpul total. Concluziile provin din
măsurători; nu presupun că o anumită strategie câștigă întotdeauna.

În CSV, `avg_comm_s` este media timpului măsurat în apelurile MPI ale
coordonatorului, inclusiv așteptarea workerilor. Acest timp se suprapune cu
calculul workerilor, deci coloanele de timp nu se adună pentru a obține
timpul total. `avg_pack_s` include împachetarea, despachetarea și alocarea
bufferelor temporare. Feliile care ocupă întreaga lățime se transmit direct
și pot avea `avg_pack_s` egal cu zero.

Verificările generatorului se rulează astfel:

```bash
uv run --with numpy --with matplotlib python -m unittest -v test_benchmark.py
```

Graficul strategiilor are două coloane pentru fiecare strategie. Coloana C
arată timpul coordonatorului în trei segmente: pack/unpack cu alocările
asociate, alte operații locale și comunicație și așteptare MPI. Restul local
se calculează ca `avg_total_s - avg_comm_s - avg_pack_s`; include pregătirea
și planificarea taskurilor, administrarea memoriei din afara pack/unpack și
costul instrumentării. Transmiterea și colectarea prin apeluri MPI intră în
segmentul MPI. Cele trei segmente formează timpul total, în limita preciziei
măsurătorilor.
Coloana W arată media maximului timpului cumulat de calcul pe un worker
din fiecare rulare. Nu include timpii de așteptare și transfer ai workerului.
Coloanele C și W se suprapun în timp și nu se adună.

## Pilot de dezvoltare, blur cu coordonator pe Victus

Scriptul `benchmark_two_machines_small.py` măsoară numai blur 9×9 pe imaginea
256×256. Rangul 0 rulează întotdeauna pe Victus, inclusiv pentru configurațiile
cu workeri numai pe HP-Laptop. Limitele sunt 2 workeri HP-Laptop și 8 workeri
Victus, fără coordonator. Referința secvențială rulează tot pe Victus.

Din directorul `HW1`, cu ambele calculatoare accesibile prin SSH și cu același
director disponibil pe ambele, rulează:

```bash
uv run --with numpy --with matplotlib python benchmark_two_machines_small.py
```

Sunt 79 de configurații cu câte 3 repetări, în total 237 de rulări măsurate.
Scriptul compilează programul MPI și reia măsurătorile lipsă din jurnal.
Raportul rezultat este `experimental_study_256x256_blur_victus.md`, iar datele
și cele trei figuri sunt în `benchmark_small_two_machines_blur_victus/`.
Aceste rezultate sunt separate de pilotul anterior, care avea alte plasări
ale coordonatorului.

Pentru regenerarea raportului și figurilor după o rulare completă:

```bash
uv run --with numpy --with matplotlib python benchmark_two_machines_small.py --plot-only
```
