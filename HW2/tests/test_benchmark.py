import argparse
from dataclasses import asdict
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import benchmark as b


class PlanTests(unittest.TestCase):
    def args(self, *options):
        return b.parser().parse_args(options)

    def test_study_covers_required_axes_without_duplicate_configs(self):
        args = self.args()
        plan = b.build_plan(args, 4)
        self.assertEqual(len(plan), len({config.id for config in plan}))
        self.assertEqual(set(b.VARIANTS), {config.variant for config in plan})
        self.assertEqual(set(range(1, 9)), {config.budget for config in plan if config.campaign == "threads"})
        dimensions = [config for config in plan if config.campaign == "dimensions"]
        self.assertEqual(set(b.SHAPES), {(c.n, c.m, c.r) for c in dimensions})
        self.assertEqual({1001, 1002, 1003, 1004, 1005}, {c.seed for c in dimensions if c.dataset == "random"})
        self.assertEqual({"random", "zeros", "max"}, {c.dataset for c in dimensions})
        self.assertEqual(set(b.SCHEDULES), {c.schedule for c in plan if c.campaign == "schedules"})
        for config in plan:
            if config.campaign == "allocation" and config.variant != "seq":
                product = 1
                for loop in b.LOOPS[config.variant]:
                    product *= config.threads[loop]
                self.assertEqual(product, 8)

    def test_full_profile_is_cartesian_and_has_measured_baselines(self):
        args = self.args("--profile", "full", "--max-threads", "2", "--series", "1",
                         "--shapes", "2x3x4", "--schedules", "static", "guided:2", "--layouts", "row")
        plan = b.build_plan(args, 4)
        self.assertEqual(len(plan), 12*2*2*3 + 3)
        for config in plan:
            baseline = b.replace(config, variant="seq", budget=1, schedule="static", threads=(), overrides=())
            self.assertIn(baseline, plan)

    def test_timeout_is_distinct_from_a_timing(self):
        args = self.args("--timeout", "0.000001", "--large-timeout", "0.000001")
        config = b.Config("test", 1000, 1000, 1000, "parallel_k")
        records = b.run_configuration(config, args, dict(b.os.environ, OMP_WAIT_POLICY="PASSIVE"))
        self.assertEqual(records[-1]["status"], "TIMEOUT")
        self.assertNotIn("seconds", records[-1])


@unittest.skipUnless(importlib.util.find_spec("matplotlib"), "analysis tests require Matplotlib")
class AggregationTests(unittest.TestCase):
    def test_partial_seed_is_excluded_and_seed_means_have_equal_weight(self):
        import analyze
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            machine = folder / "test-machine"
            machine.mkdir()
            info = {"hostname": "test-machine", "settings": {"repeats": 2}}
            (machine / "metadata.json").write_text(json.dumps(info))
            records = []
            base = dict(machine="test-machine", campaign="test", n=1,m=1,r=1,
                        layout="row",dataset="random",gp=1,threads_i=1,threads_j=1,threads_k=1,
                        schedule_i="static",chunk_i=0,schedule_j="static",chunk_j=0,schedule_k="static",chunk_k=0,
                        status="OK", minor_faults=0,major_faults=0)
            for variant, seeds in (("seq", [(2, 4), (4, 6)]), ("parallel_i", [(1, 2), (2,)])):
                for seed, times in enumerate(seeds, 1):
                    config_id = f"{variant}-{seed}"
                    for repeat, seconds in enumerate(times):
                        records.append(dict(base, variant=variant,config_id=config_id,seed=seed,repeat=repeat,seconds=seconds))
                    if len(times) != 2:
                        records.append(dict(base, variant=variant,config_id=config_id,seed=seed,repeat=-1,status="TIMEOUT"))
            (machine / "runs.jsonl").write_text("\n".join(json.dumps(row) for row in records))
            _, _, summary, failures = analyze.aggregate(folder)
            seq = next(row for row in summary if row["variant"] == "seq")
            parallel = next(row for row in summary if row["variant"] == "parallel_i")
            self.assertEqual(seq["mean_seconds"], 4)
            self.assertEqual(parallel["mean_seconds"], 1.5)
            self.assertEqual(parallel["samples"], 2)
            self.assertEqual(parallel["status"], "PARTIAL")
            self.assertNotIn("speedup", parallel)
            self.assertEqual(len(failures), 1)

    def test_python_budget_allocator_agrees_with_c(self):
        import analyze
        import subprocess
        for variant in b.VARIANTS:
            for budget in (1, 4, 7, 8, 12, 32):
                output = subprocess.check_output(
                    [str(ROOT/"matmul"), "--variant", variant, "--budget", str(budget),
                     "--n", "1", "--m", "1", "--r", "1", "--repeats", "1", "--warmups", "0"],
                    text=True, env=dict(b.os.environ, OMP_WAIT_POLICY="PASSIVE"))
                result = json.loads(output)
                self.assertEqual(analyze.balanced_threads(variant, budget),
                                 tuple(result["threads_"+loop] for loop in "ijk"))


if __name__ == "__main__":
    unittest.main()
