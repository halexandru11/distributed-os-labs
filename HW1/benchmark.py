#!/usr/bin/env python3
import os
import sys
import time
import csv
import argparse
import subprocess
import statistics
import tempfile
import shutil
import numpy as np

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

HOSTS = None
C_SOURCE = "mpi_image_proc.c"
BINARY   = "./mpi_image_proc"
CSV_FILE = "benchmark_results.csv"
IMG_DIR  = "test_images"
REPORT_FILE = "experimental_study.md"
REPORT_IMG_DIR = "benchmark_figures"
RAW_CSV_FILE = "benchmark_runs.csv"
OPS = ["grayscale", "blur", "rotate90", "grayscale,blur,flip"]
MODES = ["static_1d", "static_2d", "dynamic_1d"]
RESOLUTIONS = [("small", 256, 256), ("1.5MP", 1600, 900),
               ("4MP", 2400, 1600), ("8MP", 3840, 2160)]
NP_LIST = [2, 3, 4, 5, 6, 8, 9]
REPETITIONS = 5
COMPARISON_NP = 5

class TermUI:
    CYAN   = "\033[96m"
    GREEN  = "\033[92m"
    YELLOW = "\033[93m"
    RED    = "\033[91m"
    BOLD   = "\033[1m"
    RESET  = "\033[0m"
    CLEAR  = "\033[2K\r"

    @staticmethod
    def banner(title):
        print(f"\n{TermUI.BOLD}{TermUI.CYAN}{'='*74}{TermUI.RESET}")
        print(f"{TermUI.BOLD}{TermUI.CYAN}  {title}{TermUI.RESET}")
        print(f"{TermUI.BOLD}{TermUI.CYAN}{'='*74}{TermUI.RESET}")

    @staticmethod
    def progress(cur, total, t0, prefix="", stat=""):
        pct = (cur / total) * 100 if total > 0 else 100
        filled = int(24 * cur // max(total, 1))
        bar = "█" * filled + "░" * (24 - filled)
        elapsed = time.time() - t0
        eta = (elapsed / cur) * (total - cur) if cur > 0 else 0
        eta_str = f"{int(eta//60):02d}:{int(eta%60):02d}"
        line = f"{TermUI.CLEAR}{TermUI.BOLD}[{bar}] {pct:5.1f}%{TermUI.RESET} ({cur}/{total}) | ETA: {TermUI.YELLOW}{eta_str}{TermUI.RESET} | {prefix}"
        if stat:
            line += f" | {TermUI.GREEN}{stat}{TermUI.RESET}"
        sys.stdout.write(line[:115])
        sys.stdout.flush()

def compile_mpi_code():
    TermUI.banner("1. Compilare Cod Sursă MPI")
    cmd = ["mpicc", "-O3", "-Wall", C_SOURCE, "-o", BINARY]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"{TermUI.RED}Eroare compilare:\n{res.stderr}{TermUI.RESET}")
        sys.exit(1)
    print(f"{TermUI.GREEN}✔ Compilat cu succes -> {BINARY}{TermUI.RESET}")

def generate_ppm_image(filepath, width, height):
    if os.path.exists(filepath):
        try:
            with open(filepath, "rb") as f:
                h = f.read(64).decode('ascii', errors='ignore').split()
                if len(h) >= 3 and int(h[1]) == width and int(h[2]) == height:
                    return
        except Exception:
            pass
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    y_idx = np.linspace(0, 255, height, dtype=np.uint8)[:, None]
    x_idx = np.linspace(0, 255, width, dtype=np.uint8)[None, :]
    img = np.zeros((height, width, 3), dtype=np.uint8)
    img[:, :, 0] = np.broadcast_to(x_idx, (height, width))
    img[:, :, 1] = np.broadcast_to(y_idx, (height, width))
    img[:, :, 2] = np.broadcast_to(255 - x_idx // 2, (height, width))
    
    # Grilă fină, originală de 1 pixel grosime
    img[::120, :, :] = 255
    img[:, ::120, :] = 255

    # Marcaj roșu stânga-sus (verificare orientare rotație/flip)
    mh, mw = max(60, height // 7), max(80, width // 7)
    img[20:20+mh, 20:20+mw] = [255, 255, 255]
    img[25:20+mh-5, 25:20+mw-5] = [230, 25, 25]

    # Cerc galben central
    cy, cx = height // 2, width // 2
    r_out = min(height, width) // 5
    yy, xx = np.ogrid[:height, :width]
    img[(yy - cy)**2 + (xx - cx)**2 <= r_out**2] = [255, 220, 30]

    with open(filepath, "wb") as f:
        f.write(f"P6\n{width} {height}\n255\n".encode('ascii'))
        f.write(img.tobytes())

def read_ppm_for_plot(filepath, max_dim=700):
    with open(filepath, "rb") as f:
        token = f.read(2)
        if token != b"P6":
            raise ValueError(f"Nu este fișier P6 PPM: {filepath}")
        
        def get_tok():
            tok = b""
            while True:
                ch = f.read(1)
                if not ch: break
                if ch == b"#":
                    while ch and ch != b"\n": ch = f.read(1)
                    continue
                if ch.isspace():
                    if tok: return tok
                else:
                    tok += ch
            return tok

        w, h, _maxval = int(get_tok()), int(get_tok()), int(get_tok())
        raw = f.read(w * h * 3)
        arr = np.frombuffer(raw, dtype=np.uint8).reshape((h, w, 3))
        # Păstrăm o densitate mai mare a eșantionării pentru miniaturi
        step = max(1, max(w, h) // max_dim) if max_dim else 1
        return arr[::step, ::step, :], w, h

def run_mpi_job(np_count, in_img, out_img, mode, pipeline, host_override=None):
    cmd = ["mpirun", "--oversubscribe"]
    if host_override:
        cmd += ["--host", host_override]
    cmd += ["-np", str(np_count), BINARY, in_img, out_img, mode, pipeline]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"Eroare MPI: {' '.join(cmd)}\n{res.stderr}")

    for line in res.stdout.splitlines():
        if line.startswith("BENCHMARK,"):
            parts = line.strip().split(",")
            return {
                "op": ",".join(parts[1:-8]),
                "mode": parts[-8],
                "width": int(parts[-7]),
                "height": int(parts[-6]),
                "np": int(parts[-5]),
                "total": float(parts[-4]),
                "comm": float(parts[-3]),
                "pack": float(parts[-2]),
                "comp": float(parts[-1]),
            }
    raise RuntimeError(f"Nu s-a găsit linia BENCHMARK:\n{res.stdout}\n{res.stderr}")

def build_jobs():
    """Share np=5 runs between the worker-count and image-size experiments."""
    jobs = []
    for label, _, _ in RESOLUTIONS:
        for op in OPS:
            jobs.append((label, op, "seq", 1))
            counts = NP_LIST if label == RESOLUTIONS[-1][0] else [COMPARISON_NP]
            for mode in MODES:
                jobs.extend((label, op, mode, n) for n in counts)
    return jobs


def compare_pixels(reference, candidate):
    expected, w, h = read_ppm_for_plot(reference, max_dim=None)
    actual, aw, ah = read_ppm_for_plot(candidate, max_dim=None)
    if (w, h) != (aw, ah):
        raise RuntimeError(f"Dimensiuni diferite: {w}x{h} vs {aw}x{ah}")
    delta = np.abs(expected.astype(np.int16) - actual.astype(np.int16))
    return int(np.count_nonzero(np.any(delta != 0, axis=2))), int(delta.max())


def summarize_runs(label, runs, baseline):
    first = runs[0]
    total = statistics.mean(r["total"] for r in runs)
    workers = 1 if first["mode"] == "seq" else first["np"] - 1
    speedup = 1.0 if first["mode"] == "seq" else baseline / total
    return {
        "res_label": label, "width": first["width"], "height": first["height"],
        "megapixels": first["width"] * first["height"] / 1e6,
        "op": first["op"], "mode": first["mode"], "np": first["np"],
        "workers": workers, "repetitions": len(runs), "avg_total_s": total,
        "std_total_s": statistics.stdev(r["total"] for r in runs),
        "avg_comm_s": statistics.mean(r["comm"] for r in runs),
        "avg_pack_s": statistics.mean(r["pack"] for r in runs),
        "avg_comp_s": statistics.mean(r["comp"] for r in runs),
        "speedup": speedup, "efficiency": speedup / workers,
    }


def run_benchmark_suite(hosts=None):
    TermUI.banner("2. Pregătire imagini")
    for label, w, h in RESOLUTIONS:
        generate_ppm_image(os.path.join(IMG_DIR, f"sample_{label}.ppm"), w, h)
    jobs = build_jobs()
    total_runs = len(jobs) * REPETITIONS
    TermUI.banner(f"3. Măsurători: {len(jobs)} configurații × {REPETITIONS} repetări")
    aggregated, baselines = [], {}
    sample_outputs = {"input": os.path.join(IMG_DIR, "sample_1.5MP.ppm")}
    started = time.time()
    with tempfile.TemporaryDirectory(prefix="mpi-check-") as scratch, \
            open(RAW_CSV_FILE, "w", newline="") as raw_file, \
            open(CSV_FILE, "w", newline="") as avg_file:
        raw_writer = csv.DictWriter(raw_file, fieldnames=[
            "res_label", "repetition", "op", "mode", "width", "height", "np",
            "total", "comm", "pack", "comp"], lineterminator="\n")
        raw_writer.writeheader()
        avg_writer = None
        for index, (label, op, mode, count) in enumerate(jobs):
            image = os.path.join(IMG_DIR, f"sample_{label}.ppm")
            reference = os.path.join(scratch, f"{label}_{op.replace(',', '_')}.ppm")
            candidate = os.path.join(scratch, "candidate.ppm")
            runs = []
            for repetition in range(REPETITIONS):
                # Check the first run of every configuration outside timed intervals.
                output = (reference if mode == "seq" else candidate) if repetition == 0 else "NONE"
                run = run_mpi_job(count, image, output, mode, op, hosts)
                runs.append(run)
                raw_writer.writerow({"res_label": label, "repetition": repetition + 1, **run})
                raw_file.flush()
                if repetition == 0:
                    different, maximum = (0, 0) if mode == "seq" else compare_pixels(reference, candidate)
                    if label == "1.5MP" and mode == "seq":
                        demo = os.path.join(IMG_DIR, f"out_{op.replace(',', '_')}.ppm")
                        shutil.copyfile(reference, demo)
                        sample_outputs[op] = demo
                TermUI.progress(index * REPETITIONS + repetition + 1, total_runs, started,
                                prefix=f"{label}|{op}|{mode}|np={count}")
            key = (label, op)
            if mode == "seq":
                baselines[key] = statistics.mean(r["total"] for r in runs)
            row = summarize_runs(label, runs, baselines[key])
            row.update(different_pixels=different, max_channel_difference=maximum)
            aggregated.append(row)
            if avg_writer is None:
                avg_writer = csv.DictWriter(avg_file, fieldnames=list(row), lineterminator="\n")
                avg_writer.writeheader()
            avg_writer.writerow(row)
            avg_file.flush()
    print(f"\nFinalizat în {time.time() - started:.1f}s. Măsurători brute în {RAW_CSV_FILE}.")
    return aggregated, RESOLUTIONS[-1][0], COMPARISON_NP, sample_outputs


def figure_to_markdown(fig, filename, alt_text):
    os.makedirs(REPORT_IMG_DIR, exist_ok=True)
    path = os.path.join(REPORT_IMG_DIR, filename)
    fig.savefig(path, format="png", dpi=140, bbox_inches="tight")
    plt.close(fig)
    link = os.path.relpath(path, os.path.dirname(REPORT_FILE) or ".")
    return f"![{alt_text}]({link})\n"

def render_result_tables(results, res_label):
    tables = [
        f"### Rezultate măsurate pentru rezoluția `{res_label}`\n\n",
        "Timpii sunt exprimați în milisecunde. `np` include coordonatorul; "
        "modurile paralele folosesc `np - 1` workeri. "
        "Total arată media ± abaterea standard. Cel mai mic timp mediu din fiecare tabel este marcat cu bold.\n\n",
    ]
    for op in OPS:
        rows = [r for r in results if r["res_label"] == res_label and r["op"] == op]
        if not rows:
            continue
        best_total = min(r["avg_total_s"] for r in rows)
        tables.extend([
            f"#### {op}\n\n",
            "| Mod | np | Total (ms) | Calcul (ms) | Pack (ms) | MPI (ms) | Speedup |\n",
            "| :--- | ---: | ---: | ---: | ---: | ---: | ---: |\n",
        ])
        for r in rows:
            total = f"{r['avg_total_s'] * 1000:.1f} ± {r['std_total_s'] * 1000:.1f}"
            if r["avg_total_s"] == best_total:
                total = f"**{total}**"
            tables.append(
                f"| {r['mode']} | {r['np']} | {total} | "
                f"{r['avg_comp_s'] * 1000:.1f} | {r['avg_pack_s'] * 1000:.1f} | "
                f"{r['avg_comm_s'] * 1000:.1f} | {r['speedup']:.2f}x |\n"
            )
        tables.append("\n")
    tables.append(
        "Calcul reprezintă timpul cumulat maxim de procesare pe un proces. "
        "Pack include împachetarea, despachetarea și alocarea bufferelor temporare. "
        "MPI include timpul petrecut de coordonator în apelurile MPI, inclusiv "
        "așteptarea workerilor. Aceste intervale se suprapun și nu se adună "
        "pentru a obține timpul total.\n"
    )
    return "".join(tables)


def generate_detailed_report(results, max_res_label, mid_np, hosts, sample_outputs):
    TermUI.banner(f"4. Generare Raport în {REPORT_FILE}")
    if not HAS_MATPLOTLIB:
        raise RuntimeError("Generarea raportului necesită matplotlib.")

    # Figura 0: Verificare Vizuală cu interpolare bilineară activată
    fig0, axes0 = plt.subplots(2, 3, figsize=(14, 8))
    fig0.suptitle("Imagine inițială și rezultate secvențiale de referință", fontsize=13, fontweight="bold")
    vis = [
        ("input", "1. Imagine Inițială"),
        ("grayscale", "2. Grayscale (In-Place)"),
        ("blur", "3. Box Blur 9x9"),
        ("rotate90", "4. Rotate 90° CW"),
        ("grayscale,blur,flip", "5. Pipeline (Gray->Blur->Flip)")
    ]
    for idx, (k, title) in enumerate(vis):
        ax = axes0[idx // 3][idx % 3]
        arr, w, h = read_ppm_for_plot(sample_outputs[k])
        ax.imshow(arr, interpolation="bilinear")
        ax.set_title(f"{title}\n({w}x{h} px)", fontsize=9, fontweight="bold")
        ax.axis("off")

    ax_z = axes0[1][2]
    arr_in, _, _ = read_ppm_for_plot(sample_outputs["input"], max_dim=800)
    arr_bl, _, _ = read_ppm_for_plot(sample_outputs["blur"], max_dim=800)
    ch, cw = min(120, arr_in.shape[0]), min(120, arr_in.shape[1])
    zoom = np.concatenate([arr_in[:ch, :cw], np.full((ch, 6, 3), 255, dtype=np.uint8), arr_bl[:ch, :cw]], axis=1)
    ax_z.imshow(zoom, interpolation="bilinear")
    ax_z.set_title("6. Zoom Detaliu (Stânga: Input | Dreapta: Blur)", fontsize=9, fontweight="bold")
    ax_z.axis("off")
    fig0.tight_layout(rect=[0, 0.03, 1, 0.94])
    figure0 = figure_to_markdown(fig0, "visual_check.png", "Verificarea vizuală a operațiilor")

    sections = [
        "# Studiul experimental al prelucrării paralele de imagini în MPI",
        "## Metodologie",
        f"Mediu: `{hosts or 'local'}`. Fiecare configurație rulează de {REPETITIONS} ori. "
        "Graficele timpului arată media și abaterea standard între rulări. "
        "Speedup-ul folosește raportul mediilor `T_seq / T_par`, iar eficiența "
        "este `speedup / număr_workeri`. Coordonatorul nu procesează pixeli în modurile paralele. "
        "Aceste valori descriu rularea curentă și pot varia cu încărcarea sistemului.",
        f"Toate cele patru operații folosesc aceleași configurații. Pe imaginea `{max_res_label}` "
        f"testăm cele trei strategii cu `np` în {NP_LIST}. Pentru variația rezoluției fixăm "
        f"`np={mid_np}` și folosim imaginile "
        + ", ".join(f"`{label}`: {w}×{h}" for label, w, h in RESOLUTIONS) + ". "
        "Configurațiile comune celor două experimente sunt măsurate o singură dată.",
        "Timpul total exclude citirea și scrierea imaginilor, pornirea MPI, oprirea workerilor "
        "și reducerea finală a timpilor. Prima repetare produce și o imagine pentru verificare; "
        "scrierea și compararea pixelilor au loc în afara intervalelor măsurate. "
        "Măsurătorile brute sunt în [benchmark_runs.csv](benchmark_runs.csv), "
        "iar mediile și verificările în [benchmark_results.csv](benchmark_results.csv).",
        "## 1. Cum influențează numărul de workeri timpul?",
        f"Rezoluția este fixată la `{max_res_label}`. Fiecare curbă reprezintă o strategie; "
        "linia întreruptă arată referința secvențială. Speedup peste 1 indică un timp mediu "
        "mai mic decât cel secvențial. Eficiența de 100% este reperul ideal per worker.",
    ]
    grid_labels = []
    for count in NP_LIST:
        workers = count - 1
        cols = max(i for i in range(1, int(workers ** 0.5) + 1) if workers % i == 0)
        grid_labels.append(f"`np={count}` → {workers // cols}×{cols}")
    sections.append("Grilele `static_2d`, rânduri × coloane: " + "; ".join(grid_labels) +
                    ". O singură coloană înseamnă felii pe întreaga lățime a rezultatului.")

    colors = dict(zip(MODES, ["#1f77b4", "#e68613", "#2ca02c"]))
    scaling = [r for r in results if r["res_label"] == max_res_label]
    for metric, filename, title, ylabel in [
        ("avg_total_s", "execution_time.png", "Timp total", "Timp total (ms)"),
        ("speedup", "speedup.png", "Speedup", "Speedup (×)"),
        ("efficiency", "efficiency.png", "Eficiență", "Eficiență (%)"),
    ]:
        fig, axes = plt.subplots(2, 2, figsize=(13, 8))
        fig.suptitle(f"{title}, rezoluție {max_res_label}")
        for op, ax in zip(OPS, axes.flat):
            rows = [r for r in scaling if r["op"] == op]
            seq = next(r for r in rows if r["mode"] == "seq")
            for mode in MODES:
                curve = sorted([r for r in rows if r["mode"] == mode], key=lambda r: r["np"])
                x = [r["workers"] for r in curve]
                multiplier = 1000 if metric == "avg_total_s" else 100 if metric == "efficiency" else 1
                y = [r[metric] * multiplier for r in curve]
                if metric == "avg_total_s":
                    ax.errorbar(x, y, yerr=[r["std_total_s"] * 1000 for r in curve],
                                marker="o", capsize=3, label=mode, color=colors[mode])
                else:
                    ax.plot(x, y, marker="o", label=mode, color=colors[mode])
            if metric == "avg_total_s":
                ax.axhline(seq[metric] * 1000, linestyle="--", color="red", label="seq")
                ax.axhspan(max(0, seq[metric] - seq["std_total_s"]) * 1000,
                           (seq[metric] + seq["std_total_s"]) * 1000, color="red", alpha=0.08)
            else:
                ax.axhline(1 if metric == "speedup" else 100, linestyle="--", color="gray")
                if metric == "speedup":
                    x = [n - 1 for n in NP_LIST]
                    ax.plot(x, x, linestyle=":", color="gray", label="Ideal per worker")
            ax.set(title=op, xlabel="Număr de workeri", ylabel=ylabel)
            ax.set_xticks([n - 1 for n in NP_LIST])
            ax.set_ylim(bottom=0)
            ax.grid(True, alpha=0.3)
            ax.legend(fontsize=8)
        fig.tight_layout(rect=[0, 0, 1, 0.95])
        sections.append(figure_to_markdown(fig, filename, title))
    for op in OPS:
        rows = [r for r in scaling if r["op"] == op]
        best = min(rows, key=lambda r: r["avg_total_s"])
        sections.append(
            f"Pentru `{op}`, cel mai mic timp mediu măsurat este {best['avg_total_s'] * 1000:.1f} ms "
            f"cu `{best['mode']}`, `np={best['np']}`. "
            f"Speedup-ul acestei configurații este {best['speedup']:.2f}×."
        )
    sections.extend([
        "## 2. De la ce dimensiune merită paralelizarea?",
        f"Fixăm `np={mid_np}` pentru toate strategiile paralele și variem numărul de pixeli. "
        "Axa dimensiunii este logaritmică. Pragurile de mai jos sunt cele mai mici dimensiuni "
        "testate cu speedup peste 1, nu praguri exacte sau garanții pentru toate imaginile mai mari.",
    ])
    fig, axes = plt.subplots(2, 2, figsize=(13, 8))
    fig.suptitle(f"Timpul în funcție de dimensiunea imaginii, np={mid_np}")
    for op, ax in zip(OPS, axes.flat):
        for mode in ["seq"] + MODES:
            curve = sorted([r for r in results if r["op"] == op and r["mode"] == mode
                            and (mode == "seq" or r["np"] == mid_np)], key=lambda r: r["megapixels"])
            ax.errorbar([r["megapixels"] for r in curve], [r["avg_total_s"] * 1000 for r in curve],
                        yerr=[r["std_total_s"] * 1000 for r in curve], marker="o", capsize=3,
                        label=mode, color=colors.get(mode, "red"))
            if mode != "seq":
                wins = [r for r in curve if r["speedup"] > 1]
                finding = (f"primul câștig la `{wins[0]['res_label']}`, {wins[0]['speedup']:.2f}×"
                           if wins else "niciun câștig la dimensiunile testate")
                sections.append(f"- `{op}`, `{mode}`: {finding}.")
        ax.set(title=op, xlabel="Dimensiune (megapixeli)", ylabel="Timp total (ms)", xscale="log")
        ax.set_ylim(bottom=0)
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=8)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    # Keep list entries together with normal Markdown list spacing.
    sections.append(figure_to_markdown(fig, "resolution_scaling.png", "Variația cu dimensiunea imaginii"))

    sections.extend([
        "## 3. Cum se compară timpii coordonatorului și workerilor?",
        f"Comparăm toate operațiile la `{max_res_label}` și `np={mid_np}`. "
        "Fiecare strategie are două coloane, C pentru coordonator și W pentru worker. "
        "Coloana C împarte timpul total în pack/unpack, alte operații locale și "
        "comunicație și așteptare MPI. Pack/unpack include alocările bufferelor temporare. "
        "Alte operații locale reprezintă restul calculat ca `total - MPI - pack/unpack`; "
        "include pregătirea și planificarea taskurilor, administrarea memoriei din afara "
        "pack/unpack și costul instrumentării. Transmiterea și colectarea prin apeluri MPI "
        "intră în segmentul de comunicație și așteptare MPI, care nu reprezintă exclusiv "
        "timp inactiv. Coloana W arată media maximului "
        "timpului cumulat de calcul pe un worker, pentru fiecare rulare. "
        "Nu este suma timpilor tuturor workerilor și nu include așteptarea sau transferurile lor. "
        "Coloanele C și W se suprapun în timp și nu se adună. "
        "Împărțirea arată cât timp ocupă munca locală, dar nu dovedește singură "
        "că mutarea pack/unpack ar reduce timpul total.",
    ])
    fig, axes = plt.subplots(2, 2, figsize=(14, 9))
    for op, ax in zip(OPS, axes.flat):
        rows = [next(r for r in scaling if r["op"] == op and r["mode"] == mode
                     and r["np"] == mid_np) for mode in MODES]
        x = np.arange(len(MODES))
        packing = np.array([r["avg_pack_s"] * 1000 for r in rows])
        other = np.array([max(0.0, r["avg_total_s"] - r["avg_comm_s"] - r["avg_pack_s"]) * 1000
                          for r in rows])
        waiting = [r["avg_comm_s"] * 1000 for r in rows]
        width = 0.34
        ax.bar(x - width / 2, packing, width=width,
               label="Coordonator: pack/unpack", color="#2A6F97")
        ax.bar(x - width / 2, other, bottom=packing, width=width,
               label="Coordonator: alte operații locale", color="#8DB6CD")
        ax.bar(x - width / 2, waiting, bottom=packing + other, width=width,
               label="Coordonator: comunicație și așteptare MPI", color="#E09F3E")
        ax.bar(x + width / 2, [r["avg_comp_s"] * 1000 for r in rows], width=width,
               label="Worker: calcul maxim", color="#59A14F")
        ax.set_xticks([position + offset for position in x for offset in [-width / 2, width / 2]],
                      ["C", "W"] * len(MODES), minor=True)
        ax.tick_params(axis="x", which="major", pad=22, length=0)
        ax.tick_params(axis="x", which="minor", length=0)
        ax.set_xticks(x, MODES)
        ax.set(title=op, ylabel="Timp (ms)")
        ax.grid(True, axis="y", alpha=0.3)
        best = min(rows, key=lambda r: r["avg_total_s"])
        sections.append(f"Pentru `{op}`, la `np={mid_np}`, strategia cu timpul mediu minim "
                        f"este `{best['mode']}`, {best['avg_total_s'] * 1000:.1f} ms.")
    handles, labels = axes.flat[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=2, fontsize=9)
    fig.tight_layout(rect=[0, 0, 1, 0.93])
    sections.append(figure_to_markdown(fig, "partition_strategies.png", "Timpii coordonatorului și timpul de calcul al workerului"))

    checked = [r for r in results if r["mode"] != "seq"]
    failures = [r for r in checked if r["different_pixels"] or r["max_channel_difference"]]
    sections.extend([
        "## 4. Rezultatul paralel este corect?",
        f"Am comparat toți pixelii primei repetări din fiecare dintre cele {len(checked)} "
        f"configurații paralele cu rezultatul secvențial pentru aceeași imagine și operație. "
        f"Configurații cu diferențe: {len(failures)}. "
        f"Numărul maxim de pixeli diferiți este {max(r['different_pixels'] for r in checked)}, "
        f"iar diferența maximă pe canal este {max(r['max_channel_difference'] for r in checked)}. "
        "Verificarea include dimensiunile rezultatului; o nepotrivire de dimensiuni oprește suita.",
        figure0,
    ])
    if failures:
        sections.append("| Rezoluție | Operație | Mod | np | Pixeli diferiți | Diferență maximă |\n"
                        "| :--- | :--- | :--- | ---: | ---: | ---: |\n" + "".join(
                            f"| {r['res_label']} | {r['op']} | {r['mode']} | {r['np']} | "
                            f"{r['different_pixels']} | {r['max_channel_difference']} |\n" for r in failures))
    sections.append("## Date complete")
    for label, _, _ in RESOLUTIONS:
        sections.append(f"<details>\n<summary>Rezultate pentru {label}</summary>\n\n"
                        + render_result_tables(results, label) + "\n</details>")
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write("\n\n".join(section.rstrip() for section in sections) + "\n")
    print(f"Raport generat în {REPORT_FILE}.")
    if failures:
        raise RuntimeError(f"{len(failures)} configurații au rezultate diferite de referință. Vezi raportul.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--hosts", type=str, default=HOSTS)
    args = parser.parse_args()

    compile_mpi_code()
    results, max_res, mid_np, sample_outs = run_benchmark_suite(hosts=args.hosts)
    generate_detailed_report(results, max_res, mid_np, args.hosts, sample_outs)
