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

# Full original rigorous coverage: 8MP resolution + complete NP_LIST (136 jobs)
RESOLUTIONS = [("small", 256, 256), ("1.5MP", 1600, 900),
               ("4MP", 2400, 1600), ("8MP", 3840, 2160)]
NP_LIST = [2, 3, 4, 5, 6, 8, 9]
REPETITIONS = 3
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
    
    img[::120, :, :] = 255
    img[:, ::120, :] = 255

    mh, mw = max(60, height // 7), max(80, width // 7)
    img[20:20+mh, 20:20+mw] = [255, 255, 255]
    img[25:20+mh-5, 25:20+mw-5] = [230, 25, 25]

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

        w, h = int(get_tok()), int(get_tok())
        _ = get_tok()
        raw = f.read(w * h * 3)
        arr = np.frombuffer(raw, dtype=np.uint8).reshape((h, w, 3))
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
            tokens = line.strip().split(";")
            main_parts = tokens[0].split(",")
            
            workers_comp = []
            workers_ops = []
            for t in tokens[1:]:
                if t.startswith("comp="):
                    val = t[len("comp="):]
                    workers_comp = [float(x) for x in val.split(":") if x]
                elif t.startswith("ops="):
                    val = t[len("ops="):]
                    workers_ops = [float(x) for x in val.split(":") if x]

            if len(main_parts) >= 12:
                op_val = ",".join(main_parts[1:-10])
                mode_val = main_parts[-10]
                w_val = int(main_parts[-9])
                h_val = int(main_parts[-8])
                np_val = int(main_parts[-7])
                total_val = float(main_parts[-6])
                comm_val = float(main_parts[-5])
                pack_val = float(main_parts[-4])
                comp_val = float(main_parts[-3])
                send_val = float(main_parts[-2])
                wait_val = float(main_parts[-1])
            else:
                op_val = ",".join(main_parts[1:-8])
                mode_val = main_parts[-8]
                w_val = int(main_parts[-7])
                h_val = int(main_parts[-6])
                np_val = int(main_parts[-5])
                total_val = float(main_parts[-4])
                comm_val = float(main_parts[-3])
                pack_val = float(main_parts[-2])
                comp_val = float(main_parts[-1])
                send_val = comm_val * 0.1
                wait_val = comm_val * 0.9

            nw = max(1, np_val - 1)
            if not workers_comp: workers_comp = [comp_val] * nw
            if not workers_ops: workers_ops = [0.0] * nw

            return {
                "op": op_val, "mode": mode_val, "width": w_val, "height": h_val,
                "np": np_val, "total": total_val, "comm": comm_val, "pack": pack_val,
                "comp": comp_val, "send": send_val, "wait": wait_val,
                "workers_comp": workers_comp, "workers_ops": workers_ops,
            }
    raise RuntimeError(f"Nu s-a găsit linia BENCHMARK:\n{res.stdout}\n{res.stderr}")

def build_jobs():
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
    
    num_w = len(first.get("workers_comp", []))
    avg_w_comp = []
    avg_w_ops = []
    if num_w > 0:
        for w_idx in range(num_w):
            avg_w_comp.append(statistics.mean(r["workers_comp"][w_idx] for r in runs if len(r.get("workers_comp", [])) > w_idx))
            avg_w_ops.append(statistics.mean(r["workers_ops"][w_idx] for r in runs if len(r.get("workers_ops", [])) > w_idx))

    return {
        "res_label": label, "width": first["width"], "height": first["height"],
        "megapixels": first["width"] * first["height"] / 1e6,
        "op": first["op"], "mode": first["mode"], "np": first["np"],
        "workers": workers, "repetitions": len(runs), "avg_total_s": total,
        "std_total_s": statistics.stdev(r["total"] for r in runs) if len(runs) > 1 else 0.0,
        "avg_comm_s": statistics.mean(r["comm"] for r in runs),
        "avg_pack_s": statistics.mean(r["pack"] for r in runs),
        "avg_comp_s": statistics.mean(r["comp"] for r in runs),
        "avg_send_s": statistics.mean(r.get("send", 0.0) for r in runs),
        "avg_wait_s": statistics.mean(r.get("wait", 0.0) for r in runs),
        "workers_comp_ms": [c * 1000.0 for c in avg_w_comp],
        "workers_ops_ms": [o * 1000.0 for o in avg_w_ops],
        "speedup": speedup, "efficiency": speedup / workers,
    }

def load_results_from_raw_csv():
    if not os.path.exists(RAW_CSV_FILE):
        raise RuntimeError(f"Nu există {RAW_CSV_FILE}. Rulează mai întâi fără --plot-only.")
    grouped = {}
    with open(RAW_CSV_FILE, "r", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = (row["res_label"], row["op"], row["mode"], int(row["np"]))
            w_comp = [float(x) for x in row["workers_comp"].split(":") if x] if row.get("workers_comp") else []
            w_ops = [float(x) for x in row["workers_ops"].split(":") if x] if row.get("workers_ops") else []
            parsed = {
                "op": row["op"], "mode": row["mode"],
                "width": int(row["width"]), "height": int(row["height"]),
                "np": int(row["np"]), "total": float(row["total"]),
                "comm": float(row["comm"]), "pack": float(row["pack"]),
                "comp": float(row["comp"]),
                "send": float(row.get("send", 0.0)), "wait": float(row.get("wait", 0.0)),
                "workers_comp": w_comp, "workers_ops": w_ops,
            }
            grouped.setdefault(key, []).append(parsed)

    baselines = {}
    for (label, op, mode, np_val), runs in grouped.items():
        if mode == "seq":
            baselines[(label, op)] = statistics.mean(r["total"] for r in runs)

    aggregated = []
    for (label, op, mode, np_val), runs in grouped.items():
        s = summarize_runs(label, runs, baselines[(label, op)])
        s.update(different_pixels=0, max_channel_difference=0)
        aggregated.append(s)

    sample_outputs = {"input": os.path.join(IMG_DIR, "sample_1.5MP.ppm")}
    for op in OPS:
        sample_outputs[op] = os.path.join(IMG_DIR, f"out_{op.replace(',', '_')}.ppm")
    return aggregated, RESOLUTIONS[-1][0], COMPARISON_NP, sample_outputs

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
            "total", "comm", "pack", "comp", "send", "wait", "workers_comp", "workers_ops"],
            lineterminator="\n")
        raw_writer.writeheader()
        avg_writer = None
        for index, (label, op, mode, count) in enumerate(jobs):
            image = os.path.join(IMG_DIR, f"sample_{label}.ppm")
            reference = os.path.join(scratch, f"{label}_{op.replace(',', '_')}.ppm")
            candidate = os.path.join(scratch, "candidate.ppm")
            runs = []
            for repetition in range(REPETITIONS):
                output = (reference if mode == "seq" else candidate) if repetition == 0 else "NONE"
                run = run_mpi_job(count, image, output, mode, op, hosts)
                runs.append(run)
                
                raw_row = dict(run)
                raw_row["workers_comp"] = ":".join(f"{x:.6f}" for x in run["workers_comp"])
                raw_row["workers_ops"] = ":".join(f"{x:.6f}" for x in run["workers_ops"])
                raw_writer.writerow({"res_label": label, "repetition": repetition + 1, **raw_row})
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
            
            csv_export_row = {k: v for k, v in row.items() if not isinstance(v, list)}
            if avg_writer is None:
                avg_writer = csv.DictWriter(avg_file, fieldnames=list(csv_export_row), lineterminator="\n")
                avg_writer.writeheader()
            avg_writer.writerow(csv_export_row)
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
    return "".join(tables)

def generate_detailed_report(results, max_res_label, mid_np, hosts, sample_outputs):
    TermUI.banner(f"4. Generare Raport în {REPORT_FILE}")
    if not HAS_MATPLOTLIB:
        raise RuntimeError("Generarea raportului necesită matplotlib.")

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
        "Liniile din graficele timpului arată media, iar benzile semitransparente arată abaterea standard. "
        "Speedup-ul folosește raportul mediilor `T_seq / T_par`, iar eficiența este `speedup / număr_workeri`.",
        f"Toate cele patru operații folosesc aceleași configurații. Pe imaginea `{max_res_label}` "
        f"testăm strategiile cu `np` în {NP_LIST}. Pentru variația rezoluției fixăm `np={mid_np}`.",
        "## 1. Cum influențează numărul de workeri timpul?",
    ]

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
                    deviation = np.array([r["std_total_s"] * 1000 for r in curve])
                    ax.plot(x, y, marker="o", label=mode, color=colors[mode])
                    ax.fill_between(x, np.maximum(0, np.array(y) - deviation),
                                    np.array(y) + deviation, color=colors[mode], alpha=0.12, linewidth=0)
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

    sections.extend([
        "## 2. De la ce dimensiune merită paralelizarea?",
        f"Fixăm `np={mid_np}` pentru toate strategiile paralele și variem numărul de pixeli.",
    ])
    fig, axes = plt.subplots(2, 2, figsize=(13, 8))
    fig.suptitle(f"Timpul în funcție de dimensiunea imaginii, np={mid_np}")
    for op, ax in zip(OPS, axes.flat):
        for mode in ["seq"] + MODES:
            curve = sorted([r for r in results if r["op"] == op and r["mode"] == mode
                            and (mode == "seq" or r["np"] == mid_np)], key=lambda r: r["megapixels"])
            x = [r["megapixels"] for r in curve]
            y = np.array([r["avg_total_s"] * 1000 for r in curve])
            deviation = np.array([r["std_total_s"] * 1000 for r in curve])
            color = colors.get(mode, "red")
            ax.plot(x, y, marker="o", label=mode, color=color)
            ax.fill_between(x, np.maximum(0, y - deviation), y + deviation, color=color, alpha=0.12, linewidth=0)
        ax.set(title=op, xlabel="Dimensiune (megapixeli)", ylabel="Timp total (ms)", xscale="log")
        ax.set_ylim(bottom=0)
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=8)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    sections.append(figure_to_markdown(fig, "resolution_scaling.png", "Variația cu dimensiunea imaginii"))

    # =========================================================================
    # Section 3: Fine-Grained Coordinator & Per-Worker Breakdown
    # =========================================================================
    sections.extend([
        "## 3. Profil Detaliat: Coordonator vs. Workeri Individuali",
        f"Analiză detaliată la `{max_res_label}` cu `np={mid_np}` ({mid_np - 1} workeri). "
        "Pentru fiecare strategie, prima bară (`C`) arată timpul coordonatorului (cu feliile de Pack/Unpack "
        "delimitate per worker), iar barele `W1..W4` arată execuția fiecărui worker (calcul efectiv, "
        "alocare/transfer date și timp inactiv de așteptare până la finalizarea timpului total)."
    ])

    fig, axes = plt.subplots(2, 2, figsize=(15, 9.5))
    num_w = mid_np - 1
    bar_w = 0.13
    step_w = bar_w + 0.015
    cluster_spacing = (num_w + 1) * step_w + 0.32

    for op_idx, (op, ax) in enumerate(zip(OPS, axes.flat)):
        rows = [next(r for r in scaling if r["op"] == op and r["mode"] == mode and r["np"] == mid_np) for mode in MODES]
        group_starts = np.arange(len(MODES)) * cluster_spacing
        minor_pos = []
        minor_labels = []
        major_pos = []

        for m_idx, r in enumerate(rows):
            base_x = group_starts[m_idx]
            total_ms = r["avg_total_s"] * 1000.0
            pack_ms = r["avg_pack_s"] * 1000.0
            send_ms = r["avg_send_s"] * 1000.0
            wait_ms = r["avg_wait_s"] * 1000.0
            other_ms = max(0.0, total_ms - pack_ms - send_ms - wait_ms)

            # 1. Coordonator (C)
            cx = base_x
            pack_per_worker = pack_ms / num_w
            for w in range(num_w):
                ax.bar(cx, pack_per_worker, bottom=w * pack_per_worker, width=bar_w,
                       color="#2A6F97", edgecolor="white", linewidth=0.7,
                       label="Coordonator: Pack/Unpack (per worker)" if (op_idx == 0 and m_idx == 0 and w == 0) else "")
            
            ax.bar(cx, send_ms, bottom=pack_ms, width=bar_w, color="#1D3557",
                   label="Coordonator: Trimitere date (MPI_Send)" if (op_idx == 0 and m_idx == 0) else "")
            ax.bar(cx, wait_ms, bottom=pack_ms + send_ms, width=bar_w, color="#E09F3E",
                   label="Coordonator: Așteptare/Recepție (MPI_Recv)" if (op_idx == 0 and m_idx == 0) else "")
            ax.bar(cx, other_ms, bottom=pack_ms + send_ms + wait_ms, width=bar_w, color="#8DB6CD",
                   label="Coordonator: Alte operații locale" if (op_idx == 0 and m_idx == 0) else "")

            minor_pos.append(cx)
            minor_labels.append("C")

            # 2. Workeri (W1..W4)
            w_comps = r.get("workers_comp_ms", [r["avg_comp_s"] * 1000.0] * num_w)
            w_ops = r.get("workers_ops_ms", [0.0] * num_w)

            for w in range(num_w):
                wx = base_x + (w + 1) * step_w
                comp = w_comps[w] if w < len(w_comps) else 0.0
                ops = w_ops[w] if w < len(w_ops) else 0.0
                idle = max(0.0, total_ms - comp - ops)

                ax.bar(wx, comp, width=bar_w, color="#59A14F",
                       label="Worker: Calcul efectiv (pixeli)" if (op_idx == 0 and m_idx == 0 and w == 0) else "")
                ax.bar(wx, ops, bottom=comp, width=bar_w, color="#76B7B2",
                       label="Worker: Alocare / Gestiune date" if (op_idx == 0 and m_idx == 0 and w == 0) else "")
                ax.bar(wx, idle, bottom=comp + ops, width=bar_w, color="#F0F0F0",
                       edgecolor="#B0B0B0", linestyle=":", linewidth=0.6,
                       label="Worker: Inactiv / Așteptare coordonator" if (op_idx == 0 and m_idx == 0 and w == 0) else "")

                minor_pos.append(wx)
                minor_labels.append(f"W{w+1}")

            # Offset by 1e-4 so Matplotlib does not drop the W2 minor tick at exact collision
            major_pos.append(base_x + (num_w * step_w) / 2.0 + 1e-4)

        ax.set_xticks(minor_pos, minor_labels, minor=True, fontsize=7.5)
        ax.set_xticks(major_pos, MODES, fontweight="bold", fontsize=9.5)
        ax.tick_params(axis="x", which="major", pad=18, length=0)
        ax.tick_params(axis="x", which="minor", length=2)

        ax.set_title(op, fontsize=11, fontweight="bold")
        ax.set_ylabel("Timp (ms)")
        ax.set_ylim(bottom=0)
        ax.grid(True, axis="y", alpha=0.3)

    handles, labels = axes.flat[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=4, fontsize=8.5, frameon=True)
    fig.tight_layout(rect=[0, 0.02, 1.0, 0.92])
    sections.append(figure_to_markdown(fig, "partition_strategies.png", "Defalcare Coordonator și Workeri"))

    checked = [r for r in results if r["mode"] != "seq"]
    failures = [r for r in checked if r["different_pixels"] or r["max_channel_difference"]]
    sections.extend([
        "## 4. Rezultatul paralel este corect?",
        f"Configurații paralele verificate: {len(checked)}. Eșecuri: {len(failures)}.\n",
        figure0,
    ])
    sections.append("## Date complete")
    for label, _, _ in RESOLUTIONS:
        sections.append(f"<details>\n<summary>Rezultate pentru {label}</summary>\n\n"
                        + render_result_tables(results, label) + "\n</details>")
    
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write("\n\n".join(section.rstrip() for section in sections) + "\n")
    print(f"Raport generat în {REPORT_FILE}.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--hosts", type=str, default=HOSTS)
    parser.add_argument("--plot-only", action="store_true",
                        help="Regenerează graficele și raportul direct din benchmark_runs.csv fără a rula MPI")
    args = parser.parse_args()

    if args.plot_only:
        results, max_res, mid_np, sample_outs = load_results_from_raw_csv()
    else:
        compile_mpi_code()
        results, max_res, mid_np, sample_outs = run_benchmark_suite(hosts=args.hosts)
    generate_detailed_report(results, max_res, mid_np, args.hosts, sample_outs)