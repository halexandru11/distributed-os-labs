"""Independent Python big-integer oracle, including unsigned overflow cases."""
import json
import os
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
EXE = Path(os.environ.get("MATMUL_EXE", ROOT / "matmul"))
MASK = (1 << 64) - 1
VARIANTS = subprocess.check_output([str(EXE), "--list"], text=True).splitlines()


def run(*args, env=None):
    environment = dict(os.environ, OMP_WAIT_POLICY="PASSIVE", OMP_THREAD_LIMIT="64")
    environment.update(env or {})
    result = subprocess.run(
        [str(EXE), "--n", "3", "--m", "7", "--r", "5", "--threads", "2,2,2",
         "--repeats", "2", "--warmups", "1", "--dump", *args],
        check=True, text=True, capture_output=True, env=environment, timeout=20)
    return [json.loads(line) for line in result.stdout.splitlines()]


class MatrixTests(unittest.TestCase):
    def assert_oracle(self, record):
        n, m, r = (record[key] for key in ("n", "m", "r"))
        a, b = record["a"], record["b"]
        expected = [sum(a[i*m+k] * b[k*r+j] for k in range(m)) & MASK
                    for i in range(n) for j in range(r)]
        self.assertEqual(expected, record["c"])
        self.assertTrue(record["verified"])
        self.assertGreater(record["seconds"], 0)

    def test_every_variant_layout_schedule_and_input(self):
        for variant in VARIANTS:
            for layout in ("row", "transposed"):
                for schedule in ("static", "static:2", "dynamic:1", "guided:2"):
                    for dataset in ("random", "random_full", "zeros", "ones", "max"):
                        with self.subTest(variant=variant, layout=layout,
                                          schedule=schedule, dataset=dataset):
                            for record in run("--variant", variant, "--layout", layout,
                                              "--schedule", schedule, "--dataset", dataset):
                                self.assert_oracle(record)

    def test_one_element_and_more_threads_than_work(self):
        for variant in VARIANTS:
            for record in run("--variant", variant, "--n", "1", "--m", "1", "--r", "1"):
                self.assert_oracle(record)

    def test_independent_schedules_and_team_sizes(self):
        for variant in ("nested_ij", "nested_ik", "nested_jk", "nested_ijk",
                        "hybrid_ij_k", "hybrid_i_jk"):
            for record in run("--variant", variant, "--threads", "3,2,2",
                              "--schedule-i", "dynamic:2", "--schedule-j", "guided:3",
                              "--schedule-k", "static:4"):
                self.assert_oracle(record)
                self.assertEqual(record["schedule_i"], "dynamic")
                self.assertEqual(record["chunk_j"], 3)
                self.assertEqual(record["chunk_k"], 4)

    def test_reproducible_inputs_across_layouts_and_distinct_seeds(self):
        row = run("--seed", "42")[0]
        transposed = run("--seed", "42", "--layout", "transposed")[0]
        other = run("--seed", "43")[0]
        for key in ("a", "b", "c", "checksum"):
            self.assertEqual(row[key], transposed[key])
        self.assertNotEqual(row["a"], other["a"])

    def test_runtime_team_limit_is_visible(self):
        record = run("--variant", "nested_ijk", env={"OMP_THREAD_LIMIT": "1"})[0]
        self.assertEqual(record["team_max"], [1, 1, 1])
        self.assertEqual(record["thread_limit"], 1)
        self.assert_oracle(record)

    def test_budget_is_total_product(self):
        for variant in VARIANTS:
            for budget in (1, 4, 7, 8, 12):
                result = subprocess.run(
                    [str(EXE), "--variant", variant, "--budget", str(budget),
                     "--n", "1", "--m", "2", "--r", "1", "--repeats", "1", "--warmups", "0"],
                    text=True, capture_output=True, check=True, timeout=10,
                    env=dict(os.environ, OMP_WAIT_POLICY="PASSIVE"))
                record = json.loads(result.stdout)
                self.assertEqual(record["gp"], 1 if variant == "seq" else budget)

    def test_invalid_arguments_and_memory_bounds(self):
        cases = [("--n", "0"), ("--n", "-1"), ("--variant", "bad"),
                 ("--schedule", "dynamic:0"), ("--threads", "2,,2"),
                 ("--threads", "1,2"), ("--threads", "1,2,3", "--budget", "4"),
                 ("--layout", "bad"), ("--dataset", "bad"),
                 ("--n", "2147483647", "--m", "2147483647", "--r", "2147483647"),
                 ("--n", "100000", "--m", "100000"), ("--seed", "18446744073709551616"),
                 ("--variant",), ("--bogus", "1")]
        for args in cases:
            with self.subTest(args=args):
                result = subprocess.run([str(EXE), *args], capture_output=True, timeout=5)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(b"Error:", result.stderr)


if __name__ == "__main__":
    unittest.main()
