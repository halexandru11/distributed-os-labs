# HW2 — Metodologia studiului experimental

[Utilizare și algoritmi](README.md) · [Rezultate și concluzii](results/study/report.md) · [CSV agregat](results/study/summary.csv)

## Acoperirea cerințelor

| Cerință | Implementare / date |
| --- | --- |
| 10 variante OpenMP | `matmul.c`: i, j, k; collapse ij/jk/ijk; nested ij/jk/ik/ijk |
| 2 combinații bonus | hybrid ij/k și i/jk |
| Referință secvențială și corectitudine | verificarea fiecărui element după fiecare încălzire/repetare; teste cu oracle Python |
| Măsurare doar calcule | timer în jurul apelului nucleului; pregătirea datelor și verificarea sunt separate |
| Dimensiuni pe scară logaritmică | pătrate 10³, 100³, 1000³; forme dreptunghiulare cu raport 100:1 |
| n mult mai mare decât m | (1000,10,10), (1000,10,1000) |
| m mult mai mare decât n | (10,1000,10), (10,1000,1000) |
| r mult mai mare decât n,m | (10,10,1000) |
| 5 serii aleatoare | seed-uri 1001–1005; aceleași perechi pentru variante/platforme |
| Intrări „best” și „worst” | zeros și UINT64_MAX în campaniile dimensiuni și schedule |
| Repetări și medii | 5 repetări după o încălzire; media repetărilor, apoi media pe seed-uri |
| GP consecutiv și oversubscription | 1–32 pe Victus, 1–8 pe HP-Laptop |
| Static/dynamic/guided, diverse chunk-uri | static implicit, static:1, static:8, dynamic:1, dynamic:8, guided:1, guided:8 |
| Parametri independenți per buclă | `--threads I,J,K`, `--schedule-i/-j/-k`; campania allocation |
| Memorie B pe coloane | layout row vs transposed, aceeași B logică |
| Comparația platformelor | rulări separate pe Victus și HP-Laptop; metadate CPU/RAM/OS/toolchain |
| Date tabelare și grafice | CSV brut/agregat, PNG/SVG, raport Markdown și prezentare HTML |
| Concluzii | minime observate, speedup/eficiență și limite statistice în raport |

## Alegerea spațiului de explorare

Enunțul cere o submulțime reprezentativă a unui domeniu de parametri foarte mare. Profilul implicit `study` separă factorii; nu pretinde că măsoară produsul cartezian al tuturor dimensiunilor, bugetelor, politicilor și layout-urilor.

| Campanie | Forme (n,m,r) | Variante | GP | Intrări | Alte variabile |
| --- | --- | --- | --- | --- | --- |
| dimensions | cele 8 forme de mai sus | toate 12 + seq | 4 | 5 random + zeros + max | static, B row |
| threads | (10,10,10) | toate 12 + seq | consecutiv 1–2×CPU logice, minimum 8 | 5 random | static, B row |
| scaling | (300,300,300) | i, collapse ij + seq | aceeași plajă consecutivă | 5 random | static, B row |
| schedules | (10,10,10) | toate 12 + seq | 4 | 5 random + zeros + max | cele 7 schedule-uri |
| schedules_large | (300,300,300) | i, collapse ij + seq | 4 | 5 random + zeros + max | cele 7 schedule-uri |
| layout | (100,100,100) | toate 12 + seq | 4 | 5 random | B row/transposed |
| layout_large | (1000,1000,1000) | i, collapse ij + seq | 4 | 1 random | B row/transposed |
| allocation | (10,10,10) | cele 6 variante nested/hybrid + seq | total 8 | 5 random | 3 repartizări × static/mixed per nivel |

La fiecare configurație sunt cinci repetări ale aceleiași perechi de matrici, distincte de cele cinci seed-uri. Seed-urile sunt fixe pentru reproducere, dar diferite între seriile aleatoare. Configurațiile sunt amestecate într-o ordine pseudoaleatoare reproductibilă (seed 2026); experimentele nu rulează simultan, iar cele două calculatoare sunt parcurse consecutiv. Matricile de aceeași formă/distribuție/seed sunt identice între variante, bugete și schedule-uri.

Matricile mari evidențiază costul memoriei și oportunitatea accelerării. Cele mici permit parcurgerea bugetelor și a tuturor variantelor fără ca variantele cu echipe interioare să blocheze întregul studiu. La 300³ se repetă explorarea bugetelor pentru variantele eficiente; astfel concluzia despre scalare nu se bazează doar pe produse minuscule. Limita superioară 1000 pentru dimensiunile pătrate și limitele de execuție păstrează studiul finit.

## Protocol și timeout-uri

Pentru fiecare configurație:

1. Se alocă/gene­rează A și B, se pregătesc layout-ul și paginile rezultatului.
2. Se dezactivează ajustarea dinamică a echipelor și se activează maximum trei niveluri OpenMP.
3. Se probează echipele cerute, în afara măsurării; se salvează min/max realizate pe nivel.
4. Se construiește B logică pe linii și se calculează referința independentă.
5. Se face o încălzire verificată.
6. Pentru fiecare repetare se resetează C, se măsoară nucleul, se verifică toate elementele și se emite o înregistrare JSON.

Benchmark-ul folosește timeout-uri de **3 s pentru invocarea procesului**, respectiv **30 s pentru cazurile mari seq/i/j/collapse(ij)**. Acestea includ pregătirea, referința, încălzirea și repetările. Valorile sunt un buget practic al colectării și nu un prag de comparație pentru timpul unui singur nucleu. Pentru repetarea cu aceeași limită pentru toate variantele se pot seta ambele opțiuni la aceeași valoare.

Se păstrează ieșirea completă deja emisă înainte de întrerupere. Un seed care nu a finalizat toate cele cinci repetări nu contribuie deloc la medie. Dacă un grup are doar o parte dintre seed-uri complete, este marcat PARTIAL și exclus din clasamente/grafice. Timeout-ul nu este înlocuit cu valoarea numerică a limitei. O eroare de calcul oprește colectarea cu eroare, în loc să devină un timp valid.

## Statisticile și interpretarea

Pentru timpii t[s,q], unde s este seed-ul și q repetarea:

```text
media_seed[s] = sum(t[s,q], q=1..5) / 5
media_configurație = sum(media_seed[s], s=1..5) / 5
speedup = media_seq / media_paralel
eficiență = speedup / GP
CV = 100 × deviația_standard_a_repetărilor / media_configurație
```

Pentru zeros/max există o singură pereche și cinci repetări. Se păstrează media, mediana, minimul, maximul, deviația standard a repetărilor și deviația standard a mediilor pe seed-uri. Media pe seed-uri are ponderi egale; nu se combină selectiv repetări rapide din configurații întrerupte. CSV-ul agregat include `series_expected`, `series_complete`, `samples`, `timeouts` și `status`.

Referințele `seq` pentru speedup sunt măsurate separat în fiecare campanie și pentru fiecare formă, seed, distribuție și layout. Referința folosită pentru verificarea unui proces paralel nu este tratată drept o repetare suplimentară a benchmark-ului. Pentru o configurație cu mai multe seed-uri, speedup este raportul mediilor, nu media rapoartelor.

„GP optim” și „schedule optim” înseamnă minimum observat în grila dată. Diferențele mici, comparabile cu variația măsurării, nu demonstrează superioritate stabilă. Studiul nu estimează un minim global al spațiului infinit de parametri și nu susține că un singur algoritm este optim în toate cazurile.

## Reproducere și grile suplimentare

Din `HW2`:

```bash
# Colectare pe ambele calculatoare; apoi raport din aceleași date:
python3 benchmark.py --hosts local HP-Laptop --collect-only
python3 analyze.py --input results/study

# Aceeași durată maximă pentru toate procesele; director nou:
python3 benchmark.py --timeout 10 --large-timeout 10 --collect-only \
  --output results/study_uniform_timeout

# Produs cartezian explicit al dimensiunilor, bugetelor, politicilor și intrărilor:
python3 benchmark.py --profile full --shapes 10x10x10 100x100x100 \
  --max-threads 8 --schedules static static:8 dynamic:1 guided:8 \
  --layouts row transposed --series 5 --repeats 5 --collect-only \
  --output results/full_small

# O singură familie de factori, fără a modifica studiul existent:
python3 benchmark.py --campaigns scaling --max-threads 8 --collect-only \
  --output results/scaling_repeat
```

Profilul `full` adaugă referințele seq o singură dată pentru fiecare formă/layout/intrare. Planul exact este salvat în `plan.json`. Pentru o mașină nouă, instalează GCC/OpenMP și Python, apoi folosește `--hosts nume-ssh` sau copiază directorul HW2 și rulează local. `--collect-only` nu necesită Matplotlib/NumPy.

Reexecutarea unei colectări locale o reia din `runs.jsonl`. Scriptul refuză amestecarea datelor cu surse, plan, mediu OpenMP sau setări diferite. Dacă o invocare a fost întreruptă extern înainte de a finaliza sau marca TIMEOUT, probele ei incomplete sunt eliminate la reluare. Datele dintr-o colectare remote întreruptă rămân în directorul temporar indicat în mesajul de eroare și pot fi recuperate prin SSH/SCP.

## Limite asumate

- Aritmetica este uint64_t modulo 2⁶⁴. Nu se măsoară precizie arbitrară și nu se compară mai multe tipuri numerice; acestea sunt extensii opționale în enunț.
- Sunt folosite două platforme fizice accesibile, cu servicii obișnuite active. Metadatele conțin load-ul și guvernorii CPU; nu se pretinde un mediu exclusiv perfect.
- B transpus exclude costul pregătirii din măsurare, conform cerinței de a cronometra calculele propriu-zise.
- Numărul de page faults este înregistrat. Nu există un experiment controlat care să separe cache misses, paginare, frecvență și încărcarea externă.
- Nu se schimbă configurația gazdelor, SMT, guvernorii CPU sau serviciile sistemului. Comparațiile Docker/VM și cu HT dezactivat nu sunt efectuate.
- Cazurile TIMEOUT indică limita bugetului de colectare, fără a stabili un timp precis sau clasamentul între variantele întrerupte.

## Fișiere rezultate

| Fișier | Conținut |
| --- | --- |
| `results/study/<host>/runs.jsonl` | toate repetările verificate și evenimentele terminale |
| `results/study/<host>/runs.csv` | aceleași date în format importabil într-un spreadsheet |
| `results/study/<host>/metadata.json` | hardware, software, mediu, load, momente, hash-uri |
| `results/study/<host>/plan.json` | fiecare configurație solicitată |
| `results/study/summary.csv` | agregare pe factori, statisticile și speedup/eficiență |
| `results/study/failures.csv` | timeout-uri și eventuale erori, fără timpi inventați |
| `results/study/report.md` | tabelele măsurate și concluziile |
| `results/study/dashboard.html` | prezentare autonomă cu imagini încorporate |
| `figures/study/*.png`, `*.svg` | șapte comparații vizuale, pentru prezentare și export |

CSV-urile pot fi importate direct în LibreOffice/Excel, cu separator virgulă și punct zecimal. Raportul se regenerează exclusiv din datele salvate, fără relansarea experimentelor.
