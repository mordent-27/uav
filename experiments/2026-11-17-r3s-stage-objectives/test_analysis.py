import unittest
from analyze import hours, change, paired


class AnalysisTests(unittest.TestCase):
    def test_stale_metrics_are_ignored(self):
        self.assertEqual(hours(dict(solution=dict(s=[.2, .3]), metrics=dict(objective=999))), .5)

    def test_units_and_material_change(self):
        self.assertEqual(change(1, 1 - 2 / 3600), 'shorter')
        self.assertEqual(change(1, 1 + 2 / 3600), 'longer')
        self.assertEqual(change(1, 1 + .5 / 3600), 'within_one_second')

    def test_missing_baseline_does_not_become_improvement(self):
        result = paired([dict(baseline_h=None, returned_h=.5, change=None),
                         dict(baseline_h=1, returned_h=.5, change='shorter'),
                         dict(baseline_h=1, returned_h=None, change=None)])
        self.assertEqual(result['n'], 1)
        self.assertEqual(result['delta_seconds']['median'], -1800)
        self.assertEqual(result['relative_reduction']['median'], .5)

    def test_nonfinite_time_rejected(self):
        with self.assertRaises(AssertionError):
            hours(dict(solution=dict(s=[float('nan')])))


if __name__ == '__main__':
    unittest.main()
