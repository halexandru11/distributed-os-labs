#!/usr/bin/env python3
"""Aggregate complete repetitions and independent seeds, then plot real timings."""
import argparse
import base64
from collections import defaultdict
import csv
import html
import json
import math
from pathlib import Path
import statistics

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
import numpy as np

from benchmark import ROOT, VARIANTS, SCHEDULES

GROUP = ("machine", "campaign", "n", "m", "r", "variant", "layout", "dataset", "gp",
         "threads_i", "threads_j", "threads_k", "schedule_i", "chunk_i",
         "schedule_j", "chunk_j", "schedule_k", "chunk_k")


def aggregate(folder):
    """First average repetitions of one pair, then give each seed equal weight.

    An incomplete/timed-out seed never contributes a selectively fast partial
    sample. Groups with missing seeds retain a PARTIAL flag and are not ranked.
    """
    raw, metadata = [], {}
    for path in sorted(folder.glob("*/metadata.json")):
        info = json.loads(path.read_text())
        metadata[info["hostname"]] = info
        machine_raw = [json.loads(line) for line in (path.parent / "runs.jsonl").read_text().splitlines()]
        if "configurations" in info and len({row["config_id"] for row in machine_raw}) != info["configurations"]:
            raise ValueError(f"{path.parent}: collection incomplete; resume before generating conclusions")
        raw += machine_raw
    if not metadata:
        raise ValueError(f"no machine results in {folder}")
    per_config = defaultdict(list)
    for row in raw:
        per_config[(row["machine"], row["config_id"])].append(row)
    groups = defaultdict(list)
    failures = []
    for (machine, _), rows in per_config.items():
        samples = [row for row in rows if row["status"] == "OK"]
        terminal = [row for row in rows if row["status"] != "OK"]
        failures += terminal
        first = samples[0] if samples else rows[0].copy()
        if not samples:
            # Recover requested loop and scheduling information from the plan.
            plan_path = folder / machine / "plan.json"
            if machine not in plan_cache:
                from benchmark import Config
                plan_cache[machine] = {}
                for config in json.loads(plan_path.read_text()):
                    config["threads"] = tuple(config["threads"])
                    config["overrides"] = tuple(tuple(item) for item in config["overrides"])
                    item = Config(**config)
                    plan_cache[machine][item.id] = item
            config = plan_cache[machine][first["config_id"]]
            from benchmark import LOOPS
            loops = LOOPS[config.variant]
            threads = list(config.threads or balanced_threads(config.variant, config.budget))
            first.update(gp=math.prod(threads[loop] for loop in loops))
            for loop, size in zip("ijk", threads):
                first["threads_"+loop] = size
            overrides = dict(config.overrides)
            for loop in "ijk":
                schedule = overrides.get(loop, config.schedule)
                kind, _, chunk = schedule.partition(":")
                first["schedule_"+loop] = kind
                first["chunk_"+loop] = int(chunk) if chunk else (0 if kind == "static" else 1)
        expected = metadata[machine]["settings"]["repeats"]
        complete = (len(samples) == expected and not terminal
                    and {row["repeat"] for row in samples} == set(range(expected)))
        groups[tuple(first.get(key) for key in GROUP)].append((complete, samples, terminal))
    summary = []
    for key, entries in groups.items():
        row = dict(zip(GROUP, key))
        complete = [samples for valid, samples, _ in entries if valid]
        values = [sample["seconds"] for samples in complete for sample in samples]
        has_error = any(event["status"] == "ERROR" for _, _, events in entries for event in events)
        row.update(series_expected=len(entries), series_complete=len(complete), samples=len(values),
                   timeouts=sum(event["status"] == "TIMEOUT" for _, _, events in entries for event in events),
                   status="ERROR" if has_error else "OK" if len(complete) == len(entries) else "PARTIAL" if complete else "TIMEOUT")
        if values:
            means = [statistics.mean(sample["seconds"] for sample in samples) for samples in complete]
            row.update(mean_seconds=statistics.mean(means), median_seconds=statistics.median(values),
                       min_seconds=min(values), max_seconds=max(values),
                       stdev_seconds=statistics.stdev(values) if len(values) > 1 else 0,
                       seed_stdev_seconds=statistics.stdev(means) if len(means) > 1 else 0,
                       mean_minor_faults=statistics.mean(sample["minor_faults"] for samples in complete for sample in samples),
                       major_faults=sum(sample["major_faults"] for samples in complete for sample in samples))
            row["cv_percent"] = 100 * row["stdev_seconds"] / row["mean_seconds"]
            row["gops"] = 2 * row["n"] * row["m"] * row["r"] / row["mean_seconds"] / 1e9
        summary.append(row)
    baseline_keys = ("machine", "campaign", "n", "m", "r", "layout", "dataset")
    baselines = {tuple(row[key] for key in baseline_keys): row["mean_seconds"] for row in summary
                 if row["variant"] == "seq" and row["status"] == "OK"}
    for row in summary:
        baseline = baselines.get(tuple(row[key] for key in baseline_keys))
        if baseline and row["status"] == "OK":
            row["speedup"] = baseline / row["mean_seconds"]
            row["efficiency"] = row["speedup"] / row["gp"]
    summary.sort(key=lambda row: tuple(str(row.get(key)) for key in GROUP))
    return raw, metadata, summary, failures


plan_cache = {}


def balanced_threads(variant, budget):
    """Mirror the documented allocator to annotate timeouts with no samples."""
    from benchmark import LOOPS
    loops = LOOPS[variant]
    best = (1, 1, 1)
    if len(loops) == 1:
        best = (budget, 1, 1)
    elif len(loops) >= 2:
        candidates = [(a, b, budget//(a*b)) for a in range(1, budget+1) for b in range(1, a+1)
                      if budget % (a*b) == 0 and
                      ((len(loops) == 2 and budget//(a*b) == 1) or
                       (len(loops) == 3 and budget//(a*b) <= b))]
        best = min(candidates, key=lambda sizes: sizes[0] - (sizes[2] if len(loops) == 3 else sizes[1]))
    threads = [1, 1, 1]
    for loop, value in zip(loops, best):
        threads[loop] = value
    return tuple(threads)


def csv_write(path, rows):
    if not rows:
        path.write_text("")
        return
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def select(rows, **criteria):
    return [row for row in rows if all(row.get(key) == value for key, value in criteria.items())]


def save_figure(figure, folder, name):
    figure.savefig(folder / (name + ".png"), dpi=150, bbox_inches="tight")
    tooltips = {}
    for axis_index, axis in enumerate(figure.axes):
        if axis.get_label() == '<colorbar>':
            continue
        unit = '×' if name == 'speedup' else ('s' if name == 'layout' else 'ms')
        for index, line in enumerate(axis.lines):
            key = f'line2d_data_{axis_index}_{index}'
            line.set_gid(key)
            tooltips[key] = {'kind': 'line', 'unit': unit,
                             'points': [[float(x), float(y)] for x, y in
                                        zip(line.get_xdata(), line.get_ydata())],
                             'label': line.get_label()}
        ticks = axis.get_xticks()
        labels = [label.get_text() for label in axis.get_xticklabels()]
        for index, bar in enumerate(axis.patches):
            key = f'patch_data_{axis_index}_{index}'
            bar.set_gid(key)
            center = bar.get_x() + bar.get_width() / 2
            category = labels[min(range(len(ticks)), key=lambda i: abs(ticks[i] - center))] if len(ticks) else ''
            tooltips[key] = {'kind': 'bar', 'unit': unit,
                             'value': float(bar.get_height()), 'category': category}
    figure.savefig(folder / (name + ".svg"), bbox_inches="tight",
                   metadata={'Description': json.dumps(tooltips)})
    plt.close(figure)


def generic_chart(summary, metadata, figures):
    figure, axes = plt.subplots(1, len(metadata), figsize=(8*len(metadata), 5), squeeze=False)
    keys = ("campaign", "n", "m", "r", "layout", "dataset", "schedule_i", "chunk_i")
    for axis, machine in zip(axes.flat, sorted(metadata)):
        available = select(summary, machine=machine, status="OK", dataset="random")
        anchor = next((row for row in available if row["variant"] != "seq"), None)
        if anchor is None:
            continue
        chosen = [row for row in available if all(row[key] == anchor[key] for key in keys)
                  and row["gp"] == anchor["gp"]]
        axis.bar([row["variant"] for row in chosen], [row["mean_seconds"]*1000 for row in chosen])
        axis.set(yscale="log", ylabel="Mean milliseconds (log scale)",
                 title=f"{machine}: {anchor['n']}×{anchor['m']}×{anchor['r']}, GP={anchor['gp']}, {anchor['layout']}, {anchor['schedule_i']}")
        axis.tick_params(axis="x", labelrotation=65)
    figure.tight_layout()
    save_figure(figure, figures, "comparison")


def match_panel_scales(figure):
    """Match vertical limits and heatmap colors within each laptop pair."""
    panels = [axis for axis in figure.axes if axis.get_label() != '<colorbar>']
    if not panels:
        return
    for getter, setter in (("get_ylim", "set_ylim"),):
        bounds = [getattr(axis, getter)() for axis in panels]
        lower = min(min(pair) for pair in bounds)
        upper = max(max(pair) for pair in bounds)
        for axis, pair in zip(panels, bounds):
            getattr(axis, setter)((upper, lower) if pair[0] > pair[1] else (lower, upper))
    images = [image for axis in panels for image in axis.images]
    if images:
        norm = LogNorm(vmin=min(image.norm.vmin for image in images),
                       vmax=max(image.norm.vmax for image in images))
        for image in images:
            image.set_norm(norm)


def charts(summary, metadata, figures):
    figures.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.size": 9, "axes.grid": True, "grid.alpha": .2})
    machines = sorted(metadata)
    generated = []

    def finish(figure, name):
        match_panel_scales(figure)
        save_figure(figure, figures, name)
        generated.append(name)

    # Every dimension/variant is visible; gray means incomplete or timed out.
    from benchmark import SHAPES
    campaigns = {row["campaign"] for row in summary}
    if "dimensions" in campaigns:
        figure, axes = plt.subplots(len(machines), 1, figsize=(12, 5*len(machines)), squeeze=False)
        for axis, machine in zip(axes.flat, machines):
            data = np.full((len(VARIANTS), len(SHAPES)), np.nan)
            for row in select(summary, machine=machine, campaign="dimensions", dataset="random", status="OK"):
                shape = (row["n"], row["m"], row["r"])
                data[VARIANTS.index(row["variant"]), SHAPES.index(shape)] = row["mean_seconds"] * 1000
            if not np.isfinite(data).any():
                continue
            color_map = plt.get_cmap("viridis").copy()
            color_map.set_bad("#dedede")
            picture = axis.imshow(data, aspect="auto", norm=LogNorm(vmin=np.nanmin(data), vmax=np.nanmax(data)), cmap=color_map)
            axis.set_xticks(range(len(SHAPES)), [f"{n}×{m}×{r}" for n,m,r in SHAPES], rotation=20, ha="right")
            axis.set_yticks(range(len(VARIANTS)), VARIANTS)
            axis.set_title(f"{machine}: mean kernel time, dimensions study (gray = timeout/incomplete)")
            axis.grid(False)
            figure.colorbar(picture, ax=axis, label="milliseconds (logarithmic color scale)")
        figure.tight_layout()
        finish(figure, "dimensions")

    if "threads" in campaigns:
        figure, axes = plt.subplots(1, len(machines), figsize=(8*len(machines), 5), squeeze=False)
        for axis, machine in zip(axes.flat, machines):
            for variant in VARIANTS[1:]:
                rows = sorted(select(summary, machine=machine, campaign="threads", variant=variant, status="OK"), key=lambda row: row["gp"])
                if rows:
                    axis.plot([row["gp"] for row in rows], [row["mean_seconds"]*1000 for row in rows], marker=".", label=variant)
            shapes = sorted({(row["n"], row["m"], row["r"]) for row in summary
                             if row["machine"] == machine and row["campaign"] == "threads"})
            shape_label = ", ".join("×".join(map(str, shape)) for shape in shapes)
            axis.set(yscale="log", xlabel="Total requested thread budget GP", ylabel="Mean milliseconds (log scale)",
                     title=f"{machine}: {shape_label}, all parallel variants")
            axis.axvline(len(metadata[machine]["affinity_cpus"]), color="black", linestyle=":", label="logical CPUs")
            axis.legend(fontsize=7, ncol=2)
        figure.tight_layout()
        finish(figure, "threads")

    if "scaling" in campaigns:
        figure, axes = plt.subplots(1, len(machines), figsize=(6*len(machines), 4.5), squeeze=False)
        for axis, machine in zip(axes.flat, machines):
            for variant in ("parallel_i", "collapse_ij"):
                rows = sorted(select(summary, machine=machine, campaign="scaling", variant=variant, status="OK"), key=lambda row: row["gp"])
                if rows:
                    axis.plot([row["gp"] for row in rows], [row.get("speedup", math.nan) for row in rows], marker=".", label=variant)
            axis.axhline(1, color="gray", linestyle="--", label="sequential baseline")
            axis.axvline(len(metadata[machine]["affinity_cpus"]), color="black", linestyle=":", label="logical CPUs")
            axis.set(xlabel="Total requested thread budget GP", ylabel="Speedup = mean Tseq / mean Tpar",
                     title=f"{machine}: 300×300×300")
            axis.legend()
        figure.tight_layout()
        finish(figure, "speedup")

    if "schedules" in campaigns:
        figure, axes = plt.subplots(len(machines), 1, figsize=(11, 5*len(machines)), squeeze=False)
        for axis, machine in zip(axes.flat, machines):
            data = np.full((len(VARIANTS)-1, len(SCHEDULES)), np.nan)
            for row in select(summary, machine=machine, campaign="schedules", dataset="random", status="OK"):
                if row["variant"] == "seq":
                    continue
                kind, chunk = row["schedule_i"], row["chunk_i"]
                label = kind + (":"+str(chunk) if chunk else "")
                data[VARIANTS.index(row["variant"])-1, SCHEDULES.index(label)] = row["mean_seconds"]*1000
            if np.isfinite(data).any():
                picture = axis.imshow(data, aspect="auto", norm=LogNorm(vmin=np.nanmin(data), vmax=np.nanmax(data)))
                figure.colorbar(picture, ax=axis, label="milliseconds (logarithmic color scale)")
            axis.set_xticks(range(len(SCHEDULES)), SCHEDULES)
            axis.set_yticks(range(len(VARIANTS)-1), VARIANTS[1:])
            axis.set_title(f"{machine}: schedule/chunk, 10×10×10, GP=4")
            axis.grid(False)
        figure.tight_layout()
        finish(figure, "schedules")

    if "layout_large" in campaigns:
        figure, axes = plt.subplots(1, len(machines), figsize=(6*len(machines), 4.5), squeeze=False)
        for axis, machine in zip(axes.flat, machines):
            variants = ("seq", "parallel_i", "collapse_ij")
            for offset, layout in ((-.18, "row"), (.18, "transposed")):
                values = []
                for variant in variants:
                    rows = select(summary, machine=machine, campaign="layout_large", variant=variant, layout=layout, status="OK")
                    values.append(rows[0]["mean_seconds"] if rows else math.nan)
                axis.bar(np.arange(3)+offset, values, width=.36, label=layout)
            axis.set_xticks(range(3), variants)
            axis.set(ylabel="Mean seconds", title=f"{machine}: B layout, 1000×1000×1000")
            axis.legend()
        figure.tight_layout()
        finish(figure, "layout")

    if "dimensions" in campaigns:
        figure, axes = plt.subplots(1, len(machines), figsize=(7*len(machines), 5), squeeze=False)
        for axis, machine in zip(axes.flat, machines):
            for offset, dataset in ((-.24, "random"), (0, "zeros"), (.24, "max")):
                values = []
                for variant in VARIANTS:
                    rows = select(summary, machine=machine, campaign="dimensions", n=100, m=100, r=100,
                                  variant=variant, dataset=dataset, status="OK")
                    values.append(rows[0]["mean_seconds"]*1000 if rows else math.nan)
                axis.bar(np.arange(len(VARIANTS))+offset, values, width=.24, label=dataset)
            axis.set_xticks(range(len(VARIANTS)), VARIANTS, rotation=60, ha="right")
            axis.set(yscale="log", ylabel="Mean milliseconds (log scale)", title=f"{machine}: input values, 100×100×100")
            axis.legend()
        figure.tight_layout()
        finish(figure, "inputs")

    if "allocation" in campaigns:
        figure, axes = plt.subplots(len(machines), 1, figsize=(12, 6*len(machines)), squeeze=False)
        for axis, machine in zip(axes.flat, machines):
            rows = select(summary, machine=machine, campaign="allocation", dataset="random", status="OK")
            labels = sorted({(row["variant"], row["threads_i"], row["threads_j"], row["threads_k"]) for row in rows if row["variant"] != "seq"})
            for offset, mixed in ((-.18, False), (.18, True)):
                values = []
                for variant,i,j,k in labels:
                    chosen = [row for row in rows if (row["variant"],row["threads_i"],row["threads_j"],row["threads_k"]) == (variant,i,j,k)
                              and (row["schedule_i"] == "dynamic") == mixed]
                    values.append(chosen[0]["mean_seconds"]*1000 if chosen else math.nan)
                axis.bar(np.arange(len(labels))+offset, values, width=.36, label="mixed per-loop schedules" if mixed else "static on all loops")
            axis.set_xticks(range(len(labels)), [f"{v}\n{i},{j},{k}" for v,i,j,k in labels], rotation=45, ha="right", fontsize=10)
            axis.set(yscale="log", ylabel="Mean milliseconds (log scale)", title=f"{machine}: fixed GP=8, nested allocation")
            axis.legend(fontsize=8)
        figure.tight_layout()
        finish(figure, "allocation")

    if not generated:
        generic_chart(summary, metadata, figures)
        generated.append("comparison")
    return generated


def markdown_table(headers, rows):
    return "\n".join(["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"] +
                     ["| " + " | ".join(map(str, row)) + " |" for row in rows])


def dimension_details(summary, metadata):
    """List every heatmap cell, including unavailable results, in a closed table."""
    from benchmark import SHAPES

    details = []
    for machine in sorted(metadata):
        for n, m, r in SHAPES:
            rows = select(summary, machine=machine, campaign="dimensions",
                          n=n, m=m, r=r, dataset="random", layout="row")
            by_variant = {row["variant"]: row for row in rows}
            complete = [row for row in rows if row["status"] == "OK"]
            best = min((row["mean_seconds"] for row in complete), default=None)
            for variant in VARIANTS:
                row = by_variant.get(variant)
                if row is None:
                    details.append([machine, f"{n}×{m}×{r}", variant,
                                    "LIPSĂ", "n/a", "n/a", "n/a", "n/a", "n/a", "n/a"])
                    continue
                ok = row["status"] == "OK"
                label = f"**{variant}**" if ok and row["mean_seconds"] == best else variant
                details.append([machine, f"{n}×{m}×{r}", label, row["status"], row["gp"],
                                f"{row['mean_seconds'] * 1000:.8g}" if ok else "n/a",
                                f"{row['speedup']:.4f}" if ok and "speedup" in row else "n/a",
                                f"{row['cv_percent']:.1f}%" if ok else "n/a",
                                f"{row['series_complete']}/{row['series_expected']}", row["timeouts"]])
    return "\n\n".join([
        '<details>\n<summary>Rezultate detaliate pentru toate variantele și dimensiunile</summary>',
        'Aceleași configurații ca în hărțile de mai sus, cu intrări `random`, B pe linii și schedule `static`. '
        'Varianta cu cel mai mic timp valid pentru fiecare mașină și dimensiune este scrisă cu caractere aldine. '
        '`PARTIAL` indică seed-uri incomplete; `n/a` indică o valoare indisponibilă sau exclusă din comparație. '
        'TIMEOUT-uri numără evenimentele de întrerupere, nu timpi ai nucleului.',
        markdown_table(["Mașină", "n×m×r", "Variantă", "Status", "GP", "Media ms", "Speedup", "CV repetări",
                        "Seed-uri complete/cerute", "TIMEOUT-uri"], details),
        '</details>'])


def thread_details(summary):
    """Include both thread campaigns and their sequential references."""
    lines = ['<details>',
             '<summary>Rezultate detaliate pentru toate variantele și bugetele GP</summary>', '',
             'Tabelele includ toate configurațiile salvate din cele două campanii, inclusiv referințele '
             'secvențiale. Intrările sunt `random`, cu B pe linii și schedule `static`. '
             'Bugetul cu cel mai mic timp valid pentru fiecare variantă, dimensiune și mașină este scris '
             'cu caractere aldine. `n/a` indică o valoare indisponibilă sau exclusă din comparație. '
             'Pentru configurațiile incomplete, coloana Media ms afișează statusul, iar ceilalți indicatori sunt `n/a`.', '']
    for campaign, heading in (("scaling", "Scalare pentru parallel_i și collapse_ij"),
                              ("threads", "Variația bugetului GP pentru toate variantele")):
        rows = [row for row in summary if row["campaign"] == campaign
                and row["dataset"] == "random" and row["layout"] == "row"]
        rows.sort(key=lambda row: (row["machine"], row["n"], row["m"], row["r"],
                                  VARIANTS.index(row["variant"]), row["gp"]))
        best = {}
        for row in rows:
            key = (row["machine"], row["n"], row["m"], row["r"], row["variant"])
            if row["status"] == "OK":
                best[key] = min(best.get(key, math.inf), row["mean_seconds"])
        table = []
        for row in rows:
            key = (row["machine"], row["n"], row["m"], row["r"], row["variant"])
            ok = row["status"] == "OK"
            gp = f"**{row['gp']}**" if ok and row["mean_seconds"] == best[key] else row["gp"]
            table.append([row["machine"], row["variant"], gp,
                          f"{row['mean_seconds'] * 1000:.8g}" if ok else row["status"],
                          f"{row['speedup']:.4f}" if ok and "speedup" in row else "n/a",
                          f"{row['efficiency']:.4f}" if ok and "efficiency" in row else "n/a",
                          f"{row['cv_percent']:.1f}%" if ok else "n/a"])
        shapes = sorted({(row["n"], row["m"], row["r"]) for row in rows})
        shape_label = ", ".join(f"{n}³" if n == m == r else f"{n}×{m}×{r}" for n, m, r in shapes)
        if len(shapes) > 1:
            for cells, row in zip(table, rows):
                cells[1] += f" · {row['n']}×{row['m']}×{row['r']}"
        lines += ["### " + heading, '',
                  markdown_table(["Mașină", "Variantă, " + shape_label, "GP", "Media ms", "Speedup",
                                  "Eficiență S/GP", "CV"], table), '']
    lines += ['</details>']
    return "\n".join(lines)


def report(folder, figures, raw, metadata, summary, failures, generated):
    if {info["settings"]["profile"] for info in metadata.values()} != {"study"}:
        generic_report(folder, figures, raw, metadata, summary, failures, generated)
        return
    from benchmark import SHAPES
    lines = ["# HW2 — Rezultate experimentale măsurate", "",
             "Datele provin exclusiv din execuțiile salvate în subdirectoarele fiecărei mașini. "
             "Regenerare: `python3 HW2/analyze.py --input HW2/results/study`.", "",
             "## Platforme și metodologie", ""]
    hardware = []
    for machine, info in sorted(metadata.items()):
        cpu = {item["field"].rstrip(":"): item["data"] for item in json.loads(info["lscpu"])["lscpu"]}
        topology = {tuple(line.split(",")[1:3]) for line in info["topology"].splitlines() if not line.startswith("#")}
        ram = int(next(line.split()[1] for line in info["meminfo"].splitlines() if line.startswith("MemTotal:"))) / 1024**2
        hardware.append([machine, cpu.get("Model name"), len(topology), len(info["affinity_cpus"]),
                         f"{ram:.1f} GiB", info["created_utc"], f"{info['load_start'][0]:.2f} / {info['load_end'][0]:.2f}"])
    lines += [markdown_table(["Mașină", "CPU", "Core-uri fizice", "CPU logice disponibile", "RAM", "Început UTC", "Load 1 min început/final"], hardware), "",
              "GCC 13.3, `-O3 -std=c11 -fopenmp`, Ubuntu 24.04; versiunile exacte, topologia, "
              "guvernorii CPU, memoria, mediul OpenMP și hash-urile surselor sunt în `metadata.json`. "
              "Victus are un procesor hibrid: numărul de CPU logice nu se deduce prin dublarea tuturor core-urilor fizice.", "",
              "Măsurăm cu `omp_get_wtime()` numai apelul nucleului, inclusiv crearea echipelor, "
              "planificarea și sincronizarea cerute de variantă. Generarea A/B, aranjarea lui B, alocarea, "
              "resetarea lui C, referința secvențială și verificarea tuturor elementelor sunt în afara intervalului. "
              "O încălzire precedă cele cinci repetări ale aceleiași perechi. Pentru cazul aleator se folosesc "
              "cinci seed-uri distincte (1001–1005), identice între variante și calculatoare. Media este întâi "
              "calculată pe repetările unui seed, apoi pe seed-uri cu ponderi egale.", "",
              "`GP` este bugetul total cerut: produsul dimensiunilor echipelor pentru nivelurile nested; "
              "un `collapse` folosește o singură echipă. Bugetul este factorizat echilibrat, iar pentru GP prim "
              "nivelurile interioare au un fir. Campania `allocation` compară alte repartizări la GP=8. "
              "Mediul folosește `OMP_WAIT_POLICY=PASSIVE`, `OMP_DYNAMIC=FALSE`, `OMP_PROC_BIND=FALSE`; "
              "dimensiunile realizate în proba de echipe sunt păstrate în fiecare înregistrare.", "",
              "Profilul `study` separă factorii: dimensiuni (8 forme, toate variantele, GP=4), "
              "thread-uri (toate variantele, dimensiunile din grafic), scalare (variantele i și collapse(ij), 300³), "
              "schedule/chunk (toate variantele, 10³ și suplimentar i/collapse(ij) la 300³), "
              "layout B (toate variantele, 100³ și variantele i/collapse(ij) la 1000³), "
              "repartizarea nivelurilor și schedule-uri independente (10³). "
              "Cazurile zeros și max sunt incluse în campaniile dimensiuni și schedule. "
              "Profilul `full` disponibil în script permite produsul cartezian complet ales de utilizator.", "",
              "## Integritatea datelor și limitele măsurării", ""]
    counts = []
    for machine, info in sorted(metadata.items()):
        machine_raw = [row for row in raw if row["machine"] == machine]
        counts.append([machine, info["configurations"], sum(row["status"] == "OK" for row in machine_raw),
                       sum(row["status"] == "TIMEOUT" for row in machine_raw),
                       f"1–{info['settings']['max_threads'] or max(8, 2*len(info['affinity_cpus']))}"])
    lines += [markdown_table(["Mașină", "Configurații", "Repetări verificate", "Configurații TIMEOUT", "Bugete GP"], counts), "",
              "Limita este de 3 secunde pentru o invocare completă, respectiv 30 de secunde pentru "
              "configurațiile mari seq/i/j/collapse(ij). Include inițializarea, referința, încălzirea și toate repetările; "
              "TIMEOUT nu reprezintă un timp măsurat al înmulțirii. Repetările finalizate înaintea întreruperii "
              "rămân în datele brute, dar un seed incomplet este exclus integral din medii. "
              "Grupurile cu seed-uri lipsă sunt marcate PARTIAL și nu intră în grafice sau clasamente. "
              "Nu se înlocuiesc timeout-urile cu zero sau cu durata limită.", "",
              "Numerele sunt `uint64_t`; operațiile sunt definite modulo 2⁶⁴. Cazul `max` conține UINT64_MAX "
              "și are C[i,j]=m modulo 2⁶⁴, fără overflow semnat nedefinit. Cazul aleator [0,100] și zeros "
              "au rezultate matematice exacte pentru dimensiunile studiate. Înmulțirea cu numere de "
              "precizie arbitrară nu este studiată. Denumirile best/worst din enunț descriu valorile "
              "de intrare; nu garantează extrema timpului pentru instrucțiuni întregi de lățime fixă.", "",
              "Nu am izolat sistemele de toate serviciile și aplicațiile: load-ul observat este în tabel. "
              "Frecvența, migrarea pe core-uri și încărcarea concurentă pot afecta mediile. "
              "Rulările foarte mici sunt dominate de overhead și de variația măsurării; nu se extrapolează "
              "scalarea lor la matrici mari. Numărul de page faults este observat, dar nu dovedește "
              "cauzalitatea efectului cache-ului. Nu sunt efectuate comparații Docker/VM ori experimente "
              "controlate cu/fără Hyper-Threading.", "",
              "## Dimensiuni și alegerea variantei", ""]
    lines += ["![Dimensiuni](../../figures/study/dimensions.png)", "",
              dimension_details(summary, metadata), "",
              "Varianta i și collapse(ij) oferă celule independente fără sincronizare în bucla k. "
              "Paralelizarea k creează o echipă pentru fiecare celulă; variantele nested creează "
              "echipe suplimentare pentru fiecare iterație a nivelului exterior. collapse(jk), "
              "collapse(ijk) și hibridul i/(jk) execută câte un atomic per contribuție, deoarece "
              "iterațiile distincte pot actualiza aceeași celulă. Aceste costuri explică diferențele "
              "structurale; tabelul arată care dintre variante câștigă efectiv pe datele măsurate.", "",
              "## Numărul de thread-uri și factorul de accelerare", ""]
    lines += ["![Speedup](../../figures/study/speedup.png)", "",
              "![Thread-uri](../../figures/study/threads.png)", "",
              thread_details(summary), "",
              "Speedup = media Tseq / media Tpar pentru același calculator, campanie, formă, layout "
              "și distribuție a datelor. Eficiența este speedup/GP. Optimele sunt minime observate "
              "pe această grilă, nu garanții sau recomandări universale. Oversubscription nu adaugă "
              "unități de execuție fizice; core-urile P/E și SMT ale platformelor nu au performanțe identice. "
              "Bugetele consecutive includ GP=1, care păstrează overhead-ul OpenMP.", "",
              "## Schedule și dimensiunea chunk-ului", ""]
    lines += ["![Schedule](../../figures/study/schedules.png)", "",
              "Toate celulele fac m produse; lucrul aritmetic este uniform. Un schedule dinamic "
              "nu reduce automat timpul: introduce distribuire de task-uri, iar chunk-uri mici "
              "pot afecta localitatea sau induce false sharing. Efectul trebuie citit împreună "
              "cu mărimea problemei și variabilitatea. schedule(runtime) este setat pentru task-ul "
              "care întâlnește fiecare regiune, astfel încât nivelurile nested pot avea politici diferite.", "",
              "## Memorie și valorile elementelor", ""]
    layout_ratios = []
    for machine in sorted(metadata):
        for variant in ("seq", "parallel_i", "collapse_ij"):
            row = select(summary, machine=machine, campaign="layout_large", variant=variant, layout="row", status="OK")
            transposed = select(summary, machine=machine, campaign="layout_large", variant=variant, layout="transposed", status="OK")
            if row and transposed:
                layout_ratios.append([machine, variant, f"{row[0]['mean_seconds']:.5g}",
                                      f"{transposed[0]['mean_seconds']:.5g}",
                                      f"{row[0]['mean_seconds']/transposed[0]['mean_seconds']:.3f}"])
    lines += [markdown_table(["Mașină", "Variantă, 1000³", "B pe linii, s", "B transpus, s", "Trow / Ttransposed"], layout_ratios), "",
              "![Layout](../../figures/study/layout.png)", "",
              "B transpus permite citiri consecutive pentru ambii operanzi ai unui produs scalar. "
              "Generarea/aranjarea lui B este exclusă din timp; comparația evaluează nucleul, "
              "nu costul total pentru o singură înmulțire cu o transpunere suplimentară. "
              "La 1000³ campania layout folosește un singur seed și cinci repetări; campania layout "
              "la 100³ folosește cinci seed-uri.", "",
              "![Valori intrare](../../figures/study/inputs.png)", "",
              "zeros, random și max parcurg aceleași bucle, fără scurtcircuitări pentru zero. "
              "Diferențele observate se raportează cu precauție: pentru uint64_t instrucțiunile "
              "nu au un cost proporțional cu numărul de cifre al operandului.", "",
              "## Repartizarea thread-urilor pe niveluri", "",
              "![Alocare niveluri](../../figures/study/allocation.png)", "",
              'Fiecare pereche de bare compară aceeași variantă și aceeași repartizare a thread-urilor, cu două politici de planificare:',
              '',
              '- **static on all loops** folosește `static` pe toate buclele paralelizate. Firele primesc iterațiile în avans.',
              '- **mixed per-loop schedules** folosește **`dynamic:1 / guided:2 / static:2`** pe buclele `i / j / k`, respectiv. Pentru `i`, firele cer dinamic câte o iterație; pentru `j`, blocurile scad progresiv, cu un minim de două iterații; pentru `k`, blocurile de câte două iterații sunt atribuite static. Ultimul bloc poate fi mai mic. Politica se aplică numai dacă bucla respectivă este paralelizată.',
              '',
              'Înălțimea barei reprezintă timpul mediu al nucleului de înmulțire, în **milisecunde**, pe o **scară logaritmică**. Un timp mai mic este mai bun. Timpul include crearea echipelor OpenMP, planificarea și sincronizarea; generarea matricilor și verificarea rezultatului sunt în afara intervalului măsurat.',
              '',
              'Această campanie folosește matrici **10×10×10** și bugetul total **`GP=8`**. Etichetele de pe axa X arată varianta și vectorul `(Ti,Tj,Tk)`. De exemplu, `nested_ij` cu `4,2,1` cere patru thread-uri la nivelul `i` și două la nivelul `j`, pentru un buget total de opt; bucla `k` rămâne secvențială.',
              '',
              'Pentru două niveluri se compară repartizările `(8,1)`, `(4,2)` și `(1,8)`; pentru trei niveluri, `(8,1,1)`, `(2,2,2)` și `(1,1,8)`. Același buget poate produce numere diferite de regiuni interioare active. Într-un grup `collapse`, dimensiunea echipei este cea a primei bucle din grup. Politicile și dimensiunile echipelor se pot configura independent din CLI.',
              '',
              "## Concluzii și reproducere", ""]
    for machine in sorted(metadata):
        small = select(summary, machine=machine, campaign="dimensions", n=10,m=10,r=10,
                       dataset="random", status="OK")
        large = select(summary, machine=machine, campaign="dimensions", n=1000,m=1000,r=1000,
                       dataset="random", status="OK")
        if small and large:
            small_best = min(small, key=lambda row: row["mean_seconds"])
            large_best = min(large, key=lambda row: row["mean_seconds"])
            lines += [f"- **{machine}:** la 10³ câștigă `{small_best['variant']}` "
                      f"({small_best['mean_seconds']*1000:.5g} ms); la 1000³ câștigă "
                      f"`{large_best['variant']}` dintre variantele finalizate, cu "
                      f"{large_best['mean_seconds']*1000:.5g} ms și speedup "
                      f"{format(large_best['speedup'], '.3f')+'×' if 'speedup' in large_best else 'necunoscut (referință incompletă)'} la GP={large_best['gp']}. "
                      "Pragul de rentabilitate al paralelizării depinde de mărimea produsului.", ""]
        scaling = select(summary, machine=machine, campaign="scaling", status="OK")
        scaling = [row for row in scaling if row["variant"] != "seq" and "speedup" in row]
        if scaling:
            best = min(scaling, key=lambda row: row["mean_seconds"])
            lines += [f"- **{machine}, buget:** pe grila 300³, cea mai mică medie este "
                      f"{best['mean_seconds']*1000:.5g} ms pentru `{best['variant']}`, "
                      f"GP={best['gp']}, speedup {best['speedup']:.3f}×. "
                      "Aceasta este alegerea măsurată pentru această sarcină; se verifică CV și "
                      "se repetă înainte de a generaliza la alte dimensiuni.", ""]
    lines += ["Pentru fiecare formă, tabelul de dimensiuni identifică varianta eficientă observată; "
              "pentru 300³, tabelele identifică bugetul GP și schedule/chunk cu timpul mediu minim "
              "în eșantion. Rezultatele trebuie alese în funcție de platformă și dimensiuni: "
              "nici adăugarea de fire, nici paralelizarea tuturor buclelor nu garantează accelerare. "
              "Pentru decizii apropiate se consultă deviația standard și CV din `summary.csv`, "
              "apoi se repetă măsurările într-un mediu mai bine controlat.", "",
              "Fișiere: `summary.csv` (medii, deviații, speedup, eficiență, timeout-uri), "
              "`failures.csv` (evenimentele TIMEOUT/ERROR), `<mașină>/runs.csv` (date brute importabile "
              "în LibreOffice/Excel), `<mașină>/runs.jsonl`, `<mașină>/plan.json` și `<mașină>/metadata.json`. "
              "Graficele PNG/SVG sunt în `HW2/figures/study/`. "
              "Comenzile și acoperirea cerințelor sunt în [README](../../README.md) și [EXPERIMENTS](../../EXPERIMENTS.md).", ""]
    # Resolve figure links for any output name, including smoke/custom runs.
    import os
    content = "\n".join(lines)
    relative = os.path.relpath(figures, folder)
    content = content.replace("../../figures/study/", relative + "/")
    (folder / "report.md").write_text(content)

    write_dashboard(folder, raw, metadata, summary, failures)


def write_dashboard(folder, raw, metadata, summary, failures):
    payload = {}
    for machine, info in sorted(metadata.items()):
        series = {}
        for variant in ("parallel_i", "collapse_ij"):
            rows = sorted(select(summary, machine=machine, campaign="scaling", variant=variant, status="OK"), key=lambda row: row["gp"])
            rows = [row for row in rows if "speedup" in row]
            series[variant] = [{key: row[key] for key in ("gp", "mean_seconds", "speedup", "efficiency", "cv_percent")} for row in rows]
        payload[machine] = {"cpus": len(info["affinity_cpus"]), "series": series}
    document = '''<!doctype html><html lang="ro"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>HW2 — Scalarea OpenMP</title><style>
:root{font-family:var(--font-sans,system-ui);color:var(--foreground,#263345)}body{margin:0;background:transparent}main{max-width:960px;margin:auto}
.controls{display:flex;align-items:center;gap:8px;flex-wrap:wrap;padding:12px 0}button{font:inherit;padding:8px 14px;border:1px solid var(--border,#cbd5e1);border-radius:var(--radius,8px);background:var(--secondary,#f1f5f9);color:var(--foreground,#263345);cursor:pointer}button[aria-pressed=true]{background:var(--primary,#2563eb);color:var(--primary-foreground,#fff);border-color:transparent}
.caption,small{font-size:12px;color:var(--muted-foreground,#64748b);line-height:1.6}.plot{width:100%;height:310px;display:block;overflow:visible}.legend{display:flex;gap:18px;font-size:13px;padding-bottom:12px;flex-wrap:wrap}.dot{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:5px}.table-wrap{overflow:auto}table{font-size:13px;border-collapse:collapse;width:100%;margin:8px 0}th,td{text-align:left;padding:9px 8px;border-bottom:1px solid var(--border,#d6dee8);white-space:nowrap}th{font-weight:600}.stats{margin:0;font-size:13px}p{line-height:1.5}#details{min-height:24px;font-size:13px}svg text{fill:var(--muted-foreground,#64748b);font-size:11px}
</style></head><body><main><p class="stats">__COUNTS__</p><div class="controls" id="controls"></div>
<div class="legend"><span><i class="dot" style="background:var(--chart-1,#3b82f6)"></i>parallel_i</span><span><i class="dot" style="background:var(--chart-2,#ec4899)"></i>collapse_ij</span><span>300×300×300 · static · B pe linii</span></div>
<svg id="plot" class="plot" viewBox="0 0 700 310" role="img" aria-label="Speedup în funcție de numărul total de thread-uri"></svg>
<p id="details" aria-live="polite">Selectează un punct pentru detalii.</p><div class="table-wrap"><table><thead><tr><th>Variantă</th><th>GP optim observat</th><th>Media ms</th><th>Speedup</th><th>Eficiență</th><th>CV</th></tr></thead><tbody id="winners"></tbody></table></div>
<p class="caption">Media pe cinci perechi aleatoare × cinci repetări. Speedup = media Tseq / media Tpar. Linia verticală indică CPU-urile logice disponibile. Optimele sunt observații pe grila măsurată și depind de încărcarea gazdei. Toate rezultatele sunt verificate; timeout-urile și seriile incomplete sunt excluse din medii. Aritmetică uint64_t modulo 2⁶⁴.</p>
<script>const data=__DATA__;const NS='http://www.w3.org/2000/svg';const colors=['var(--chart-1,#3b82f6)','var(--chart-2,#ec4899)'];
function node(tag,attrs,text){const n=document.createElementNS(NS,tag);for(const [k,v] of Object.entries(attrs))n.setAttribute(k,v);if(text!==undefined)n.textContent=text;return n}
function show(machine){document.querySelectorAll('button').forEach(b=>b.setAttribute('aria-pressed',String(b.textContent===machine)));const d=data[machine],svg=document.getElementById('plot');svg.replaceChildren();document.getElementById('winners').replaceChildren();const rows=Object.values(d.series).flat();if(!rows.length)return;const xmax=Math.max(...rows.map(r=>r.gp)),ymax=Math.ceil(Math.max(...rows.map(r=>r.speedup))*1.12);const X=g=>52+(g-1)/Math.max(1,xmax-1)*620,Y=s=>267-s/ymax*240;
for(let y=0;y<=ymax;y++){svg.append(node('line',{x1:52,x2:672,y1:Y(y),y2:Y(y),stroke:'var(--border,#d6dee8)'}));svg.append(node('text',{x:40,y:Y(y)+4,'text-anchor':'end'},y+'×'))}
const step=xmax>16?4:1;for(let x=1;x<=xmax;x++){if(x!==1&&x%step!==0&&x!==xmax)continue;svg.append(node('text',{x:X(x),y:286,'text-anchor':'middle'},x))}
svg.append(node('text',{x:365,y:306,'text-anchor':'middle'},'Buget total de thread-uri GP'));
svg.append(node('line',{x1:X(d.cpus),x2:X(d.cpus),y1:20,y2:267,stroke:'var(--muted-foreground,#64748b)','stroke-dasharray':'4 4'}));svg.append(node('text',{x:Math.min(X(d.cpus)+5,610),y:18},d.cpus+' CPU logice'));
Object.entries(d.series).forEach(([variant,points],index)=>{svg.append(node('polyline',{points:points.map(p=>X(p.gp)+','+Y(p.speedup)).join(' '),fill:'none',stroke:colors[index],'stroke-width':2}));for(const point of points){const c=node('circle',{cx:X(point.gp),cy:Y(point.speedup),r:4,fill:colors[index],tabindex:0,role:'button','aria-label':variant+', GP '+point.gp+', speedup '+point.speedup.toFixed(2)});const describe=()=>{document.getElementById('details').textContent=variant+' · GP='+point.gp+' · '+(point.mean_seconds*1000).toFixed(3)+' ms · speedup '+point.speedup.toFixed(3)+'× · CV '+point.cv_percent.toFixed(1)+'%'};c.append(node('title',{},variant+' GP='+point.gp+': '+point.speedup.toFixed(3)+'×'));c.addEventListener('mouseenter',describe);c.addEventListener('focus',describe);c.addEventListener('click',describe);svg.append(c)}if(points.length){const best=points.reduce((a,b)=>a.mean_seconds<b.mean_seconds?a:b);const tr=document.createElement('tr');for(const value of [variant,best.gp,(best.mean_seconds*1000).toFixed(3),best.speedup.toFixed(3)+'×',best.efficiency.toFixed(3),best.cv_percent.toFixed(1)+'%']){const td=document.createElement('td');td.textContent=value;tr.append(td)}document.getElementById('winners').append(tr)}});document.getElementById('details').textContent='Selectează un punct pentru detalii.'}
for(const machine of Object.keys(data)){const b=document.createElement('button');b.textContent=machine;b.onclick=()=>show(machine);document.getElementById('controls').append(b)}show(Object.keys(data)[0]);</script></main></body></html>'''
    counts = f"10 variante + 2 bonus · {len(metadata)} calculatoare · {sum(row['status']=='OK' for row in raw):,} repetări verificate · {len(failures)} TIMEOUT/ERROR"
    document = document.replace("__DATA__", json.dumps(payload)).replace("__COUNTS__", html.escape(counts))
    (folder / "dashboard.html").write_text(document)


def generic_report(folder, figures, raw, metadata, summary, failures, generated):
    import os
    lines = ["# HW2 — Campanie personalizată", "",
             "Acest raport descrie grila din plan.json; nu este raportul profilului study. "
             "Profilul smoke validează colectarea și nu susține concluzii de performanță.", "",
             markdown_table(["Mașină", "Profil", "Serii aleatoare", "Repetări/pereche", "Configurații"],
                            [[machine, info["settings"]["profile"], info["settings"]["series"],
                              info["settings"]["repeats"], info["configurations"]] for machine, info in sorted(metadata.items())]), "",
             f"{len(raw)} înregistrări; {len(failures)} evenimente TIMEOUT/ERROR. "
             "Agregarea și excluderea seriilor incomplete urmează metodologia din EXPERIMENTS.md. "
             "summary.csv include mediile, deviațiile și speedup-ul față de o referință măsurată compatibilă.", ""]
    for name in generated:
        lines += [f"![{name}]({os.path.relpath(figures/(name+'.png'), folder)})", ""]
    (folder / "report.md").write_text("\n".join(lines))
    images = "".join(f'<img style="width:100%;height:auto" alt="{name}" src="data:image/png;base64,{base64.b64encode((figures/(name+".png")).read_bytes()).decode()}">'
                     for name in generated)
    (folder / "dashboard.html").write_text('<!doctype html><html><meta charset="utf-8"><title>HW2</title>'+images+'</html>')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "results" / "study")
    parser.add_argument("--figures", type=Path)
    args = parser.parse_args()
    folder = args.input.resolve()
    figures = (args.figures or ROOT / "figures" / folder.name).resolve()
    raw, metadata, summary, failures = aggregate(folder)
    csv_write(folder / "summary.csv", summary)
    csv_write(folder / "failures.csv", failures)
    generated = charts(summary, metadata, figures)
    report(folder, figures, raw, metadata, summary, failures, generated)
    print(f"{len(raw)} records, {len(summary)} summary groups, {len(failures)} timeout/error events; report: {folder / 'report.md'}")


if __name__ == "__main__":
    main()
