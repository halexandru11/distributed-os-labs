#!/usr/bin/env python3
"""Generate the combined study from saved CSVs; never launch MPI benchmarks."""
import csv
import json
import math
import statistics
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'benchmark_two_machines' / 'combined'
REPORT = ROOT / 'experimental_study_two_machines_combined.md'
SIZES = [('1.5MP', 1600, 900), ('4MP', 2400, 1600),
         ('8MP', 3840, 2160), ('64MP', 10667, 6000)]
OPS = ['grayscale', 'blur', 'rotate90', 'grayscale,blur,flip']
MODES = ['static_1d', 'static_2d', 'dynamic_1d']
COLORS = ['#2878b5', '#e58b26', '#38945b']
PROFILES = [(2, 0), (0, 8), (2, 4), (2, 8)]
ROWS = []


def get(size, op, mode, hp, victus):
    matches = [r for r in ROWS if (r['resolution'], r['op'], r['mode'], r['hp'], r['victus'])
               == (size, op, mode, hp, victus)]
    assert len(matches) == 1, (size, op, mode, hp, victus)
    return matches[0]


def load():
    hashes = set()
    for size, width, height in SIZES:
        folder = ROOT / 'benchmark_two_machines' / size
        meta = json.loads((folder / 'metadata.json').read_text())
        hashes.add(meta['source_sha256'])
        with (folder / 'runs.csv').open() as f:
            runs = list(csv.DictReader(f))
        with (folder / 'results.csv').open() as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == (80 if size == '64MP' else 320)
        assert len(runs) == len(rows) * 3
        for r in rows:
            for key in ['hp', 'victus', 'workers', 'repetitions']:
                r[key] = int(r[key])
            for key in ['total', 'std', 'speedup', 'efficiency']:
                r[key] = float(r[key])
                assert math.isfinite(r[key])
            group = [x for x in runs if all(str(r[k]) == x[k] for k in
                     ['op', 'mode', 'hp', 'victus', 'coordinator'])]
            assert len(group) == r['repetitions'] == 3
            assert sorted(int(x['repeat']) for x in group) == [0, 1, 2]
            assert next(x for x in group if x['repeat'] == '0')['mismatched_pixels'] == '0'
            assert r['verified'] == 'True'
            assert math.isclose(statistics.mean(float(x['total']) for x in group), r['total'])
            assert math.isclose(statistics.stdev(float(x['total']) for x in group), r['std'])
            r.update(resolution=size, width=width, height=height,
                     megapixels=width * height / 1e6,
                     throughput_mpps=width * height / 1e6 / r['total'],
                     relative_std_pct=100 * r['std'] / r['total'])
            ROWS.append(r)
    assert len(hashes) == 1, 'Source versions differ between studies'
    for r in ROWS:
        seq = next(x for x in ROWS if x['resolution'] == r['resolution']
                   and x['op'] == r['op'] and x['mode'] == 'seq'
                   and x['coordinator'] == r['coordinator'])
        assert math.isclose(r['speedup'], seq['total'] / r['total'])
        assert math.isclose(r['efficiency'], r['speedup'] / r['workers'] if r['workers'] else 1)


def panels(title):
    fig, axes = plt.subplots(1, 4, figsize=(22, 5), sharey=True)
    fig.suptitle(title, fontsize=14)
    return fig, axes


def finish(fig, axes, filename, ylabel):
    for ax in axes:
        ax.grid(axis='y', alpha=.25)
        ax.set_axisbelow(True)
    axes[0].set_ylabel(ylabel)
    axes[0].set_ylim(bottom=0, top=axes[0].get_ylim()[1] * 1.08)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='lower center', ncol=4, frameon=False)
    fig.tight_layout(rect=(0, .08, 1, .94))
    fig.savefig(OUT / filename, dpi=160, bbox_inches='tight')
    plt.close(fig)


def figures(op, sizes):
    slug = op.replace(',', '_')
    fig, axes = panels(f'{op}: timp la aceeași distribuție a workerilor')
    for ax, (h, v) in zip(axes, PROFILES):
        ax.set_title(f'HP={h}, Victus={v}')
        for mode, color in zip(MODES, COLORS):
            rs = [get(s, op, mode, h, v) for s in sizes]
            y = np.array([r['total'] * 1000 for r in rs])
            sd = np.array([r['std'] * 1000 for r in rs])
            ax.plot(range(len(sizes)), y, 'o-', color=color, label=mode)
            ax.fill_between(range(len(sizes)), np.maximum(0, y - sd), y + sd, color=color, alpha=.15)
        ax.set_xticks(range(len(sizes)), sizes)
        ax.set_xlabel('Rezoluție (categorii)')
    finish(fig, axes, f'execution_time_{slug}.png', 'Timp total (ms)')

    fig, axes = panels(f'{op}: speedup pe Victus, 1–8 workeri')
    for ax, (size, _, _) in zip(axes, SIZES):
        ax.set_title(size)
        if size not in sizes:
            ax.text(.5, .5, 'Operație nemăsurată', transform=ax.transAxes, ha='center')
            continue
        for mode, color in zip(MODES, COLORS):
            ax.plot(range(1, 9), [get(size, op, mode, 0, v)['speedup'] for v in range(1, 9)],
                    'o-', color=color, label=mode)
        ax.axhline(1, color='gray', linestyle=':', linewidth=1)
        ax.set_xticks(range(1, 9))
        ax.set_xlabel('Workeri Victus (+1 coordonator)')
    finish(fig, axes, f'speedup_{slug}.png', 'Speedup față de secvențial Victus')

    fig, axes = panels(f'{op}: strategii la 8 workeri Victus, cu/fără 2 workeri HP')
    for ax, (size, _, _) in zip(axes, SIZES):
        ax.set_title(size)
        if size not in sizes:
            ax.text(.5, .5, 'Operație nemăsurată', transform=ax.transAxes, ha='center')
            continue
        for j, (mode, color) in enumerate(zip(MODES, COLORS)):
            rs = [get(size, op, mode, h, 8) for h in (0, 2)]
            ax.bar(np.arange(2) + (j - 1) * .24, [r['total'] * 1000 for r in rs],
                   width=.24, color=color, label=mode,
                   yerr=[r['std'] * 1000 for r in rs], capsize=3)
        ax.set_xticks([0, 1], ['0 HP + 8 V', '2 HP + 8 V'])
    finish(fig, axes, f'partition_strategies_{slug}.png', 'Timp total (ms), medie ± SD')


def image(name, alt):
    return f'![{alt}](benchmark_two_machines/combined/{name})'


def table(headers, rows):
    return '\n'.join(['| ' + ' | '.join(headers) + ' |',
                      '| ' + ' | '.join(['---'] * len(headers)) + ' |'] +
                     ['| ' + ' | '.join(map(str, row)) + ' |' for row in rows])


def time_cell(row):
    return f'{row["total"]*1000:.3f} ± {row["std"]*1000:.3f}'


def main():
    load()
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / 'results.csv').open('w') as f:
        writer = csv.DictWriter(f, fieldnames=list(ROWS[0]))
        writer.writeheader()
        writer.writerows(ROWS)
    # Compare identical Victus allocations and scheduling; only HP workers are added.
    comparison = []
    for op in OPS:
        for size, _, _ in SIZES:
            if op != OPS[-1] and size == '64MP':
                continue
            alone = get(size, op, 'dynamic_1d', 0, 8)
            mixed = get(size, op, 'dynamic_1d', 2, 8)
            comparison.append((op, size, 100 * (mixed['total'] / alone['total'] - 1)))
    fig, ax = plt.subplots(figsize=(11, 7))
    values = [value for _, _, value in comparison]
    positions = np.arange(len(comparison))
    bars = ax.barh(positions, values, color=['#c44840' if v >= 0 else '#38945b' for v in values])
    ax.set_yticks(positions, [f'{op} — {size}' for op, size, _ in comparison])
    ax.invert_yaxis()
    ax.axvline(0, color='#555555', linewidth=1)
    ax.bar_label(bars, labels=[f'{v:+.0f}% timp' for v in values], padding=6, fontsize=10)
    ax.set_xlim(min(0, min(values)) - 15, max(values) * 1.24)
    ax.set_xlabel('Schimbarea timpului (%) față de Victus singur; mai puțin = mai bine')
    ax.set_title('Adăugarea HP la Victus crește sau reduce timpul?\n'
                 'dynamic_1d: 0 HP + 8 Victus → 2 HP + 8 Victus', pad=16)
    ax.grid(axis='x', alpha=.2)
    ax.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(OUT / 'adding_hp.png', dpi=160, bbox_inches='tight')
    plt.close(fig)
    report = ['# Studiu pe două calculatoare, comparație între rezoluții', '',
        'Comparăm `1.5MP`, `4MP`, `8MP` și `64MP`. La 64MP este măsurat numai pipeline-ul `grayscale,blur,flip`.', '',
        '## Ajută al doilea calculator?', '',
        image('adding_hp.png', 'Efectul adăugării HP la Victus'), '',
        '`dynamic_1d`: **8 workeri Victus → 8 Victus + 2 HP**. '
        'Roșu = mai lent; verde = mai rapid. `+100% timp` înseamnă durată dublă. '
        '**Adăugarea HP crește timpul mediu în toate cazurile afișate.**', '',
        '## Metodologie', '',
        'Conexiune Ethernet; HP: i7-7500U, 2 nuclee/4 fire; Victus: i5-12500H, 16 fire. '
        'Open MPI 4.1.6, `mpicc -O3 -Wall`, `--bind-to none`. '
        'Coordonatorul este suplimentar și rulează pe Victus, exceptând testele exclusiv HP.', '',
        *[f'- `{size}`: `sample_{size}.ppm`, {w}×{h} pixeli.' for size, w, h in SIZES], '',
        '**1040 configurații × 3 repetări = 3120 rulări**, cu blur 9×9. '
        'Timpii exclud lansarea MPI și operațiile pe fișiere; pipeline-ul însumează cele trei etape. '
        'Toate configurațiile au verificarea pixelilor trecută în prima repetare.', '',
        '**Speedup** = timp secvențial / timp paralel; **eficiență** = speedup / workeri; '
        '**CV** = 100 × SD / medie. SD este abaterea standard, nu un interval de încredere. '
        'Trei repetări limitează precizia comparațiilor.', '',
        '**Culori:** albastru = `static_1d`, portocaliu = `static_2d`, verde = `dynamic_1d`. '
        'Benzile și barele de eroare arată ± SD. Panourile aceleiași imagini au aceeași scară verticală.', '']
    for op in OPS:
        sizes = [size for size, _, _ in SIZES
                 if any(r['resolution'] == size and r['op'] == op for r in ROWS)]
        figures(op, sizes)
        slug = op.replace(',', '_')
        best = [min((r for r in ROWS if r['resolution'] == size and r['op'] == op and r['mode'] != 'seq'),
                    key=lambda r: r['total']) for size in sizes]
        report += [f'## {op}', '', '### Timp total', '',
            image(f'execution_time_{slug}.png', f'Timp total, {op}'), '',
            'Panouri: **2 HP**, **8 V**, **2 HP + 4 V**, **2 HP + 8 V**. '
            'X = rezoluție; Y = timp (ms). **Mai jos = mai rapid.**', '',
            '### Speedup', '', image(f'speedup_{slug}.png', f'Speedup pe Victus, {op}'), '',
            'Panouri: **1.5MP, 4MP, 8MP, 64MP**. X = workeri Victus (1–8); '
            'Y = speedup față de secvențialul Victus. **Mai sus = mai bine; sub 1× = mai lent decât secvențialul.**', '',
            '### Compararea strategiilor', '',
            image(f'partition_strategies_{slug}.png', f'Strategii, {op}'), '',
            'Aceleași panouri de rezoluție. În fiecare: **8 V** în stânga, **8 V + 2 HP** în dreapta. '
            'Barele arată timpul (ms). **Mai scurt = mai rapid.**', '',
            '### Cele mai bune rezultate observate', '',
            'Minimul mediu din toate configurațiile paralele, pentru fiecare imagine. '
            'Numărul de workeri poate diferi de cel din graficele de timp.', '',
            table(['Imagine', 'Timp ± SD (ms)', 'Strategie', 'HP', 'Victus', 'Speedup', 'Eficiență', 'CV'],
                  [[f'`sample_{r["resolution"]}.ppm`', time_cell(r), r['mode'], r['hp'], r['victus'],
                    f'{r["speedup"]:.2f}×', f'{r["efficiency"]*100:.1f}%',
                    f'{r["relative_std_pct"]:.1f}%'] for r in best]), '']
        notes = {
            'grayscale': 'Câștig modest; strategia cu minimul observat diferă între rezoluții.',
            'blur': 'La 8 workeri Victus, `dynamic_1d` crește de la 4.93× la 6.76× între 1.5MP și 8MP.',
            'rotate90': 'Minimele folosesc 7, 3 și 5 workeri Victus; 8 workeri nu oferă timpul minim.',
            'grayscale,blur,flip': '`dynamic_1d` cu 8 workeri Victus are timpul minim la toate rezoluțiile, cu speedup aproximativ 5×.',
        }
        report += [notes[op], '']
    report += ['## Reproducere', '',
        'Generatorul folosește datele salvate, fără rulări MPI:', '',
        '```bash', 'uv run --with numpy --with matplotlib python benchmark_two_machines_combined.py', '```', '',
        'Regenerează raportul, cele 13 grafice și CSV-ul agregat. Editați textul în generator pentru a-l păstra la regenerare.', '',
        '## Date complete', '',
        '[CSV agregat](benchmark_two_machines/combined/results.csv) · '
        '[Generator](benchmark_two_machines_combined.py). Timpii din CSV sunt în secunde.', '']
    for size, _, _ in SIZES:
        report += [f'- **{size}**: [studiu](experimental_study_two_machines_{size}.md), '
                   f'[rezultate](benchmark_two_machines/{size}/results.csv), '
                   f'[rulări](benchmark_two_machines/{size}/runs.csv), '
                   f'[metadata](benchmark_two_machines/{size}/metadata.json).']
    REPORT.write_text('\n'.join(report) + '\n')
    print(f'Validated {len(ROWS)} configurations; wrote {REPORT.name} and 13 PNGs in {OUT.relative_to(ROOT)}')


if __name__ == '__main__':
    main()
