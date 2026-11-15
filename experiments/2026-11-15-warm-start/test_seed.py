"""Verify physical seed and its full-precision encoding before the controls."""
import unittest
import numpy as np
import controls as c


class SeedTests(unittest.TestCase):
    def test_good_seed_roundtrip_and_original_feasibility(self):
        models = [c.tr.Model(0, 0, c.tr.LIBRARIES[k]) for k in ['normalized', 'original']]
        source, y = c.load_seed(models[0])
        other, second = c.load_seed(models[1])
        np.testing.assert_array_equal(y, second)
        self.assertEqual(source, other)
        decoded = c.tr.decode(models[0], y, source)
        self.assertEqual(decoded['r'][0], source['instance']['r0'])
        self.assertEqual(decoded['r'][-1], source['instance']['rf'])
        for task, stamp in zip(source['instance']['tasks'], source['task_stamp']):
            np.testing.assert_array_equal(decoded['r'][stamp], task)
        self.assertGreater(min(c.tr.diag.replay(source)), .02)
        for m in models:
            for eps, p in [(.2, 2.), (.0005, 12.)]:
                m.stage(eps, p)
                f, gradient = m.eval(y, np.zeros(m.me), np.zeros(m.mi), 1e4)
                self.assertTrue(np.isfinite(f) and np.isfinite(gradient).all())
                selection = c.tr.describe(m, y, source, eps, p)
                actual = [r['phi']-eps for r in selection['tasks']+selection['modes']]
                np.testing.assert_allclose(m.h[m.stamps-1:], actual, rtol=1e-12, atol=1e-14)
            m.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
