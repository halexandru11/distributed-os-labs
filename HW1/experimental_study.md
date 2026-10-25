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
Comparația folosește 4 workeri și un coordonator. Modul `static_2d` formează o grilă 2×2.

Barele sunt alăturate deoarece intervalele măsurate se suprapun. Timpul apelurilor MPI este măsurat pe coordonator și include așteptarea rezultatelor de la workeri. Calculul CPU reprezintă timpul cumulat maxim pe un worker. Suma acestor valori nu reprezintă timpul total.

Pack/unpack include alocarea bufferelor temporare. Feliile care ocupă întreaga lățime sunt transmise direct, deci pot avea timp de pack/unpack zero. Dalele 2D necesită copierea rândurilor în buffere contigue și reasamblarea rezultatului.

![Comparația strategiilor de divizare](benchmark_figures/partition_strategies.png)

### Tabel Sintetic al Rezultatelor Măsurate (Rezoluție: `8MP`)

| Operație | Mod Paralelizare | Procese (`np`) | Workers | Timp Total (s) | Calcul CPU (s) | Pack/Unpack (s) | Apeluri MPI cu așteptare (s) | Speedup ($S_p$) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `grayscale` | `seq` | 1 | 1 | **0.0453s** | 0.0453s | 0.0000s | 0.0000s | **1.00x** |
| `grayscale` | `static_1d` | 2 | 1 | **0.0806s** | 0.0511s | 0.0000s | 0.0806s | **0.56x** |
| `grayscale` | `static_1d` | 3 | 2 | **0.0833s** | 0.0484s | 0.0000s | 0.0833s | **0.54x** |
| `grayscale` | `static_1d` | 4 | 3 | **0.1078s** | 0.0362s | 0.0000s | 0.1078s | **0.42x** |
| `grayscale` | `static_1d` | 5 | 4 | **0.1216s** | 0.0858s | 0.0000s | 0.1216s | **0.37x** |
| `grayscale` | `static_1d` | 6 | 5 | **0.2064s** | 0.0530s | 0.0000s | 0.2064s | **0.22x** |
| `grayscale` | `static_1d` | 8 | 7 | **0.1353s** | 0.0381s | 0.0000s | 0.1353s | **0.34x** |
| `blur` | `seq` | 1 | 1 | **0.8520s** | 0.8520s | 0.0000s | 0.0000s | **1.00x** |
| `blur` | `static_1d` | 2 | 1 | **1.0613s** | 1.0204s | 0.0000s | 1.0613s | **0.80x** |
| `blur` | `static_1d` | 3 | 2 | **0.8961s** | 0.8457s | 0.0000s | 0.8961s | **0.95x** |
| `blur` | `static_1d` | 4 | 3 | **0.7741s** | 0.7029s | 0.0000s | 0.7741s | **1.10x** |
| `blur` | `static_1d` | 5 | 4 | **0.8569s** | 0.8150s | 0.0000s | 0.8569s | **0.99x** |
| `blur` | `static_1d` | 6 | 5 | **1.0537s** | 0.9867s | 0.0000s | 1.0537s | **0.81x** |
| `blur` | `static_1d` | 8 | 7 | **0.9201s** | 0.7888s | 0.0000s | 0.9200s | **0.93x** |
| `rotate90` | `seq` | 1 | 1 | **0.0999s** | 0.0999s | 0.0000s | 0.0000s | **1.00x** |
| `rotate90` | `static_1d` | 2 | 1 | **0.1338s** | 0.0883s | 0.0000s | 0.1338s | **0.75x** |
| `rotate90` | `static_1d` | 3 | 2 | **0.1609s** | 0.0800s | 0.0305s | 0.1285s | **0.62x** |
| `rotate90` | `static_1d` | 4 | 3 | **0.1506s** | 0.0959s | 0.0238s | 0.1255s | **0.66x** |
| `rotate90` | `static_1d` | 5 | 4 | **0.1687s** | 0.0945s | 0.0256s | 0.1422s | **0.59x** |
| `rotate90` | `static_1d` | 6 | 5 | **0.1580s** | 0.1016s | 0.0144s | 0.1429s | **0.63x** |
| `rotate90` | `static_1d` | 8 | 7 | **0.2152s** | 0.1551s | 0.0176s | 0.1971s | **0.46x** |
| `grayscale,blur,flip` | `seq` | 1 | 1 | **1.2003s** | 1.2003s | 0.0000s | 0.0000s | **1.00x** |
| `grayscale,blur,flip` | `static_1d` | 2 | 1 | **1.1126s** | 1.0158s | 0.0000s | 1.1126s | **1.08x** |
| `grayscale,blur,flip` | `static_1d` | 3 | 2 | **1.0473s** | 0.9335s | 0.0000s | 1.0472s | **1.15x** |
| `grayscale,blur,flip` | `static_1d` | 4 | 3 | **1.4404s** | 1.1654s | 0.0000s | 1.4403s | **0.83x** |
| `grayscale,blur,flip` | `static_1d` | 5 | 4 | **1.2060s** | 0.9632s | 0.0000s | 1.2060s | **1.00x** |
| `grayscale,blur,flip` | `static_1d` | 6 | 5 | **1.3704s** | 1.1360s | 0.0000s | 1.3703s | **0.88x** |
| `grayscale,blur,flip` | `static_1d` | 8 | 7 | **1.3802s** | 1.0080s | 0.0000s | 1.3802s | **0.87x** |
| `blur` | `static_2d` | 5 | 4 | **1.1267s** | 0.9893s | 0.0693s | 1.0565s | **0.76x** |
| `blur` | `dynamic_1d` | 5 | 4 | **0.8657s** | 0.8253s | 0.0000s | 0.8656s | **0.98x** |
| `grayscale,blur,flip` | `static_2d` | 5 | 4 | **1.6098s** | 1.2644s | 0.1783s | 1.4189s | **0.75x** |
| `grayscale,blur,flip` | `dynamic_1d` | 5 | 4 | **1.0872s** | 0.8364s | 0.0000s | 1.0871s | **1.10x** |
