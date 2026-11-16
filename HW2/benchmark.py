#!/usr/bin/env python3
"""Reproducible OpenMP experiments. Collection uses only Python's standard library.

The study profile varies one factor at a time; full traverses a Cartesian grid.
Each invocation runs in isolation, flushes verified samples, and has an optional wall timeout.
"""
import argparse
import csv
from dataclasses import asdict, dataclass, replace
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import platform
import random
import re
import shlex
import shutil
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent
VARIANTS = ("seq", "parallel_i", "parallel_j", "parallel_k", "collapse_ij",
            "collapse_jk", "collapse_ijk", "nested_ij", "nested_jk", "nested_ik",
            "nested_ijk", "hybrid_ij_k", "hybrid_i_jk")
LOOPS = {"seq": (), "parallel_i": (0,), "parallel_j": (1,), "parallel_k": (2,),
         "collapse_ij": (0,), "collapse_jk": (1,), "collapse_ijk": (0,),
         "nested_ij": (0, 1), "nested_jk": (1, 2), "nested_ik": (0, 2),
         "nested_ijk": (0, 1, 2), "hybrid_ij_k": (0, 2), "hybrid_i_jk": (0, 1)}
SHAPES = ((10, 10, 10), (100, 100, 100), (1000, 1000, 1000),
          (1000, 10, 10), (1000, 10, 1000), (10, 1000, 10),
          (10, 1000, 1000), (10, 10, 1000))
SCHEDULES = ("static", "static:1", "static:8", "dynamic:1", "dynamic:8", "guided:1", "guided:8")
CSV_FIELDS = ("config_id", "campaign", "machine", "status", "variant", "n", "m", "r",
              "layout", "dataset", "seed", "repeat", "gp", "threads_i", "threads_j", "threads_k",
              "schedule_i", "chunk_i", "schedule_j", "chunk_j", "schedule_k", "chunk_k",
              "seconds", "reference_seconds", "minor_faults", "major_faults", "verified", "checksum",
              "team_min", "team_max", "levels", "thread_limit", "wall_seconds", "timeout_seconds", "error")


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


@dataclass(frozen=True)
class Config:
    campaign: str
    n: int
    m: int
    r: int
    variant: str
    budget: int = 4
    schedule: str = "static"
    layout: str = "row"
    dataset: str = "random"
    seed: int = 1001
    threads: tuple = ()
    overrides: tuple = ()

    @property
    def id(self):
        return digest(asdict(self))[:20]

    def command(self, executable, repeats, warmups):
        command = [str(executable), "--n", str(self.n), "--m", str(self.m), "--r", str(self.r),
                   "--variant", self.variant, "--layout", self.layout, "--dataset", self.dataset,
                   "--seed", str(self.seed), "--schedule", self.schedule,
                   "--repeats", str(repeats), "--warmups", str(warmups)]
        if self.threads:
            command += ["--threads", ",".join(map(str, self.threads))]
        else:
            command += ["--budget", str(self.budget)]
        for loop, schedule in self.overrides:
            command += ["--schedule-" + loop, schedule]
        return command


def datasets(series):
    return [("random", 1001 + i) for i in range(series)] + [("zeros", 1001), ("max", 1001)]


def build_plan(args, logical_cpus):
    maximum = args.max_threads or max(8, 2 * logical_cpus)
    if maximum > 256:
        raise ValueError("maximum total thread budget supported by the executable is 256")
    gp = min(4, logical_cpus)
    plan = []

    def add(campaign, shapes, variants, budgets, schedules=("static",), layouts=("row",), inputs=None):
        for shape, variant, budget, schedule, layout, (dataset, seed) in itertools.product(
                shapes, variants, budgets, schedules, layouts, inputs or datasets(args.series)):
            plan.append(Config(campaign, *shape, variant, budget, schedule, layout, dataset, seed))

    if args.profile == "smoke":
        add("smoke", [(3, 7, 5), (10, 10, 10)], VARIANTS, [4],
            ("static", "dynamic:2", "guided:2"), ("row", "transposed"), [("random", 1001)])
    elif args.profile == "full":
        shapes = [tuple(map(int, shape.split("x"))) for shape in args.shapes]
        if any(len(shape) != 3 or min(shape) < 1 for shape in shapes):
            raise ValueError("shapes must be positive NxMxR triples")
        add("full", shapes, VARIANTS[1:], range(1, maximum+1), args.schedules, args.layouts)
    else:
        add("dimensions", SHAPES, VARIANTS[1:], [gp])
        add("threads", [(100, 100, 100)], VARIANTS[1:], range(1, maximum+1),
            inputs=[("random", 1001+i) for i in range(args.series)])
        add("scaling", [(300, 300, 300)], ["parallel_i", "collapse_ij"], range(1, maximum+1),
            inputs=[("random", 1001+i) for i in range(args.series)])
        add("schedules", [(100, 100, 100)], VARIANTS[1:], [gp], SCHEDULES)
        add("schedules_large", [(300, 300, 300)], ["parallel_i", "collapse_ij"], [gp], SCHEDULES)
        add("layout", [(100, 100, 100)], VARIANTS[1:], [gp], layouts=("row", "transposed"),
            inputs=[("random", 1001+i) for i in range(args.series)])
        add("layout_large", [(1000, 1000, 1000)], ["parallel_i", "collapse_ij"], [gp],
            layouts=("row", "transposed"), inputs=[("random", 1001)])
        # Hold the total GP at 8 while moving parallelism among nested levels.
        for variant in VARIANTS[7:]:
            loops = LOOPS[variant]
            splits = [(8,)+(1,)*(len(loops)-1), (1,)*(len(loops)-1)+(8,),
                      (4, 2) if len(loops) == 2 else (2, 2, 2)]
            for split, mixed, (dataset, seed) in itertools.product(
                    splits, (False, True), [("random", 1001+i) for i in range(args.series)]):
                threads = [1, 1, 1]
                for loop, size in zip(loops, split):
                    threads[loop] = size
                overrides = (("i", "dynamic:1"), ("j", "guided:2"), ("k", "static:2")) if mixed else ()
                plan.append(Config("allocation", 10, 10, 10, variant, budget=8,
                                   dataset=dataset, seed=seed, threads=tuple(threads), overrides=overrides))
    # Every campaign/shape/input/layout has its own measured sequential baseline.
    baselines = {replace(config, variant="seq", budget=1, schedule="static", threads=(), overrides=())
                 for config in plan}
    plan = list(set(plan) | baselines)
    # Stable shuffle avoids making a variant always follow the same predecessor.
    plan.sort(key=lambda config: config.id)
    random.Random(2026).shuffle(plan)
    return plan


def read_text(path):
    try:
        return Path(path).read_text().strip()
    except OSError:
        return None


def capture(command):
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=10)
        return result.stdout.strip() if result.returncode == 0 else result.stderr.strip()
    except (OSError, subprocess.TimeoutExpired) as error:
        return str(error)


def metadata(args, plan, environment):
    affinity = sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else list(range(os.cpu_count() or 1))
    return {
        "created_utc": datetime.now(timezone.utc).isoformat(), "hostname": socket.gethostname(),
        "platform": platform.platform(), "python": sys.version, "os_release": read_text("/etc/os-release"),
        "logical_cpus": os.cpu_count(), "affinity_cpus": affinity,
        "lscpu": capture(["lscpu", "-J"]), "topology": capture(["lscpu", "-p=CPU,CORE,SOCKET,ONLINE"]),
        "meminfo": read_text("/proc/meminfo"), "load_start": os.getloadavg(),
        "cpu_governors": sorted({read_text(p) for p in Path("/sys/devices/system/cpu").glob("cpu[0-9]*/cpufreq/scaling_governor")}),
        "virtualization": capture(["systemd-detect-virt"]),
        "cgroup_cpu_max": read_text("/sys/fs/cgroup/cpu.max"),
        "compiler": capture(["gcc", "--version"]), "compile_command": "gcc -O3 -std=c11 -Wall -Wextra -Wpedantic -fopenmp matmul.c -o matmul",
        "openmp_environment": {key: value for key, value in environment.items() if key.startswith(("OMP_", "GOMP_"))},
        "source_sha256": hashlib.sha256((ROOT / "matmul.c").read_bytes()).hexdigest(),
        "benchmark_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "settings": {key: getattr(args, key) for key in ("profile", "series", "repeats", "warmups", "timeout", "large_timeout", "max_threads")},
        "plan_sha256": digest([asdict(config) for config in plan]), "configurations": len(plan),
    }


def run_configuration(config, args, environment):
    timeout = args.large_timeout if (config.variant in ("seq", "parallel_i", "parallel_j", "collapse_ij")
                                    and config.n * config.m * config.r >= 100_000_000) else args.timeout
    start = time.monotonic()
    try:
        process = subprocess.run(config.command(ROOT / "matmul", args.repeats, args.warmups),
                                 capture_output=True, text=True, env=environment, timeout=timeout or None)
        stdout, error = process.stdout, process.stderr[-4000:]
        status = "OK" if process.returncode == 0 else "ERROR"
    except subprocess.TimeoutExpired as exception:
        stdout = exception.stdout or b""
        stdout = stdout.decode() if isinstance(stdout, bytes) else stdout
        error, status = f"process wall time exceeded {timeout:g} seconds", "TIMEOUT"
    records = []
    for line in stdout.splitlines():
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            if status != "TIMEOUT":
                raise
            continue  # a killed process may have written one incomplete final line
        if record.get("verified") is not True:
            raise RuntimeError(f"unverified sample from {config.id}")
        record.update(config_id=config.id, campaign=config.campaign, machine=socket.gethostname(), status="OK")
        records.append(record)
    wall = time.monotonic() - start
    if status == "OK" and len(records) != args.repeats:
        raise RuntimeError(f"{config.id}: expected {args.repeats} samples, received {len(records)}")
    if status != "OK":
        record = {key: value for key, value in asdict(config).items() if key in CSV_FIELDS}
        record.update(config_id=config.id, machine=socket.gethostname(), status=status, repeat=-1,
                      gp=config.budget if not config.threads else None, error=error)
        records.append(record)
    for record in records:
        record.update(wall_seconds=wall, timeout_seconds=timeout)
    return records


def collect(args):
    subprocess.run(["make", "-C", str(ROOT)], check=True)
    logical = len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else os.cpu_count() or 1
    plan = build_plan(args, logical)
    if args.campaigns:
        plan = [config for config in plan if config.campaign in args.campaigns]
    environment = dict(os.environ, OMP_WAIT_POLICY="PASSIVE", OMP_DYNAMIC="FALSE", OMP_PROC_BIND="FALSE")
    info = metadata(args, plan, environment)
    folder = Path(args.output).resolve() / socket.gethostname()
    folder.mkdir(parents=True, exist_ok=True)
    metadata_path, raw_path = folder / "metadata.json", folder / "runs.jsonl"
    if metadata_path.exists():
        previous = json.loads(metadata_path.read_text())
        for key in ("source_sha256", "benchmark_sha256", "plan_sha256", "settings", "openmp_environment"):
            if previous[key] != info[key]:
                raise RuntimeError(f"{folder}: {key} changed; use a new output directory")
        info = previous
    else:
        metadata_path.write_text(json.dumps(info, indent=2) + "\n")
        (folder / "plan.json").write_text(json.dumps([asdict(config) for config in plan], indent=2) + "\n")
    rows, finished = [], set()
    if raw_path.exists():
        for line in raw_path.read_text().splitlines():
            row = json.loads(line)
            rows.append(row)
        # Resume only configurations with a terminal event or all repetitions.
        for config in plan:
            samples = [row for row in rows if row["config_id"] == config.id]
            if len([row for row in samples if row["status"] == "OK"]) == args.repeats or any(row["status"] != "OK" for row in samples):
                finished.add(config.id)
        # Drop samples from an externally interrupted invocation before rerunning it.
        rows = [row for row in rows if row["config_id"] in finished]
        raw_path.write_text("".join(json.dumps(row) + "\n" for row in rows))
    errors = []
    with raw_path.open("a", buffering=1) as raw:
        for index, config in enumerate(plan, 1):
            if config.id in finished:
                continue
            records = run_configuration(config, args, environment)
            for record in records:
                raw.write(json.dumps(record) + "\n")
                rows.append(record)
                if record["status"] == "ERROR":
                    errors.append(record)
            if index % 50 == 0 or any(record["status"] != "OK" for record in records):
                print(f"{socket.gethostname()}: {index}/{len(plan)} {config.campaign} {config.variant} "
                      f"{config.n}x{config.m}x{config.r} GP={config.budget} {records[-1]['status']}", flush=True)
            if errors:
                break  # a wrong result is a failure, not a performance measurement
    with (folder / "runs.csv").open("w", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: canonical(value) if isinstance(value, (list, dict)) else value
                             for key, value in row.items()})
    info.update(finished_utc=datetime.now(timezone.utc).isoformat(), load_end=os.getloadavg(),
                completed_configurations=len({row["config_id"] for row in rows}),
                successful_samples=sum(row["status"] == "OK" for row in rows),
                timeouts=sum(row["status"] == "TIMEOUT" for row in rows))
    metadata_path.write_text(json.dumps(info, indent=2) + "\n")
    if errors:
        raise RuntimeError(f"calculation failed: {errors[0]}")
    return folder


def collect_remote(host, args):
    if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.@-]*", host):
        raise ValueError("invalid SSH host name")
    ssh = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", host]
    scratch = subprocess.check_output(ssh + ["mktemp -d /tmp/sod-hw2.XXXXXXXX"], text=True).strip()
    if not re.fullmatch(r"/tmp/sod-hw2\.[A-Za-z0-9]+", scratch):
        raise RuntimeError("unexpected remote temporary directory")
    try:
        subprocess.run(["scp", "-q", str(ROOT / "matmul.c"), str(ROOT / "Makefile"),
                        str(ROOT / "benchmark.py"), f"{host}:{scratch}/"], check=True)
        command = ["python3", f"{scratch}/benchmark.py", "--collect-only", "--output", f"{scratch}/results",
                   "--profile", args.profile, "--series", str(args.series), "--repeats", str(args.repeats),
                   "--warmups", str(args.warmups), "--timeout", str(args.timeout),
                   "--large-timeout", str(args.large_timeout)]
        if args.max_threads:
            command += ["--max-threads", str(args.max_threads)]
        for flag in ("shapes", "schedules", "layouts", "campaigns"):
            if getattr(args, flag):
                command += ["--"+flag, *getattr(args, flag)]
        subprocess.run(ssh + [shlex.join(command)], check=True)
        destination = Path(args.output).resolve()
        destination.mkdir(parents=True, exist_ok=True)
        subprocess.run(["scp", "-q", "-r", f"{host}:{scratch}/results/.", str(destination)], check=True)
    except BaseException:
        print(f"Remote results retained at {host}:{scratch}", file=sys.stderr)
        raise
    else:
        # Only remove the exact directory created by this invocation.
        subprocess.run(ssh + [shlex.join(["python3", "-c", "import shutil,sys; shutil.rmtree(sys.argv[1])", scratch])], check=True)


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--profile", choices=("smoke", "study", "full"), default="study")
    result.add_argument("--hosts", nargs="+", default=["local"], help="sequential collection on local and/or SSH hosts")
    result.add_argument("--output", type=Path, default=ROOT / "results" / "study")
    result.add_argument("--series", type=int, default=5, help="independent random matrix pairs")
    result.add_argument("--repeats", type=int, default=5, help="timings per identical pair and configuration")
    result.add_argument("--warmups", type=int, default=1)
    result.add_argument("--timeout", type=float, default=600.0, help="whole-invocation wall limit in seconds; 0 disables it (default: 600)")
    result.add_argument("--large-timeout", type=float, default=600.0, help="wall limit in seconds for large sequential/outer-loop cases; 0 disables it (default: 600)")
    result.add_argument("--max-threads", type=int, help="default: max(8, 2*available logical CPUs)")
    result.add_argument("--shapes", nargs="+", default=["10x10x10", "100x100x100", "1000x1000x1000",
                                                       "1000x10x10", "10x1000x10", "10x1000x1000"])
    result.add_argument("--schedules", nargs="+", default=list(SCHEDULES))
    result.add_argument("--layouts", nargs="+", choices=("row", "transposed"), default=["row", "transposed"])
    result.add_argument("--campaigns", nargs="+", help="collect selected campaigns only, into a new output directory")
    result.add_argument("--collect-only", action="store_true", help="do not generate charts (no external Python dependencies)")
    result.add_argument("--report-only", action="store_true")
    return result


def main():
    args = parser().parse_args()
    if min(args.series, args.repeats) <= 0 or args.warmups < 0:
        raise SystemExit("series and repeats must be positive; warmups must be nonnegative")
    if any(not math.isfinite(value) or value < 0 for value in (args.timeout, args.large_timeout)):
        raise SystemExit("timeouts must be finite and nonnegative; 0 disables the limit")
    if args.max_threads is not None and args.max_threads <= 0:
        raise SystemExit("max-threads must be positive")
    if not args.report_only:
        for host in args.hosts:
            collect(args) if host == "local" else collect_remote(host, args)
    if not args.collect_only:
        subprocess.run([sys.executable, str(ROOT / "analyze.py"), "--input", str(args.output)], check=True)


if __name__ == "__main__":
    main()
