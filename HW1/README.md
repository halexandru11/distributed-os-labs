# HW1 — Procesarea imaginilor cu MPI

Programul C procesează imagini PPM (P6), secvențial sau în paralel, pe un calculator ori pe clusterul HP-Laptop + Victus. Comparăm timpul de execuție și speedup-ul pentru trei strategii de partiționare.

- **Operații:** `grayscale`, `invert`, `sepia`, `blur` (implicit 9×9, configurabil prin `blur:N`), `flip` și `rotate90`. Operațiile se pot înlănțui într-un pipeline.
- **Strategii:** `static_1d` (benzi orizontale), `static_2d` (grilă de blocuri), `dynamic_1d` (taskuri distribuite dinamic); `seq` oferă referința secvențială.
- **Procese:** rank 0 coordonează; în modurile paralele, celelalte `np - 1` procese sunt workeri.

## Documentație

- [USAGE.md](USAGE.md) — cerințe, compilare, exemple și rularea benchmark-urilor.
- [EXPERIMENTS.md](EXPERIMENTS.md) — metodologie, rezultate, limite și legături către rapoartele detaliate.
- [Vizualizarea partiționării](visualizarea_strategiilor_de_partitionare.md) — exemple pentru 1–10 workeri.

## Fișiere

- [mpi_image_proc.c](mpi_image_proc.c): implementarea MPI.
- `benchmark*.py` și `test_benchmark*.py`: măsurători, generarea rapoartelor și teste.
- [figures/](figures/): grafice grupate după experiment și rezoluție.
- `benchmark_two_machines/` și `benchmark_small_two_machines*/`: rezultate CSV, jurnale și metadate.
- `test_images/`: imagini PPM de intrare și exemple de ieșire.

[Toate temele](../README.md)
