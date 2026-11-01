# Distribuirea imaginii între workeri

- **`static_1d`** împarte imaginea în benzi orizontale, câte una per worker.
- **`static_2d`** împarte imaginea într-o grilă. Pentru un număr prim de workeri, produce benzi orizontale.
- **`dynamic_1d`** creează `6 × P` benzi pentru `P` workeri. Următoarea bandă merge la workerul care termină.

Culorile identifică workerii, fără coordonator. La `dynamic_1d`, sunt colorate doar sarcinile atribuite inițial; benzile gri așteaptă în coadă. Diagramele arată regiunile de ieșire, fără marginile suplimentare necesare blur-ului.

[Varianta interactivă](partition_strategy_figures/interactive.html) · [Implementarea C](mpi_image_proc.c)

## Partiționarea pentru fiecare număr de workeri

| Workeri | Procese MPI cu coordonator | Grilă static_2d, coloane × rânduri | Benzi dynamic_1d |
| ---: | ---: | --- | ---: |
| `1` | `2` | `1×1` | `6` |
| `2` | `3` | `1×2` | `12` |
| `3` | `4` | `1×3` | `18` |
| `4` | `5` | `2×2` | `24` |
| `5` | `6` | `1×5` | `30` |
| `6` | `7` | `2×3` | `36` |
| `7` | `8` | `1×7` | `42` |
| `8` | `9` | `2×4` | `48` |
| `9` | `10` | `3×3` | `54` |
| `10` | `11` | `2×5` | `60` |

### 1 worker

![Partiționarea pentru 1 worker](partition_strategy_figures/workers_1.svg)

### 2 workeri

![Partiționarea pentru 2 workeri](partition_strategy_figures/workers_2.svg)

### 3 workeri

![Partiționarea pentru 3 workeri](partition_strategy_figures/workers_3.svg)

### 4 workeri

![Partiționarea pentru 4 workeri](partition_strategy_figures/workers_4.svg)

### 5 workeri

![Partiționarea pentru 5 workeri](partition_strategy_figures/workers_5.svg)

### 6 workeri

![Partiționarea pentru 6 workeri](partition_strategy_figures/workers_6.svg)

### 7 workeri

![Partiționarea pentru 7 workeri](partition_strategy_figures/workers_7.svg)

### 8 workeri

![Partiționarea pentru 8 workeri](partition_strategy_figures/workers_8.svg)

### 9 workeri

![Partiționarea pentru 9 workeri](partition_strategy_figures/workers_9.svg)

### 10 workeri

![Partiționarea pentru 10 workeri](partition_strategy_figures/workers_10.svg)
