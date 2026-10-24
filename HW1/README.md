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
