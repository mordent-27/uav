import unittest
from common import targets, classify

GOOD = dict(original_residual=0., min_energy=.1, max_energy=1., accepted=True)

class T(unittest.TestCase):
    def test_targets(self):
        rows = targets()
        self.assertEqual(len(rows), 590)
        self.assertEqual(sum(r['jump'] for r in rows), 354)
        self.assertEqual(sum(r['route'] == 'G' for r in rows), 60)
    def test_success(self):
        self.assertEqual(classify('R', True, 0., GOOD, (0, 1)), 'success')
    def test_correction_is_not_success(self):
        self.assertEqual(classify('R', True, 1e-6, GOOD, (0, 1)), 'corrected_feasible')
        self.assertEqual(classify('R', False, 0., GOOD, (0, 1)), 'corrected_feasible')
    def test_rejections(self):
        self.assertEqual(classify('R', True, 0., dict(GOOD, accepted=False), (0, 1)), 'rejected')
        self.assertEqual(classify('base', True, 0., dict(GOOD, original_residual=1e-8), (0, 1)), 'rejected')
        self.assertEqual(classify('base', True, 0., dict(GOOD, min_energy=-1e-9), (0, 1)), 'rejected')
    def test_base_ignores_carrier(self):
        self.assertEqual(classify('base', True, 0., dict(GOOD, accepted=False), (0, 1)), 'success')

if __name__ == '__main__':
    unittest.main()
