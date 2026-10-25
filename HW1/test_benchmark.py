import tempfile
import unittest
from pathlib import Path

import benchmark as b


class BenchmarkTests(unittest.TestCase):
    def test_matrix_has_same_coverage_for_every_operation(self):
        jobs = b.build_jobs()
        self.assertEqual(len(jobs), 136)
        self.assertEqual(len(jobs), len(set(jobs)))
        for label, _, _ in b.RESOLUTIONS:
            for op in b.OPS:
                self.assertIn((label, op, 'seq', 1), jobs)
                counts = b.NP_LIST if label == '8MP' else [5]
                for mode in b.MODES:
                    self.assertEqual(
                        {n for res, operation, strategy, n in jobs
                         if (res, operation, strategy) == (label, op, mode)}, set(counts))

    def test_summary_uses_measured_mpi_time_and_sample_deviation(self):
        run = dict(op='blur', mode='static_2d', np=5, width=9, height=7,
                   total=0.1, comm=0.08, comp=0.07, pack=0.01)
        runs = [dict(run, total=t) for t in [0.1, 0.2, 0.3]]
        result = b.summarize_runs('test', runs, baseline=0.4)
        self.assertAlmostEqual(result['avg_comm_s'], 0.08)
        self.assertAlmostEqual(result['std_total_s'], 0.1)
        self.assertAlmostEqual(result['speedup'], 2)
        self.assertAlmostEqual(result['efficiency'], 0.5)
        self.assertEqual(result['repetitions'], 3)

    def test_pixel_check_reads_every_pixel_and_handles_rotated_dimensions(self):
        with tempfile.TemporaryDirectory() as d:
            expected = Path(d) / 'expected.ppm'
            actual = Path(d) / 'actual.ppm'
            pixels = bytearray(9 * 7 * 3)
            expected.write_bytes(b'P6\n9 7\n255\n' + pixels)
            actual.write_bytes(expected.read_bytes())
            self.assertEqual(b.compare_pixels(expected, actual), (0, 0))
            pixels[-1] = 255
            actual.write_bytes(b'P6\n9 7\n255\n' + pixels)
            self.assertEqual(b.compare_pixels(expected, actual), (1, 255))
            actual.write_bytes(b'P6\n7 9\n255\n' + pixels)
            with self.assertRaisesRegex(RuntimeError, 'Dimensiuni diferite'):
                b.compare_pixels(expected, actual)

    def test_tables_keep_units_variation_and_highlight_minimum(self):
        row = b.summarize_runs('8MP', [dict(op='grayscale', mode='seq', np=1,
            width=9, height=7, total=t, comm=0, pack=0, comp=t) for t in [0.1, 0.2]], 0.15)
        other = dict(row)
        other.update(mode='static_1d', np=5, avg_total_s=0.3)
        text = b.render_result_tables([row, other], '8MP')
        self.assertIn('Total (ms)', text)
        self.assertIn('**150.0 ± 70.7**', text)
        self.assertEqual(text.count('**'), 2)
        self.assertNotIn('$', text)


if __name__ == '__main__':
    unittest.main()
