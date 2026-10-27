#!/usr/bin/env python3
"""Run the 256x256 two-machine pilot without replacing the original study."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
import tempfile
import time

import benchmark as b
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'benchmark_small_two_machines'
OPS = b.OPS
MODES = b.MODES
REPS = 3
CONFIGS = [(h, 0) for h in (1, 2)] + [(0, v) for v in range(1, 9)] + [(h, v) for h in (1, 2) for v in range(1, 9)]
PROFILES = [(2, 0), (0, 4), (2, 4), (2, 8)]
TITLES = ['HP-Laptop only', 'Victus only', 'HP-Laptop: 1 worker + Victus', 'HP-Laptop: 2 workers + Victus']
COLORS = ['#2878b5', '#e58b26', '#38945b']


def command(h, v, mode, op, output):
    args = [str(OUT / 'mpi_image_proc'), str(ROOT / 'test_images/sample_small.ppm'), str(output), mode, op]
    cmd = ['mpirun', '--oversubscribe', '--bind-to', 'none']
    if mode == 'seq':
        return cmd + ['-np', '1', '--host', 'HP-Laptop' if h else 'victus'] + args
    if h:
        cmd += ['-np', str(h + 1), '--host', 'HP-Laptop'] + args
        if v:
            cmd += [':', '-np', str(v), '--host', 'victus'] + args
    else:
        cmd += ['-np', str(v + 1), '--host', 'victus'] + args
    return cmd


def run(h, v, mode, op, output):
    result = subprocess.run(command(h, v, mode, op, output), cwd=ROOT, capture_output=True, text=True, timeout=90)
    if result.returncode:
        raise RuntimeError(result.stderr)
    line = next(x for x in result.stdout.splitlines() if x.startswith('BENCHMARK,'))
    parts = line.split(';')
    values = parts[0].split(',')
    metrics = dict(zip(['total', 'comm', 'pack', 'comp', 'send', 'wait'], map(float, values[-6:])))
    for part in parts[1:]:
        key, value = part.split('=', 1)
        metrics['workers_' + key] = [float(x) for x in value.split(':') if x]
    return metrics


def collect():
    OUT.mkdir(exist_ok=True)
    subprocess.run(['mpicc', '-O3', '-Wall', str(ROOT / b.C_SOURCE), '-o', str(OUT / 'mpi_image_proc')], check=True)
    image, w, h = b.read_ppm_for_plot(ROOT / 'test_images/sample_small.ppm', max_dim=None)
    assert (w, h) == (256, 256)
    metadata = {'date': time.strftime('%Y-%m-%d %H:%M:%S %z'), 'repetitions': REPS,
                'image_sha256': hashlib.sha256((ROOT / 'test_images/sample_small.ppm').read_bytes()).hexdigest(),
                'source_sha256': hashlib.sha256((ROOT / b.C_SOURCE).read_bytes()).hexdigest(),
                'binding': 'none', 'mixed_coordinator': 'HP-Laptop', 'machines': {}}
    for host in ['HP-Laptop', 'victus']:
        metadata['machines'][host] = subprocess.check_output(['ssh', '-o', 'BatchMode=yes', host, 'hostname; lscpu; mpirun --version'], text=True)
    (OUT / 'metadata.json').write_text(json.dumps(metadata, indent=2))
    path = OUT / 'runs.jsonl'
    previous = [json.loads(x) for x in path.read_text().splitlines()] if path.exists() else []
    done = {(x['op'], x['mode'], x['hp'], x['victus'], x['repeat']) for x in previous}
    jobs = [(op, 'seq', h, v) for op in OPS for h, v in [(1, 0), (0, 1)]]
    jobs += [(op, mode, h, v) for op in OPS for mode in MODES for h, v in CONFIGS]
    total = len(jobs) * REPS
    with tempfile.TemporaryDirectory(dir=OUT) as tmp, path.open('a', buffering=1) as raw:
        references = {}
        for op in OPS:
            reference = Path(tmp) / (op.replace(',', '_') + '.ppm')
            run(1, 0, 'seq', op, reference)
            references[op] = reference
        for op, mode, h, v in jobs:
            for repeat in range(REPS):
                key = (op, mode, h, v, repeat)
                if key in done:
                    continue
                candidate = Path(tmp) / 'candidate.ppm'
                metrics = run(h, v, mode, op, candidate if repeat == 0 else 'NONE')
                mismatch = b.compare_pixels(references[op], candidate)[0] if repeat == 0 else None
                if mismatch:
                    raise RuntimeError(f'Pixel mismatch: {key}: {mismatch}')
                row = dict(op=op, mode=mode, hp=h, victus=v, repeat=repeat, mismatched_pixels=mismatch, **metrics)
                raw.write(json.dumps(row) + '\n')
                done.add(key)
                print(f'{len(done)}/{total}: {op} {mode} HP={h} V={v} rep={repeat + 1}, {metrics["total"]*1000:.3f} ms', flush=True)
    return [json.loads(x) for x in path.read_text().splitlines()]


def figures_and_report(raw):
    grouped = {}
    for r in raw:
        grouped.setdefault((r['op'], r['mode'], r['hp'], r['victus']), []).append(r)
    rows = []
    for (op, mode, h, v), runs in grouped.items():
        row = dict(op=op, mode=mode, hp=0 if mode == 'seq' else h, victus=0 if mode == 'seq' else v, workers=0 if mode == 'seq' else h+v,
                   coordinator='HP-Laptop' if h else 'victus', repetitions=len(runs))
        for key in ['total', 'comm', 'pack', 'comp', 'send', 'wait']:
            row[key] = statistics.mean(r[key] for r in runs)
        row['std'] = statistics.stdev(r['total'] for r in runs)
        for key in ['workers_comp', 'workers_ops']:
            row[key] = [statistics.mean(r[key][i] for r in runs) for i in range(len(runs[0][key]))]
        row['verified'] = all(r['mismatched_pixels'] == 0 for r in runs if r['repeat'] == 0)
        rows.append(row)
    baselines = {(r['op'], r['coordinator']): r['total'] for r in rows if r['mode'] == 'seq'}
    for r in rows:
        r['speedup'] = baselines[r['op'], r['coordinator']] / r['total']
        r['efficiency'] = r['speedup'] / r['workers'] if r['workers'] else 1.0
    with (OUT / 'results.csv').open('w') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    with (OUT / 'runs.csv').open('w') as f:
        writer = csv.DictWriter(f, fieldnames=list(raw[0]) + ['coordinator'])
        writer.writeheader()
        writer.writerows(dict(r, hp=0 if r['mode'] == 'seq' else r['hp'], victus=0 if r['mode'] == 'seq' else r['victus'], coordinator='HP-Laptop' if r['hp'] else 'victus') for r in raw)
    report = ['# Studiu pilot pe două calculatoare, 256×256', '',
        'Imaginea `test_images/sample_small.ppm` are 65.536 pixeli. Acest raport păstrează studiul original și folosește numai imaginea de 256×256.', '',
        '## Metodologie', '',
        f'Am măsurat {len(rows)} de configurații, cu câte {REPS} repetări, în total {len(raw)} de rulări măsurate. Cele patru operații sunt grayscale, blur 9×9, rotate90 și pipeline-ul grayscale,blur,flip. Strategiile sunt static_1d, static_2d și dynamic_1d.', '',
        'HP-Laptop are un Intel Core i7-7500U, cu 2 nuclee și 4 fire hardware. Victus are un Intel Core i5-12500H și 16 fire hardware. Am folosit Open MPI 4.1.6, compilare `mpicc -O3 -Wall` și `--bind-to none`. Procesele rulează fără fixare pe nuclee. Coordonatorul este un proces suplimentar față de numărul de workeri.', '',
        'În rulările mixte, rangul 0 și primii 1 sau 2 workeri sunt pe HP-Laptop, iar restul workerilor sunt pe Victus. În rulările pe un singur calculator, coordonatorul rulează pe același calculator. Limitele de 2 și 8 se referă la workeri.', '',
        'Speedup = media timpului secvențial / media timpului paralel. Referința secvențială rulează pe calculatorul coordonatorului, deci HP-Laptop pentru configurațiile mixte. Eficiența este speedup / numărul total de workeri. Pe calculatoare diferite, acest raport depinde de performanța referinței secvențiale.', '',
        'Timpii provin din instrumentarea C și exclud lansarea MPI, citirea imaginii, scrierea rezultatului și verificarea pixelilor. Prima repetare a fiecărei configurații salvează rezultatul pentru comparație integrală cu referința secvențială. Celelalte repetări folosesc ieșirea NONE. Timpii sunt afișați ca medie și abatere standard. Trei repetări oferă o verificare pilot, cu precizie limitată pentru operațiile scurte.', '',
        'Cele patru panouri ale graficelor de timp și speedup folosesc aceeași limită verticală, calculată din maximul datelor afișate în acea figură, cu 10% spațiu suplimentar. Graficele strategiilor au două rânduri: configurațiile pe un singur calculator sus și configurațiile mixte jos. Fiecare rând folosește propria limită verticală comună, calculată din maximul celor două panouri, cu 10% spațiu suplimentar. Pentru timp sunt incluse benzile de abatere standard și referințele secvențiale; pentru strategii sunt incluse înălțimile totale ale barelor suprapuse. Limitele sunt calculate separat pentru fiecare operație și tip de grafic. Valorile extreme din aceeași figură pot comprima curbele și barele mai mici. Tabelele păstrează valorile numerice. Datele brute includ timpii fiecărui worker, distribuția pe calculatoare și datele necesare eficienței. Variația cu rezoluția necesită măsurători la alte dimensiuni și nu poate fi evaluată cu această singură imagine.', '']
    for op in OPS:
        slug = op.replace(',', '_')
        subset = [r for r in rows if r['op'] == op and r['mode'] != 'seq']
        # Share a scale within each four-panel figure, not across operations.
        time_max = max(
            max(r['total'] + r['std'] for r in subset),
            *(baselines[op, host] for host in ('HP-Laptop', 'victus')),
        ) * 1100
        speed_max = max(1, max(r['speedup'] for r in subset)) * 1.1
        report += [f'## {op}', '']
        for metric, filename, ylabel, limit in [('total', 'execution_time', 'Timp total (ms)', time_max), ('speedup', 'speedup', 'Speedup', speed_max)]:
            fig, axes = plt.subplots(1, 4, figsize=(22, 5), sharey=True)
            for idx, ax in enumerate(axes):
                for mode, color in zip(MODES, COLORS):
                    rr = [r for r in subset if r['mode'] == mode and ((idx == 0 and r['victus'] == 0) or (idx == 1 and r['hp'] == 0) or (idx >= 2 and r['hp'] == idx-1 and r['victus'] > 0))]
                    rr.sort(key=lambda r: r['hp'] if idx == 0 else r['victus'])
                    x = [r['hp'] if idx == 0 else r['victus'] for r in rr]
                    y = [r[metric] * (1000 if metric == 'total' else 1) for r in rr]
                    ax.plot(x, y, 'o-', color=color, label=mode)
                    if metric == 'total':
                        ax.fill_between(x, [a-r['std']*1000 for a, r in zip(y, rr)], [a+r['std']*1000 for a, r in zip(y, rr)], color=color, alpha=.15)
                if metric == 'total':
                    ax.axhline(baselines[op, 'victus' if idx == 1 else 'HP-Laptop']*1000, color='gray', linestyle='--', label='Secvențial')
                else:
                    ax.axhline(1, color='gray', linestyle='--')
                ax.set(title=TITLES[idx], xlabel='Workeri HP-Laptop' if idx == 0 else 'Workeri Victus', ylim=(0, limit))
                ax.set_xticks([1, 2] if idx == 0 else range(1, 9))
                ax.grid(alpha=.25)
            axes[0].set_ylabel(ylabel)
            handles, labels = axes[0].get_legend_handles_labels()
            fig.legend(handles, labels, loc='upper center', bbox_to_anchor=(.5, .95), ncol=4)
            fig.suptitle(f'{op} | 256×256', y=.995)
            fig.tight_layout(rect=(0, 0, 1, .86))
            fig.savefig(OUT / f'{filename}_{slug}.png', dpi=160, bbox_inches='tight')
            plt.close(fig)
            report += [f'![{ylabel}, {op}](benchmark_small_two_machines/{filename}_{slug}.png)', '']
        fig, axes = plt.subplots(2, 2, figsize=(20, 12), sharey='row')
        partition_limits = []
        for profiles in (PROFILES[:2], PROFILES[2:]):
            profile_rows = [r for r in subset if (r['hp'], r['victus']) in profiles]
            partition_limits.append(max(
                max(r['total'], r['pack'] + r['send'] + r['wait'],
                    *(comp + ops for comp, ops in zip(r['workers_comp'], r['workers_ops'])))
                for r in profile_rows
            ) * 1100)
        for idx, (ax, (h, v)) in enumerate(zip(axes.flat, PROFILES)):
            ticks, labels = [], []
            pos = 0
            for mode in MODES:
                r = next(r for r in subset if (r['mode'], r['hp'], r['victus']) == (mode, h, v))
                parts = [r['pack'], r['send'], r['wait'], max(0, r['total']-r['pack']-r['send']-r['wait'])]
                bottom = 0
                for value, color, label in zip(parts, ['#2878b5', '#173c60', '#e58b26', '#abc9dc'], ['C: pack/unpack', 'C: MPI send', 'C: MPI receive/wait', 'C: alte operații']):
                    ax.bar(pos, value*1000, bottom=bottom, color=color, label=label if pos == 0 else None)
                    bottom += value*1000
                ax.annotate(f'{r["total"]*1000:.2f} ms', (pos, r['total']*1000), xytext=(0, 6), textcoords='offset points', ha='center', fontsize=7, rotation=45)
                ticks.append(pos)
                labels.append('C\n' + ('HP' if h else 'V'))
                start = pos
                for i, (comp, ops) in enumerate(zip(r['workers_comp'], r['workers_ops'])):
                    pos += 1
                    ax.bar(pos, comp*1000, color='#38945b', label='W: calcul' if pos == 1 else None)
                    ax.bar(pos, ops*1000, bottom=comp*1000, color='#7bc1ac', label='W: alocare/transfer' if pos == 1 else None)
                    ticks.append(pos)
                    labels.append(f'W{i+1}\n' + ('HP' if i < h else 'V'))
                ax.text((start+pos)/2, -.29, mode, ha='center', transform=ax.get_xaxis_transform(), fontsize=10)
                pos += 2
            ax.set_xticks(ticks, labels, rotation=90, fontsize=7)
            ax.set(title=f'HP-Laptop: {h} workeri | Victus: {v} workeri', ylim=(0, partition_limits[idx // 2]))
            ax.grid(axis='y', alpha=.25)
        for ax in axes[:, 0]:
            ax.set_ylabel('Timp (ms)')
        handles, labels = axes[0, 0].get_legend_handles_labels()
        fig.legend(handles, labels, loc='upper center', bbox_to_anchor=(.5, .95), ncol=6)
        fig.suptitle(f'{op} | 256×256', y=.995)
        fig.tight_layout(rect=(0, .06, 1, .91), h_pad=7)
        fig.savefig(OUT / f'partition_strategies_{slug}.png', dpi=160, bbox_inches='tight')
        plt.close(fig)
        report += [f'![Strategii, {op}](benchmark_small_two_machines/partition_strategies_{slug}.png)', '']
        best = min(subset, key=lambda r: r['total'])
        report += [f'Cel mai mic timp paralel mediu este {best["total"]*1000:.3f} ms, cu {best["mode"]}, {best["hp"]} workeri HP-Laptop și {best["victus"]} workeri Victus. Speedup față de referința de pe {best["coordinator"]} este {best["speedup"]:.2f}.', '']
    worst = max((r for r in rows if r['mode'] != 'seq'), key=lambda r: r['std'] / r['total'])
    peak = max(raw, key=lambda r: r['total'])
    report += ['## Verificare și interpretare', '',
        f'Cea mai lentă repetare a durat {peak["total"]*1000:.3f} ms, pentru {peak["op"]}, {peak["mode"]}, cu {peak["hp"]} workeri HP-Laptop și {peak["victus"]} workeri Victus. Cea mai mare abatere standard relativă este {worst["std"]/worst["total"]*100:.1f}%, pentru {worst["op"]}, {worst["mode"]}, HP={worst["hp"]}, Victus={worst["victus"]}. Am păstrat toate repetările. Acest pilot verifică matricea și graficele, dar variația limitează concluziile despre ordinea strategiilor. Nu am măsurat separat rețeaua sau încărcarea de fond, deci nu pot atribui variația unei singure cauze.', '',
        f'Toate cele {len(rows)} de configurații au rezultate identice pixel cu pixel cu referința secvențială în prima repetare.', '',
        'Barele C și W se suprapun în timp și nu se adună. HP înseamnă HP-Laptop, iar V înseamnă Victus. Barele workerilor arată calculul și timpul instrumentat de alocare/transfer. Timpul rămas până la timpul coordonatorului nu este etichetat drept inactivitate, deoarece programul nu măsoară separat acea durată. Segmentele pack/unpack nu sunt defalcate per worker, deoarece instrumentarea oferă numai totalul coordonatorului.', '',
        '## Reproducere', '',
        'Scriptul separat este [benchmark_two_machines_small.py](benchmark_two_machines_small.py). Ambele calculatoare trebuie să acceseze același director și să accepte conexiuni SSH fără parolă. Rularea completă folosește comanda de mai jos. Scriptul reia configurațiile lipsă din jurnalul existent.', '',
        '```bash', 'uv run --with numpy --with matplotlib python benchmark_two_machines_small.py', '```', '',
        'Pentru regenerarea raportului și a figurilor din măsurătorile salvate:', '',
        '```bash', 'uv run --with numpy --with matplotlib python benchmark_two_machines_small.py --plot-only', '```', '',
        '## Date complete', '',
        'Datele sunt în [results.csv](benchmark_small_two_machines/results.csv), [runs.csv](benchmark_small_two_machines/runs.csv) și [runs.jsonl](benchmark_small_two_machines/runs.jsonl). Fișierul [metadata.json](benchmark_small_two_machines/metadata.json) păstrează informațiile calculatoarelor și hash-urile imaginii și sursei. În jurnalul intern JSONL, pentru modul seq, hp=1 sau victus=1 selectează calculatorul referinței, fără workeri. Fișierele CSV arată zero workeri pentru modul seq.', '',
        '| Operație | Strategie | HP workeri | Victus workeri | Coordonator | Total ms | Abatere ms | Speedup | Eficiență |',
        '| --- | --- | ---: | ---: | --- | ---: | ---: | ---: | ---: |']
    for r in rows:
        report.append(f'| {r["op"]} | {r["mode"]} | {r["workers"] if r["mode"] == "seq" else r["hp"]} | {0 if r["mode"] == "seq" else r["victus"]} | {r["coordinator"]} | {r["total"]*1000:.3f} | {r["std"]*1000:.3f} | {r["speedup"]:.3f} | {r["efficiency"]:.3f} |')
    (ROOT / 'experimental_study_256x256_two_machines.md').write_text('\n'.join(report) + '\n')
    print('Report written.', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plot-only', action='store_true', help='Regenerate the report from saved pilot measurements.')
    args = parser.parse_args()
    if args.plot_only:
        raw = [json.loads(line) for line in (OUT / 'runs.jsonl').read_text().splitlines()]
    else:
        raw = collect()
    expected = (len(OPS) * 2 + len(OPS) * len(MODES) * len(CONFIGS)) * REPS
    if len(raw) != expected:
        raise RuntimeError(f'Incomplete pilot: {len(raw)} measurements, expected {expected}')
    figures_and_report(raw)
