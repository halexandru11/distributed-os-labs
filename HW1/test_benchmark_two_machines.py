import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import benchmark_two_machines_small as benchmark


class BenchmarkPathsTest(unittest.TestCase):
    def test_collect_creates_missing_output_parents_before_compiling(self):
        class StopBeforeCompilation(Exception):
            pass

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'benchmark_two_machines' / '1.5MP'
            with patch.object(benchmark, 'OUT', output), patch.object(
                benchmark.subprocess, 'run', side_effect=StopBeforeCompilation
            ) as compile_command:
                with self.assertRaises(StopBeforeCompilation):
                    benchmark.collect()
                self.assertTrue(output.is_dir())
                self.assertIn(str(output / 'mpi_image_proc'), compile_command.call_args.args[0])

    def test_input_paths_match_declared_dimensions(self):
        for resolution in benchmark.RESOLUTIONS:
            with self.subTest(resolution=resolution[0]), patch.object(
                benchmark, 'RESOLUTION', resolution
            ):
                path = benchmark.image_path()
                self.assertTrue(path.is_file(), str(path))
                _, width, height = benchmark.b.read_ppm_for_plot(path, max_dim=1)
                self.assertEqual((width, height), resolution[1:])
                command = benchmark.command(1, 0, 'static_1d', 'blur', 'NONE')
                self.assertIn(str(path), command)


if __name__ == '__main__':
    unittest.main()
