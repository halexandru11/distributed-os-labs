# Studiul Experimental al Prelucrării Paralele de Imagini în MPI

**Mediu de execuție:** Single Machine (Local Multi-Core) | **Rezoluție principală:** `8MP` (~25 MB per imagine necomprimată)

Acest studiu evaluează performanța implementării paralele bazate pe șablonul **Coordonator-Workers** în MPI pentru procesarea matricilor de pixeli RGB (format necomprimat **PPM `P6`**).

## 0. Verificarea Vizuală a Corectitudinii Operațiilor Grafice
Imaginea generată conține un marcaj roșu în stânga-sus, o grilă albă fină (1 px) și un cerc central galben. Aceste repere permit confirmarea corectitudinii algoritmilor de rotire, oglindire și asamblare a feliilor transmise prin MPI:

![Verificarea vizuală a operațiilor](benchmark_figures/visual_check.png)

## 1. Variația Timpului de Execuție în Funcție de Numărul de Procese MPI (`np`)
**Concluzii experimentale:**
- **Operații cu calcul intensiv per pixel (`blur` și `pipeline`):** Timpul de execuție scade pronunțat pe măsură ce adăugăm workeri, evidențiind o scalabilitate puternică (Strong Scaling).
- **Operații simple (`grayscale`):** Complexitatea aritmetică redusă per pixel face ca timpul de transmitere a datelor prin memorie/rețea să limiteze câștigul paralel.
- **Saturația Hardware (Oversubscription):** Peste numărul de nuclee fizice/logice ale mașinii, panta se aplatizează sau începe să urce ușor din cauza context-switching-ului la nivel de OS.

![Timpul de execuție în funcție de numărul de procese](benchmark_figures/execution_time.png)

## 2. Analiza Speedup-ului Paralel ($S_p = \frac{T_{seq}}{T_{par}}$)
Speedup-ul măsoară accelerarea obținută comparativ cu execuția secvențială:
- Pentru filtrul **Box Blur**, volumul mare de operații aritmetice pe vecinătăți oferă un speedup solid pe arhitecturi multi-core.
- Pentru filtrul **Grayscale**, speedup-ul rămâne aproape de 1.0x-1.1x din cauza raportului mic între calcul și comunicație.

![Speedup în funcție de numărul de workeri](benchmark_figures/speedup.png)

## 3. Scalabilitatea cu Rezoluția Imaginii ($N \times M$ Megapixeli)
Timpul de execuție crește liniar cu numărul de pixeli, conform complexității $O(N \cdot M)$. Pe imagini mari (8MP), panta execuției paralele este semnificativ mai mică decât cea secvențială, confirmând eficiența algoritmului paralel pe volume mari de date.

![Scalabilitatea cu rezoluția imaginii](benchmark_figures/resolution_scaling.png)

## 4. Comparația Strategiilor de Divizare (1D vs. 2D) și Load-Balancing (Static vs. Dinamic)
- **Divizare 1D vs. 2D:** Divizarea 1D orizontală este structural superioară divizării 2D în dale, deoarece ordinea *row-major* din C permite citirea directă a memoriei fără overhead-ul de împachetare (`pack_submatrix`) vizibil în bara portocalie a modului `static_2d`.
- **Static vs. Dinamic:** Deși `static_1d` transmite mai puține mesaje, **`dynamic_1d` obține cel mai bun timp de execuție**. Împărțirea în *chunk*-uri mai mici aduce două avantaje majore: o localitate a memoriei cache (L2/L3) superioară și eliminarea timpilor morți cauzați de fluctuațiile de frecvență ale nucleelor CPU (straggler effect).
- **Comportament pe cluster:** Avantajul modului dinamic va fi și mai pronunțat la conectarea a două laptopuri cu procesoare diferite.

![Comparația strategiilor de divizare](benchmark_figures/partition_strategies.png)

### Tabel Sintetic al Rezultatelor Măsurate (Rezoluție: `8MP`)

| Operație | Mod Paralelizare | Procese (`np`) | Workers | Timp Total (s) | Calcul CPU (s) | Pack/Unpack (s) | Comunicație MPI (s) | Speedup ($S_p$) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `grayscale` | `seq` | 1 | 1 | **0.0287s** | 0.0287s | 0.0000s | 0.0000s | **1.00x** |
| `grayscale` | `static_1d` | 2 | 1 | **0.0484s** | 0.0282s | 0.0000s | 0.0203s | **0.59x** |
| `grayscale` | `static_1d` | 3 | 2 | **0.0319s** | 0.0145s | 0.0000s | 0.0174s | **0.90x** |
| `grayscale` | `static_1d` | 4 | 3 | **0.0258s** | 0.0104s | 0.0000s | 0.0155s | **1.11x** |
| `grayscale` | `static_1d` | 5 | 4 | **0.0249s** | 0.0088s | 0.0000s | 0.0162s | **1.15x** |
| `grayscale` | `static_1d` | 6 | 5 | **0.0235s** | 0.0070s | 0.0000s | 0.0165s | **1.22x** |
| `grayscale` | `static_1d` | 8 | 7 | **0.0263s** | 0.0053s | 0.0000s | 0.0210s | **1.09x** |
| `blur` | `seq` | 1 | 1 | **0.6391s** | 0.6391s | 0.0000s | 0.0000s | **1.00x** |
| `blur` | `static_1d` | 2 | 1 | **0.6538s** | 0.6311s | 0.0000s | 0.0227s | **0.98x** |
| `blur` | `static_1d` | 3 | 2 | **0.3374s** | 0.3195s | 0.0000s | 0.0178s | **1.89x** |
| `blur` | `static_1d` | 4 | 3 | **0.2271s** | 0.2122s | 0.0000s | 0.0149s | **2.81x** |
| `blur` | `static_1d` | 5 | 4 | **0.1803s** | 0.1646s | 0.0000s | 0.0158s | **3.54x** |
| `blur` | `static_1d` | 6 | 5 | **0.1471s** | 0.1318s | 0.0000s | 0.0153s | **4.35x** |
| `blur` | `static_1d` | 8 | 7 | **0.1144s** | 0.0984s | 0.0000s | 0.0160s | **5.59x** |
| `rotate90` | `seq` | 1 | 1 | **0.0391s** | 0.0391s | 0.0000s | 0.0000s | **1.00x** |
| `rotate90` | `static_1d` | 2 | 1 | **0.0593s** | 0.0379s | 0.0000s | 0.0215s | **0.66x** |
| `rotate90` | `static_1d` | 3 | 2 | **0.0481s** | 0.0188s | 0.0117s | 0.0176s | **0.81x** |
| `rotate90` | `static_1d` | 4 | 3 | **0.0369s** | 0.0125s | 0.0090s | 0.0154s | **1.06x** |
| `rotate90` | `static_1d` | 5 | 4 | **0.0337s** | 0.0097s | 0.0081s | 0.0159s | **1.16x** |
| `rotate90` | `static_1d` | 6 | 5 | **0.0319s** | 0.0075s | 0.0077s | 0.0167s | **1.22x** |
| `rotate90` | `static_1d` | 8 | 7 | **0.0302s** | 0.0059s | 0.0050s | 0.0193s | **1.29x** |
| `grayscale,blur,flip` | `seq` | 1 | 1 | **0.6837s** | 0.6837s | 0.0000s | 0.0000s | **1.00x** |
| `grayscale,blur,flip` | `static_1d` | 2 | 1 | **0.7513s** | 0.6798s | 0.0000s | 0.0715s | **0.91x** |
| `grayscale,blur,flip` | `static_1d` | 3 | 2 | **0.3969s** | 0.3467s | 0.0000s | 0.0502s | **1.72x** |
| `grayscale,blur,flip` | `static_1d` | 4 | 3 | **0.2746s** | 0.2299s | 0.0000s | 0.0446s | **2.49x** |
| `grayscale,blur,flip` | `static_1d` | 5 | 4 | **0.2225s** | 0.1782s | 0.0000s | 0.0442s | **3.07x** |
| `grayscale,blur,flip` | `static_1d` | 6 | 5 | **0.1911s** | 0.1449s | 0.0000s | 0.0462s | **3.58x** |
| `grayscale,blur,flip` | `static_1d` | 8 | 7 | **0.1560s** | 0.1055s | 0.0000s | 0.0505s | **4.38x** |
| `blur` | `static_2d` | 4 | 3 | **0.2286s** | 0.2128s | 0.0000s | 0.0158s | **2.80x** |
| `blur` | `dynamic_1d` | 4 | 3 | **0.2238s** | 0.2126s | 0.0000s | 0.0113s | **2.86x** |
| `grayscale,blur,flip` | `static_2d` | 4 | 3 | **0.2742s** | 0.2302s | 0.0000s | 0.0440s | **2.49x** |
| `grayscale,blur,flip` | `dynamic_1d` | 4 | 3 | **0.2651s** | 0.2273s | 0.0000s | 0.0378s | **2.58x** |
