import unittest
from common import revisits, choose

class T(unittest.TestCase):
    def test_adjacent_charging_is_not_revisit(self):
        self.assertEqual(revisits([-1, 0, 0, -1, 1]), [])
    def test_gap_is_revisit(self):
        self.assertEqual(revisits([0, -1, 0, 1, 1, 2, 1]), [0, 1])
    def test_other_region_between_is_revisit(self):
        self.assertEqual(revisits([0, 1, 0]), [0])
    def test_choose_small(self):
        self.assertEqual(choose([(2., 'b'), (1., 'a')]), ['a', 'b'])
    def test_choose_quantiles(self):
        rows = [(float(i), f'c{i:02d}') for i in range(11)]
        self.assertEqual(choose(rows), ['c00', 'c02', 'c04', 'c06', 'c08', 'c10'])

if __name__ == '__main__':
    unittest.main()
