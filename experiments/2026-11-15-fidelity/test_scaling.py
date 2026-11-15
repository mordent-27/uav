"""Check actual row/variable transforms, AL gradients and common KKT before solving."""
import unittest
import numpy as np
import run as r


class ScalingTests(unittest.TestCase):
    def setUp(self):
        self.models = [r.Variant(k) for k in ['N', 'R', 'Q', 'U']]

    def tearDown(self):
        for model in self.models:
            model.close()

    def test_same_physical_initial_point_and_positive_row_rescaling(self):
        base = self.models[0]
        x = base.x0 + np.random.default_rng(4).uniform(-1e-4, 1e-4, base.n)
        ref = base.reference
        ref.stage(.2, 2.)
        ref.eval(np.ascontiguousarray(x/ref.scale), np.zeros(ref.me), np.zeros(ref.mi), 0.)
        h, g = ref.h.copy(), ref.g.copy()
        tr = r.tr.decode(base, np.ascontiguousarray(x/base.scale), base.source)
        delta = np.diff(np.array(tr['r']), axis=0)
        denominator = np.sqrt(np.sum(delta**2, axis=1)+.001**2)+np.sqrt((36*np.array(tr['s']))**2+.001**2)
        for model in self.models:
            np.testing.assert_array_equal(model.x0, base.x0)
            np.testing.assert_allclose(model.y0*model.scale, base.x0, rtol=1e-15, atol=1e-15)
            model.stage(.2, 2.)
            y = np.ascontiguousarray(x/model.scale)
            model.eval(y, np.zeros(model.me), np.zeros(model.mi), 0.)
            expected_g = g*model.wg
            if model.kind in ['N', 'R']:
                expected_g[:36] /= denominator
            np.testing.assert_allclose(model.h, h*model.wh, rtol=2e-10, atol=2e-13)
            np.testing.assert_allclose(model.g, expected_g, rtol=2e-10, atol=2e-13)
            self.assertTrue((model.wh > 0).all() and (model.wg > 0).all())

    def test_al_gradient_chain_rule_and_finite_differences(self):
        rng = np.random.default_rng(13)
        for model in self.models:
            model.stage(.2, 2.)
            x = model.x0 + rng.uniform(-1e-4, 1e-4, model.n)
            y = np.ascontiguousarray(x/model.scale)
            lam, mu = rng.normal(size=model.me), rng.uniform(0., 1., model.mi)
            jac = model.jacobian(y)
            _, gf = model.eval(y, np.zeros(model.me), np.zeros(model.mi), 0.)
            h, g = model.h.copy(), model.g.copy()
            for rho in [0., 10., 1e4]:
                _, actual = model.eval(y, lam, mu, rho)
                expected = gf+jac[:model.me].T@(lam+rho*h)+jac[model.me:].T@(np.maximum(0., mu+rho*g) if rho else mu)
                np.testing.assert_allclose(actual, expected, atol=5e-10, rtol=1e-10)
            _, actual = model.eval(y, lam, mu, 10.)
            for j in range(model.n):
                step = 1e-7*max(1., abs(y[j]))
                a, b = y.copy(), y.copy()
                a[j] += step
                b[j] -= step
                fd = (model.eval(a, lam, mu, 10.)[0]-model.eval(b, lam, mu, 10.)[0])/(2*step)
                self.assertLess(abs(fd-actual[j])/(1+abs(fd)), 3e-5, (model.kind, j, fd, actual[j]))

    def test_common_and_paper_units_stationarity_from_reference_jacobian(self):
        rng = np.random.default_rng(15)
        for model in self.models:
            model.stage(.01, 8.)
            y = np.ascontiguousarray((model.x0+rng.uniform(-1e-4, 1e-4, model.n))/model.scale)
            lam, mu = rng.normal(size=model.me), rng.uniform(0., 1., model.mi)
            values = model.metrics(y, lam, mu)
            q, le, mi = model.reference_state(y, lam, mu)
            ref = model.reference
            jac = ref.jacobian(q)
            _, gf = ref.eval(q, np.zeros(ref.me), np.zeros(ref.mi), 0.)
            gradient = gf+jac[:ref.me].T@le+jac[ref.me:].T@mi
            self.assertAlmostEqual(max(abs(gradient)), values['common_kkt']['stat'], places=9)
            np.testing.assert_allclose(max(abs(gradient/ref.scale)), values['paper_units_kkt']['stat'], rtol=1e-11)


if __name__ == '__main__':
    unittest.main(verbosity=2)
