"""Validate the new choice instrumentation against the unchanged Rust evaluator."""
import ctypes as ct
import unittest
import numpy as np
import trace as tr


class TraceTests(unittest.TestCase):
    def test_softmin_values_and_weights_from_rust(self):
        lib = ct.CDLL('/tmp/uav-library-trace-helpers.so')
        lib.trace_min.argtypes = [tr.Model.ptr(np.zeros(1)).__class__, ct.c_size_t, ct.c_double,
                                 tr.Model.ptr(np.zeros(1)).__class__]
        lib.trace_min.restype = ct.c_double
        lib.trace_psi.argtypes = [ct.c_double, ct.c_double, tr.Model.ptr(np.zeros(1)).__class__]
        for y in [-2., -.001, -.0005, 0., .0005, .001, 3.]:
            values = np.empty(2)
            lib.trace_psi(y, .001, tr.Model.ptr(values))
            self.assertAlmostEqual(float(tr.psi(y)), values[0], places=14)
        rng = np.random.default_rng(42)
        for p in [2., 6., 12.]:
            for z in [np.array([.0005, .01, 1., 5., 10.]), rng.uniform(.0005, 10., 37)]:
                derivatives = np.empty(len(z))
                phi = lib.trace_min(tr.Model.ptr(z), len(z), p, tr.Model.ptr(derivatives))
                item = tr.softmin(z, p)
                self.assertAlmostEqual(phi, item['phi'], places=13)
                np.testing.assert_allclose(derivatives, item['dphi_dz'], rtol=2e-13, atol=1e-16)

    def test_described_choices_match_all_rust_equalities(self):
        for representation in ['original', 'normalized']:
            model = tr.Model(0, 0, tr.LIBRARIES[representation])
            template = model.solution(model.y)
            y = model.y + np.random.default_rng(9).uniform(-.02, .02, model.n)
            for stage in [0, 6, 12]:
                eps, p = max(.0005, .2*.6**stage), min(12., 2.*1.2**stage)
                model.stage(eps, p)
                model.eval(y, np.zeros(model.me), np.zeros(model.mi), 0.)
                description = tr.describe(model, y, template, eps, p)
                values = np.array([r['phi'] - eps for r in description['tasks'] + description['modes']])
                np.testing.assert_allclose(values, model.h[model.stamps-1:], atol=5e-14, rtol=1e-12)
                for row in description['modes'] + description['tasks']:
                    self.assertAlmostEqual(sum(row['derivative_share']), 1., places=13)
            model.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
