#!/usr/bin/env python3
"""Benchmark the grayscale,blur,flip pipeline on sample_64MP.ppm on two machines."""
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
OUTPUT_ROOT = ROOT / 'benchmark_two_machines'
RESOLUTIONS = [('64MP', 10667, 6000)]
RESOLUTION = RESOLUTIONS[0]
OUT = OUTPUT_ROOT / RESOLUTION[0]
OPS = ['grayscale,blur,flip']
PROGRESS = None
MODES = b.MODES
REPS = 3
CONFIGS = [(h, 0) for h in (1, 2)] + [(0, v) for v in range(1, 9)] + [(h, v) for h in (1, 2) for v in range(1, 9)]
PROFILES = [(2, 0), (0, 4), (2, 4), (2, 8)]
TITLES = ['HP-Laptop workers only', 'Victus workers only', 'HP-Laptop: 1 worker + Victus', 'HP-Laptop: 2 workers + Victus']
COLORS = ['#2878b5', '#e58b26', '#38945b']


def image_path():
    return ROOT / 'test_images' / f'sample_{RESOLUTION[0]}.ppm'


def load_selected_runs(path):
    if not path.exists():
        return []
    records = [json.loads(line) for line in path.read_text().splitlines()]
    return [record for record in records if record['op'] in OPS]


def jobs():
    return ([(op, 'seq', h, 0) for op in OPS for h in (1, 0)]
            + [(op, mode, h, v) for op in OPS for mode in MODES for h, v in CONFIGS])


class Progress:
    def __init__(self, total, completed=0):
        self.total = total
        self.completed = completed
        self.initial = completed
        self.started = time.monotonic()

    @staticmethod
    def duration(seconds):
        seconds = max(0, int(seconds))
        return f'{seconds // 3600:02d}:{seconds // 60 % 60:02d}:{seconds % 60:02d}'

    def show(self, label):
        elapsed = time.monotonic() - self.started
        fresh = self.completed - self.initial
        eta = self.duration(elapsed / fresh * (self.total - self.completed)) if fresh else 'estimating'
        print(f'\r\033[2K{self.completed}/{self.total} | elapsed {self.duration(elapsed)} | ETA {eta} | {label}', end='', flush=True)



def coordinator(h, v):
    return 'HP-Laptop' if h and not v else 'victus'


def command(h, v, mode, op, output):
    args = [str(OUT / 'mpi_image_proc'), str(image_path()), str(output), mode, op]
    cmd = ['mpirun', '--oversubscribe', '--bind-to', 'none']
    # Open MPI assigns rank 0 to the first application context.
    # Keep the coordinator separate so ranks 1..h remain HP workers.
    cmd += ['-np', '1', '--host', coordinator(h, v)] + args
    if mode != 'seq':
        for host, count in [('HP-Laptop', h), ('victus', v)]:
            if count:
                cmd += [':', '-np', str(count), '--host', host] + args
    return cmd



def run(h, v, mode, op, output):
    label = f'{RESOLUTION[0]} {op} {mode} HP={h} V={v}'
    with subprocess.Popen(command(h, v, mode, op, output), cwd=ROOT,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) as process:
        started = time.monotonic()
        while True:
            if PROGRESS:
                PROGRESS.show(label)
            try:
                stdout, stderr = process.communicate(timeout=1)
                break
            except subprocess.TimeoutExpired:
                if time.monotonic() - started >= 300:
                    process.kill()
                    process.communicate()
                    raise RuntimeError(f'MPI job exceeded 300 seconds: {label}')
        if process.returncode:
            raise RuntimeError(stderr)
    line = next(x for x in stdout.splitlines() if x.startswith('BENCHMARK,'))
    parts = line.split(';')
    values = parts[0].split(',')
    metrics = dict(zip(['total', 'comm', 'pack', 'comp', 'send', 'wait'], map(float, values[-6:])))
    for part in parts[1:]:
        key, value = part.split('=', 1)
        metrics['workers_' + key] = [float(x) for x in value.split(':') if x]
    return metrics


def collect():
    OUT.mkdir(parents=True, exist_ok=True)
    subprocess.run(['mpicc', '-O3', '-Wall', str(ROOT / b.C_SOURCE), '-o', str(OUT / 'mpi_image_proc')], check=True)
    _, w, h = b.read_ppm_for_plot(image_path(), max_dim=None)
    if (w, h) != RESOLUTION[1:]:
        raise ValueError(f'Unexpected dimensions for {image_path()}: {w}x{h}')
    metadata = {'date': time.strftime('%Y-%m-%d %H:%M:%S %z'), 'repetitions': REPS,
                'image_sha256': hashlib.sha256(image_path().read_bytes()).hexdigest(),
                'source_sha256': hashlib.sha256((ROOT / b.C_SOURCE).read_bytes()).hexdigest(),
                'resolution': RESOLUTION[0], 'operations': OPS, 'binding': 'none', 'coordinator': 'HP-Laptop for HP-only; victus otherwise', 'machines': {}}
    for host in ['HP-Laptop', 'victus']:
        metadata['machines'][host] = subprocess.check_output(['ssh', '-o', 'BatchMode=yes', host, 'hostname; lscpu; mpirun --version'], text=True)
    metadata_path = OUT / 'metadata.json'
    if metadata_path.exists():
        previous_metadata = json.loads(metadata_path.read_text())
        for field in ['image_sha256', 'source_sha256', 'repetitions', 'binding', 'coordinator']:
            if previous_metadata.get(field) != metadata[field]:
                raise RuntimeError(f'Cannot resume changed {field}; use a fresh output directory: {OUT}')
    else:
        metadata_path.write_text(json.dumps(metadata, indent=2))
    path = OUT / 'runs.jsonl'
    previous = load_selected_runs(path)
    validate_records(previous, complete=False)
    done = {(x['op'], x['mode'], x['hp'], x['victus'], x['repeat']) for x in previous}
    pending_jobs = jobs()
    total = len(pending_jobs) * REPS
    if len(done) == total:
        return previous
    with tempfile.TemporaryDirectory(dir=OUT) as tmp, path.open('a', buffering=1) as raw:
        references = {}
        for op in OPS:
            reference = Path(tmp) / (op.replace(',', '_') + '.ppm')
            run(0, 0, 'seq', op, reference)
            references[op] = reference
        for op, mode, h, v in pending_jobs:
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
                PROGRESS.completed += 1
                PROGRESS.show(f'{RESOLUTION[0]} {op} {mode} HP={h} V={v} rep={repeat + 1}, {metrics["total"]*1000:.3f} ms')
                print(flush=True)
    return load_selected_runs(path)


def figures_and_report(raw, time_limit=None, speed_limit=None):
    grouped = {}
    for r in raw:
        grouped.setdefault((r['op'], r['mode'], r['hp'], r['victus']), []).append(r)
    rows = []
    for (op, mode, h, v), runs in grouped.items():
        row = dict(op=op, mode=mode, hp=0 if mode == 'seq' else h, victus=0 if mode == 'seq' else v, workers=0 if mode == 'seq' else h+v,
                   coordinator=coordinator(h, v), repetitions=len(runs))
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
        writer.writerows(dict(r, hp=0 if r['mode'] == 'seq' else r['hp'], victus=0 if r['mode'] == 'seq' else r['victus'], coordinator=coordinator(r['hp'], r['victus'])) for r in raw)
    time_max = time_limit or max(r['total'] + r['std'] for r in rows) * 1100
    speed_max = speed_limit or max(1, max(r['speedup'] for r in rows)) * 1.1
    report = [f'# Studiu pe două calculatoare, {RESOLUTION[0]}', '',
        f'Imaginea `test_images/sample_{RESOLUTION[0]}.ppm` are {RESOLUTION[1]}×{RESOLUTION[2]} pixeli. Rezultatele sunt separate de studiile anterioare.', '',
        '## Metodologie', '',
        f'Am măsurat {len(rows)} de configurații, cu câte {REPS} repetări, în total {len(raw)} de rulări măsurate. Măsurăm numai pipeline-ul grayscale,blur,flip, cu blur 9×9. Strategiile sunt static_1d, static_2d și dynamic_1d.', '',
        'HP-Laptop are un Intel Core i7-7500U, cu 2 nuclee și 4 fire hardware. Victus are un Intel Core i5-12500H și 16 fire hardware. Am folosit Open MPI 4.1.6, compilare `mpicc -O3 -Wall` și `--bind-to none`. Procesele rulează fără fixare pe nuclee. Coordonatorul este un proces suplimentar față de numărul de workeri.', '',
        'Rangul 0 rulează pe HP-Laptop pentru testele exclusiv pe HP-Laptop și pe Victus pentru celelalte teste. Graficul HP-Laptop include 1 proces secvențial, 2 procese cu un worker și 3 procese cu doi workeri. Rangurile 1 până la numărul de workeri HP-Laptop rulează pe HP-Laptop, iar workerii rămași rulează pe Victus. Limitele de 2 și 8 se referă la workeri, fără coordonator.', '',
        'Speedup = media timpului secvențial / media timpului paralel. Referința secvențială rulează pe HP-Laptop pentru testele exclusiv pe HP-Laptop și pe Victus pentru celelalte teste. Eficiența este speedup / numărul total de workeri. Pe calculatoare diferite, acest raport depinde de performanța referinței secvențiale.', '',
        'Timpii provin din instrumentarea C și exclud lansarea MPI, citirea imaginii, scrierea rezultatului și verificarea pixelilor. Prima repetare a fiecărei configurații salvează rezultatul pentru comparație integrală cu referința secvențială. Celelalte repetări folosesc ieșirea NONE. Timpii sunt afișați ca medie și abatere standard. Trei repetări oferă o verificare pilot, cu precizie limitată pentru operațiile scurte.', '',
        'Toate graficele de timp folosesc aceeași limită verticală, inclusiv graficele strategiilor. Graficele de speedup folosesc o limită comună. Valorile extreme ridică limita verticală, astfel că unele curbe și bare sunt aproape de zero pe această scară. Tabelele păstrează valorile numerice. Datele brute includ timpii fiecărui worker, distribuția pe calculatoare și datele necesare eficienței. Această rulare măsoară numai imaginea de 64MP. CSV-urile păstrează eficiența și pot fi comparate cu rezultatele anterioare la alte rezoluții.', '']
    for op in OPS:
        slug = op.replace(',', '_')
        subset = [r for r in rows if r['op'] == op and r['mode'] != 'seq']
        report += [f'## {op}', '']
        for metric, filename, ylabel, limit in [('total', 'execution_time', 'Timp total (ms)', time_max), ('speedup', 'speedup', 'Speedup', speed_max)]:
            fig, axes = plt.subplots(1, 4, figsize=(22, 5), sharey=True)
            for idx, ax in enumerate(axes):
                for mode, color in zip(MODES, COLORS):
                    rr = [r for r in subset if r['mode'] == mode and ((idx == 0 and r['victus'] == 0) or (idx == 1 and r['hp'] == 0) or (idx >= 2 and r['hp'] == idx-1 and r['victus'] > 0))]
                    rr.sort(key=lambda r: r['hp'] if idx == 0 else r['victus'])
                    if idx == 0:
                        rr = [next(r for r in rows if r['op'] == op and r['mode'] == 'seq' and r['coordinator'] == 'HP-Laptop')] + rr
                    x = [r['workers'] + 1 if idx == 0 else r['victus'] for r in rr]
                    y = [r[metric] * (1000 if metric == 'total' else 1) for r in rr]
                    ax.plot(x, y, 'o-', color=color, label=mode)
                    if metric == 'total':
                        ax.fill_between(x, [a-r['std']*1000 for a, r in zip(y, rr)], [a+r['std']*1000 for a, r in zip(y, rr)], color=color, alpha=.15)
                if metric == 'total':
                    ax.axhline(baselines[op, 'HP-Laptop' if idx == 0 else 'victus']*1000, color='gray', linestyle='--', label='Secvențial')
                else:
                    ax.axhline(1, color='gray', linestyle='--')
                ax.set(title=TITLES[idx], xlabel='Procese HP-Laptop, inclusiv coordonatorul' if idx == 0 else 'Workeri Victus', ylim=(0, limit))
                ax.set_xticks([1, 2, 3] if idx == 0 else range(1, 9))
                ax.grid(alpha=.25)
            axes[0].set_ylabel(ylabel)
            handles, labels = axes[0].get_legend_handles_labels()
            fig.legend(handles, labels, loc='upper center', bbox_to_anchor=(.5, .95), ncol=4)
            fig.suptitle(f'{op} | {RESOLUTION[0]}', y=.995)
            fig.tight_layout(rect=(0, 0, 1, .86))
            fig.savefig(OUT / f'{filename}_{slug}.png', dpi=160, bbox_inches='tight')
            plt.close(fig)
            report += [f'![{ylabel}, {op}](benchmark_two_machines/{RESOLUTION[0]}/{filename}_{slug}.png)', '']
        fig, axes = plt.subplots(1, 4, figsize=(30, 7), sharey=True)
        for ax, (h, v) in zip(axes, PROFILES):
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
                labels.append('C\n' + ('HP' if coordinator(h, v) == 'HP-Laptop' else 'V'))
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
            ax.set(title=f'HP-Laptop: {h} workeri | Victus: {v} workeri', ylim=(0, time_max))
            ax.grid(axis='y', alpha=.25)
        axes[0].set_ylabel('Timp (ms)')
        handles, labels = axes[0].get_legend_handles_labels()
        fig.legend(handles, labels, loc='upper center', bbox_to_anchor=(.5, .95), ncol=6)
        fig.suptitle(f'{op} | {RESOLUTION[0]}', y=.995)
        fig.tight_layout(rect=(0, .12, 1, .86))
        fig.savefig(OUT / f'partition_strategies_{slug}.png', dpi=160, bbox_inches='tight')
        plt.close(fig)
        report += [f'![Strategii, {op}](benchmark_two_machines/{RESOLUTION[0]}/partition_strategies_{slug}.png)', '']
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
        f'Datele sunt în [results.csv](benchmark_two_machines/{RESOLUTION[0]}/results.csv), [runs.csv](benchmark_two_machines/{RESOLUTION[0]}/runs.csv) și [runs.jsonl](benchmark_two_machines/{RESOLUTION[0]}/runs.jsonl). Fișierul [metadata.json](benchmark_two_machines/{RESOLUTION[0]}/metadata.json) păstrează informațiile calculatoarelor și hash-urile imaginii și sursei. Câmpurile hp și victus reprezintă numărul de workeri. În CSV, modul seq are zero workeri și coloana coordinator identifică laptopul. În jurnalul JSONL, hp=1 selectează referința secvențială HP-Laptop, iar hp=0 selectează Victus.', '',
        '| Operație | Strategie | HP workeri | Victus workeri | Coordonator | Total ms | Abatere ms | Speedup | Eficiență |',
        '| --- | --- | ---: | ---: | --- | ---: | ---: | ---: | ---: |']
    for r in rows:
        report.append(f'| {r["op"]} | {r["mode"]} | {r["workers"] if r["mode"] == "seq" else r["hp"]} | {0 if r["mode"] == "seq" else r["victus"]} | {r["coordinator"]} | {r["total"]*1000:.3f} | {r["std"]*1000:.3f} | {r["speedup"]:.3f} | {r["efficiency"]:.3f} |')
    (ROOT / f'experimental_study_two_machines_{RESOLUTION[0]}.md').write_text('\n'.join(report) + '\n')
    print('Report written.', flush=True)


def validate_records(raw, complete=True):
    expected = {(op, mode, h, v, repeat)
                for op, mode, h, v in jobs() for repeat in range(REPS)}
    actual = [(r['op'], r['mode'], r['hp'], r['victus'], r['repeat']) for r in raw]
    if len(actual) != len(set(actual)) or not set(actual) <= expected or (complete and set(actual) != expected):
        raise RuntimeError(f'Incomplete or incompatible data for {RESOLUTION[0]}')


def common_limits(datasets):
    time_limit = 0
    speed_limit = 1
    for raw in datasets:
        grouped = {}
        for r in raw:
            grouped.setdefault((r['op'], r['mode'], r['hp'], r['victus']), []).append(r['total'])
        means = {key: statistics.mean(values) for key, values in grouped.items()}
        for (op, mode, h, v), values in grouped.items():
            mean = statistics.mean(values)
            time_limit = max(time_limit, mean + statistics.stdev(values))
            baseline = means[op, 'seq', 1 if coordinator(h, v) == 'HP-Laptop' else 0, 0]
            speed_limit = max(speed_limit, baseline / mean)
    return time_limit * 1100, speed_limit * 1.1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plot-only', action='store_true', help='Regenerate reports from saved measurements.')
    args = parser.parse_args()
    total = len(RESOLUTIONS) * len(jobs()) * REPS
    completed = sum(len(load_selected_runs(path)) for path in
                    [OUTPUT_ROOT / r[0] / 'runs.jsonl' for r in RESOLUTIONS] if path.exists())
    PROGRESS = Progress(total, completed)
    print(f'{len(RESOLUTIONS)} resolutions, {len(OPS)} operations, {total} measured runs; {completed} saved.', flush=True)
    datasets = []
    for RESOLUTION in RESOLUTIONS:
        OUT = OUTPUT_ROOT / RESOLUTION[0]
        if args.plot_only:
            raw = load_selected_runs(OUT / 'runs.jsonl')
        else:
            raw = collect()
        validate_records(raw)
        datasets.append(raw)
    print('Generating reports and figures...', flush=True)
    limits = common_limits(datasets)
    for RESOLUTION, raw in zip(RESOLUTIONS, datasets):
        OUT = OUTPUT_ROOT / RESOLUTION[0]
        figures_and_report(raw, *limits)
