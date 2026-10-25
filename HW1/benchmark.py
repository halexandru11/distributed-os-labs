#!/usr/bin/env python3
import os
import sys
import time
import csv
import argparse
import subprocess
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
        step = max(1, max(w, h) // max_dim)
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

def run_benchmark_suite(hosts=None):
    resolutions = [
        ("1.5MP", 1600, 900),
        ("4MP",   2400, 1600),
        ("8MP",   3840, 2160),
    ]
    np_list = [1, 2, 3, 4, 5, 6, 8]
    reps = 3

    TermUI.banner("2. Pregătire Imagini de Test")
    for label, w, h in resolutions:
        p = os.path.join(IMG_DIR, f"sample_{label}.ppm")
        print(f"  Imagine {label} ({w}x{h} px, {(w*h*3)/(1024*1024):.1f} MB) -> {p}")
        generate_ppm_image(p, w, h)

    sample_in = os.path.join(IMG_DIR, f"sample_{resolutions[0][0]}.ppm")
    sample_ops = ["grayscale", "blur", "rotate90", "grayscale,blur,flip"]
    sample_outputs = {"input": sample_in}
    for op in sample_ops:
        out_name = os.path.join(IMG_DIR, f"out_{op.replace(',', '_')}.ppm")
        run_mpi_job(3, sample_in, out_name, "static_1d", op, hosts)
        sample_outputs[op] = out_name
    print(f"{TermUI.GREEN}✔ Imagini demonstrative generate.{TermUI.RESET}")

    max_label, max_w, max_h = resolutions[-1]
    max_img = os.path.join(IMG_DIR, f"sample_{max_label}.ppm")
    # Four workers form a 2x2 grid in static_2d.
    mid_np = 5

    jobs = []
    for op in ["grayscale", "blur", "rotate90", "grayscale,blur,flip"]:
        jobs.append((max_label, max_img, op, "seq", 1))
        for np_val in [n for n in np_list if n > 1]:
            jobs.append((max_label, max_img, op, "static_1d", np_val))

    for op in ["blur", "grayscale,blur,flip"]:
        for m in ["static_2d", "dynamic_1d"]:
            jobs.append((max_label, max_img, op, m, mid_np))

    for label, w, h in resolutions[:-1]:
        p = os.path.join(IMG_DIR, f"sample_{label}.ppm")
        for op in ["grayscale", "blur", "grayscale,blur,flip"]:
            jobs.append((label, p, op, "seq", 1))
            jobs.append((label, p, op, "static_1d", mid_np))

    total_runs = len(jobs) * reps
    TermUI.banner(f"3. Rulare Măsurători ({len(jobs)} config x {reps} rep = {total_runs} rulări)")

    aggregated = []
    seq_map = {}
    t0 = time.time()
    cur = 0
    last_str = ""

    with open(CSV_FILE, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["res_label", "width", "height", "megapixels", "op", "mode", "np", "workers",
                         "avg_total_s", "avg_comm_s", "avg_pack_s", "avg_comp_s", "speedup", "efficiency"])

        for (res_label, img_path, op, mode, np_val) in jobs:
            t_tot, t_comm, t_pack, t_comp = [], [], [], []
            w_px, h_px = 0, 0
            for r in range(reps):
                TermUI.progress(cur, total_runs, t0, prefix=f"{res_label}|{op[:8]}|{mode[:7]}|np={np_val}", stat=last_str)
                res = run_mpi_job(np_val, img_path, "NONE", mode, op, hosts)
                t_tot.append(res["total"])
                t_comm.append(res["comm"])
                t_pack.append(res["pack"])
                t_comp.append(res["comp"])
                w_px, h_px = res["width"], res["height"]
                cur += 1

            avg_tot = sum(t_tot) / len(t_tot)
            # Coordinator MPI calls include waits and overlap worker computation.
            avg_comm = sum(t_comm) / len(t_comm)
            avg_pack = sum(t_pack) / len(t_pack)
            avg_comp = sum(t_comp) / len(t_comp)
            mp = round((w_px * h_px) / 1e6, 2)
            workers = 1 if mode == "seq" else (np_val - 1)

            if mode == "seq":
                seq_map[(res_label, op)] = avg_tot
                avg_comm = 0.0
                avg_pack = 0.0
                speedup, eff = 1.0, 1.0
            else:
                base = seq_map.get((res_label, op), avg_tot)
                speedup = base / avg_tot if avg_tot > 0 else 1.0
                eff = speedup / workers if workers > 0 else 0.0

            last_str = f"{avg_tot:.3f}s (pack={avg_pack:.4f}s, {speedup:.2f}x)"
            TermUI.progress(cur, total_runs, t0, prefix="Finalizat", stat=last_str)

            row = {
                "res_label": res_label, "width": w_px, "height": h_px, "megapixels": mp,
                "op": op, "mode": mode, "np": np_val, "workers": workers,
                "avg_total_s": avg_tot, "avg_comm_s": avg_comm, "avg_pack_s": avg_pack,
                "avg_comp_s": avg_comp, "speedup": speedup, "efficiency": eff
            }
            aggregated.append(row)
            writer.writerow([res_label, w_px, h_px, mp, op, mode, np_val, workers,
                             f"{avg_tot:.5f}", f"{avg_comm:.5f}", f"{avg_pack:.5f}", f"{avg_comp:.5f}",
                             f"{speedup:.3f}", f"{eff:.3f}"])
            f.flush()

    print(f"\n\n{TermUI.GREEN}✔ Finalizat în {time.time()-t0:.1f}s! Salvat -> {CSV_FILE}{TermUI.RESET}")
    return aggregated, max_label, mid_np, sample_outputs

def figure_to_markdown(fig, filename, alt_text):
    os.makedirs(REPORT_IMG_DIR, exist_ok=True)
    path = os.path.join(REPORT_IMG_DIR, filename)
    fig.savefig(path, format="png", dpi=140, bbox_inches="tight")
    plt.close(fig)
    return f"![{alt_text}]({path})\n"

def generate_detailed_report(results, max_res_label, mid_np, hosts, sample_outputs):
    TermUI.banner(f"4. Generare Raport în {REPORT_FILE}")
    if not HAS_MATPLOTLIB:
        print(f"{TermUI.RED}matplotlib necesar. pip install matplotlib{TermUI.RESET}")
        return

    ops = ["grayscale", "blur", "rotate90", "grayscale,blur,flip"]
    op_titles = {
        "grayscale": "Cat 1: Grayscale (In-Place)",
        "blur": "Cat 2: Box Blur 9x9 (Neighborhood)",
        "rotate90": "Cat 3: Rotate 90° CW (Move/Dimensions)",
        "grayscale,blur,flip": "Full Pipeline (Gray -> Blur -> Flip)"
    }

    # Figura 0: Verificare Vizuală cu interpolare bilineară activată
    fig0, axes0 = plt.subplots(2, 3, figsize=(14, 8))
    fig0.suptitle("Verificare Vizuală: Imagine Inițială vs. Rezultate Procesate MPI", fontsize=13, fontweight="bold")
    vis = [
        ("input", "1. Imagine Inițială"),
        ("grayscale", "2. Grayscale (In-Place)"),
        ("blur", "3. Box Blur 9x9 (Fără cusături)"),
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

    # Figura 1: Timp vs Procese
    fig1, axes1 = plt.subplots(2, 2, figsize=(13, 8))
    fig1.suptitle(f"Timpul de Execuție vs. Numărul de Procese MPI (Imagine {max_res_label})", fontsize=13, fontweight="bold")
    for idx, op in enumerate(ops):
        ax = axes1[idx // 2][idx % 2]
        sub = [r for r in results if r["res_label"] == max_res_label and r["op"] == op]
        seq = next((r for r in sub if r["mode"] == "seq"), None)
        par = sorted([r for r in sub if r["mode"] == "static_1d"], key=lambda x: x["np"])
        if seq:
            ax.axhline(seq["avg_total_s"], color="red", linestyle="--", label="Secvențial (1 proc)")
        if par:
            ax.plot([p["np"] for p in par], [p["avg_total_s"] for p in par], marker="o", linewidth=2, color="#1f77b4", label="Paralel (static_1d)")
        ax.set_title(op_titles[op], fontweight="bold", fontsize=10)
        ax.set_xlabel("Număr Procese MPI (np)")
        ax.set_ylabel("Timp Total (secunde)")
        ax.grid(True, linestyle=":", alpha=0.6)
        ax.legend(fontsize=8)
    fig1.tight_layout(rect=[0, 0.03, 1, 0.94])
    figure1 = figure_to_markdown(fig1, "execution_time.png", "Timpul de execuție în funcție de numărul de procese")

    # Figura 2: Speedup
    fig2, axes2 = plt.subplots(2, 2, figsize=(13, 8))
    fig2.suptitle(f"Speedup Paralel (T_seq / T_par) vs. Număr Procese Worker ({max_res_label})", fontsize=13, fontweight="bold")
    for idx, op in enumerate(ops):
        ax = axes2[idx // 2][idx % 2]
        sub = [r for r in results if r["res_label"] == max_res_label and r["op"] == op]
        par = sorted([r for r in sub if r["mode"] == "static_1d"], key=lambda x: x["workers"])
        if par:
            workers_list = [p["workers"] for p in par]
            ax.plot(workers_list, [p["speedup"] for p in par], marker="s", linewidth=2, color="#2ca02c", label="Speedup Real")
            ax.plot(workers_list, workers_list, linestyle=":", color="gray", label="Speedup Ideal Liniar")
        ax.axhline(1.0, color="red", linestyle="--", label="Prag Secvențial (1.0x)")
        ax.set_title(op_titles[op], fontweight="bold", fontsize=10)
        ax.set_xlabel("Număr Procese Worker (np - 1)")
        ax.set_ylabel("Speedup (x)")
        ax.grid(True, linestyle=":", alpha=0.6)
        ax.legend(fontsize=8)
    fig2.tight_layout(rect=[0, 0.03, 1, 0.94])
    figure2 = figure_to_markdown(fig2, "speedup.png", "Speedup în funcție de numărul de workeri")

    # Figura 3: Scalabilitate cu Rezoluția
    fig3, axes3 = plt.subplots(1, 3, figsize=(14, 4.5))
    fig3.suptitle(f"Scalabilitate cu Rezoluția Imaginii (Secvențial vs. Paralel np={mid_np})", fontsize=13, fontweight="bold")
    for idx, op in enumerate(["grayscale", "blur", "grayscale,blur,flip"]):
        ax = axes3[idx]
        sub_seq = sorted([r for r in results if r["op"] == op and r["mode"] == "seq"], key=lambda x: x["megapixels"])
        sub_par = sorted([r for r in results if r["op"] == op and r["mode"] == "static_1d" and r["np"] == mid_np], key=lambda x: x["megapixels"])
        if sub_seq:
            ax.plot([r["megapixels"] for r in sub_seq], [r["avg_total_s"] for r in sub_seq], marker="o", linestyle="--", color="red", label="Secvențial")
        if sub_par:
            ax.plot([r["megapixels"] for r in sub_par], [r["avg_total_s"] for r in sub_par], marker="s", color="#1f77b4", label=f"Paralel (np={mid_np})")
        ax.set_title(op_titles[op], fontweight="bold", fontsize=10)
        ax.set_xlabel("Rezoluție (Megapixeli)")
        ax.set_ylabel("Timp (s)")
        ax.grid(True, linestyle=":", alpha=0.6)
        ax.legend(fontsize=8)
    fig3.tight_layout(rect=[0, 0.03, 1, 0.92])
    figure3 = figure_to_markdown(fig3, "resolution_scaling.png", "Scalabilitatea cu rezoluția imaginii")

    # Figura 4: Împărțire Slicing (cu Pack/Unpack evidențiat separat)
    fig4, (ax4a, ax4b) = plt.subplots(1, 2, figsize=(13, 5))
    fig4.suptitle(f"Analiza Strategiilor de Divizare și Load-Balancing (np={mid_np}, {max_res_label})", fontsize=13, fontweight="bold")
    
    modes_test = ["static_1d", "static_2d", "dynamic_1d"]
    comp_blur, pack_blur, comm_blur = [], [], []
    for m in modes_test:
        r = next((x for x in results if x["res_label"] == max_res_label and x["op"] == "blur" and x["mode"] == m and x["np"] == mid_np), None)
        comp_blur.append(r["avg_comp_s"] if r else 0)
        pack_blur.append(r["avg_pack_s"] if r else 0)
        comm_blur.append(r["avg_comm_s"] if r else 0)

    positions = np.arange(len(modes_test))
    bar_width = 0.25
    ax4a.bar(positions - bar_width, comp_blur, width=bar_width, label="Calcul CPU maxim pe worker", color="#2A6F97")
    ax4a.bar(positions, pack_blur, width=bar_width, label="Pack / Unpack cu alocare", color="#E09F3E")
    ax4a.bar(positions + bar_width, comm_blur, width=bar_width, label="Apeluri MPI cu așteptare", color="#9E2A2B")
    ax4a.set_xticks(range(len(modes_test)))
    ax4a.set_xticklabels(modes_test)
    ax4a.set_title("Box Blur (Calcul Intensiv per Pixel)", fontweight="bold", fontsize=10)
    ax4a.set_ylabel("Timp (secunde)")
    ax4a.grid(True, axis="y", linestyle=":", alpha=0.6)
    ax4a.legend(fontsize=8)

    comp_pipe, pack_pipe, comm_pipe = [], [], []
    for m in modes_test:
        r = next((x for x in results if x["res_label"] == max_res_label and x["op"] == "grayscale,blur,flip" and x["mode"] == m and x["np"] == mid_np), None)
        comp_pipe.append(r["avg_comp_s"] if r else 0)
        pack_pipe.append(r["avg_pack_s"] if r else 0)
        comm_pipe.append(r["avg_comm_s"] if r else 0)

    positions = np.arange(len(modes_test))
    bar_width = 0.25
    ax4b.bar(positions - bar_width, comp_pipe, width=bar_width, label="Calcul CPU maxim pe worker", color="#2A6F97")
    ax4b.bar(positions, pack_pipe, width=bar_width, label="Pack / Unpack cu alocare", color="#E09F3E")
    ax4b.bar(positions + bar_width, comm_pipe, width=bar_width, label="Apeluri MPI cu așteptare", color="#9E2A2B")
    ax4b.set_xticks(range(len(modes_test)))
    ax4b.set_xticklabels(modes_test)
    ax4b.set_title("Full Pipeline (Înlănțuire Filtre Grafice)", fontweight="bold", fontsize=10)
    ax4b.set_ylabel("Timp (secunde)")
    ax4b.grid(True, axis="y", linestyle=":", alpha=0.6)
    ax4b.legend(fontsize=8)

    fig4.tight_layout(rect=[0, 0.03, 1, 0.92])
    figure4 = figure_to_markdown(fig4, "partition_strategies.png", "Comparația strategiilor de divizare")

    tbl = [
        f"### Tabel Sintetic al Rezultatelor Măsurate (Rezoluție: `{max_res_label}`)\n\n",
        "| Operație | Mod Paralelizare | Procese (`np`) | Workers | Timp Total (s) | Calcul CPU (s) | Pack/Unpack (s) | Apeluri MPI cu așteptare (s) | Speedup ($S_p$) |\n",
        "| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |\n"
    ]
    for r in results:
        if r["res_label"] == max_res_label:
            tbl.append(
                f"| `{r['op']}` | `{r['mode']}` | {r['np']} | {r['workers']} | "
                f"**{r['avg_total_s']:.4f}s** | {r['avg_comp_s']:.4f}s | "
                f"{r['avg_pack_s']:.4f}s | {r['avg_comm_s']:.4f}s | **{r['speedup']:.2f}x** |\n"
            )

    cluster_str = f"Cluster Multi-Node (`{hosts}`)" if hosts else "Single Machine (Local Multi-Core)"
    sections = [
        (
            "# Studiul Experimental al Prelucrării Paralele de Imagini în MPI\n\n"
            f"**Mediu de execuție:** {cluster_str} | **Rezoluție principală:** `{max_res_label}` (~25 MB per imagine necomprimată)\n\n"
            "Acest studiu evaluează performanța implementării paralele bazate pe șablonul **Coordonator-Workers** în MPI pentru procesarea matricilor de pixeli RGB (format necomprimat **PPM `P6`**)."
        ),
        (
            "## 0. Verificarea Vizuală a Corectitudinii Operațiilor Grafice\n"
            "Imaginea generată conține un marcaj roșu în stânga-sus, o grilă albă fină (1 px) și un cerc central galben. Aceste repere permit confirmarea corectitudinii algoritmilor de rotire, oglindire și asamblare a feliilor transmise prin MPI:"
        ),
        figure0,
        (
            "## 1. Variația Timpului de Execuție în Funcție de Numărul de Procese MPI (`np`)\n"
            "**Concluzii experimentale:**\n"
            "- **Operații cu calcul intensiv per pixel (`blur` și `pipeline`):** Timpul de execuție scade pronunțat pe măsură ce adăugăm workeri, evidențiind o scalabilitate puternică (Strong Scaling).\n"
            "- **Operații simple (`grayscale`):** Complexitatea aritmetică redusă per pixel face ca timpul de transmitere a datelor prin memorie/rețea să limiteze câștigul paralel.\n"
            "- **Saturația Hardware (Oversubscription):** Peste numărul de nuclee fizice/logice ale mașinii, panta se aplatizează sau începe să urce ușor din cauza context-switching-ului la nivel de OS."
        ),
        figure1,
        (
            "## 2. Analiza Speedup-ului Paralel ($S_p = \\frac{T_{seq}}{T_{par}}$)\n"
            "Speedup-ul măsoară accelerarea obținută comparativ cu execuția secvențială:\n"
            "- Pentru filtrul **Box Blur**, volumul mare de operații aritmetice pe vecinătăți oferă un speedup solid pe arhitecturi multi-core.\n"
            "- Pentru filtrul **Grayscale**, speedup-ul rămâne aproape de 1.0x-1.1x din cauza raportului mic între calcul și comunicație."
        ),
        figure2,
        (
            "## 3. Scalabilitatea cu Rezoluția Imaginii ($N \\times M$ Megapixeli)\n"
            "Timpul de execuție crește liniar cu numărul de pixeli, conform complexității $O(N \\cdot M)$. Pe imagini mari (8MP), panta execuției paralele este semnificativ mai mică decât cea secvențială, confirmând eficiența algoritmului paralel pe volume mari de date."
        ),
        figure3,
        (
            "## 4. Comparația Strategiilor de Divizare (1D vs. 2D) și Load-Balancing (Static vs. Dinamic)\n"
            f"Comparația folosește {mid_np - 1} workeri și un coordonator. Modul `static_2d` formează o grilă 2×2.\n\n"
            "Barele sunt alăturate deoarece intervalele măsurate se suprapun. Timpul apelurilor MPI este măsurat pe coordonator și include așteptarea rezultatelor de la workeri. Calculul CPU reprezintă timpul cumulat maxim pe un worker. Suma acestor valori nu reprezintă timpul total.\n\n"
            "Pack/unpack include alocarea bufferelor temporare. Feliile care ocupă întreaga lățime sunt transmise direct, deci pot avea timp de pack/unpack zero. Dalele 2D necesită copierea rândurilor în buffere contigue și reasamblarea rezultatului."
        ),
        figure4,
        "".join(tbl)
    ]

    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write("\n\n".join(section.rstrip() for section in sections) + "\n")

    print(f"{TermUI.GREEN}✔ Raport final regenerat cu succes -> {REPORT_FILE}{TermUI.RESET}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--hosts", type=str, default=HOSTS)
    args = parser.parse_args()

    compile_mpi_code()
    results, max_res, mid_np, sample_outs = run_benchmark_suite(hosts=args.hosts)
    generate_detailed_report(results, max_res, mid_np, args.hosts, sample_outs)
