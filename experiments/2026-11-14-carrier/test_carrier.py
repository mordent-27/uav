"""Boundary and adversarial tests for the fixed-mode carrier construction."""

import copy
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('carrier', ROOT/'scripts/carrier_certificate.py')
carrier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(carrier)


def plan(r=None, seconds=None, modes=None, regions=None):
    r = [[-1., 0.], [-1., 0.], [1., 0.], [1., 0.]] if r is None else r
    seconds = [30., 200., 30.] if seconds is None else seconds
    modes = [0, -1, 0] if modes is None else modes
    regions = [dict(o=[0., 0.], rho=2.)] if regions is None else regions
    s = [x/3600 for x in seconds]
    return dict(instance=dict(regions=regions), phys=dict(v_c=10.8), modes=modes,
                solution=dict(r=r, s=s, c=[s[k] if m>=0 else 0. for k,m in enumerate(modes)]))


class CarrierTests(unittest.TestCase):
    def test_original_counterexample_rejected(self):
        result = carrier.certify(plan())
        self.assertFalse(result['feasible'])
        self.assertAlmostEqual(result['carriers'][0]['failures'][0]['excess_km'], 1.4)

    def test_exact_reachability_boundary_and_perturbation(self):
        at = 2/10.8*3600
        for dt, expected in [(0., True), (1., True), (-1., False)]:
            d = plan(seconds=[30., at+dt, 30.])
            result = carrier.certify(d)
            self.assertEqual(result['feasible'], expected)
            if expected:
                self.assertLessEqual(max(carrier.check_constructed(d, result).values()), 1e-9)

    def test_continuous_moving_charge(self):
        d = plan(r=[[-1.,0.],[0.,0.],[1.,0.]],
                 seconds=[3600/10.8,3600/10.8], modes=[0,0])
        result = carrier.certify(d)
        self.assertTrue(result['feasible'])
        self.assertEqual(result['carriers'][0]['positions'], d['solution']['r'])
        carrier.check_constructed(d, result)

    def test_charge_interval_speed_checked(self):
        d = plan(r=[[-1.,0.],[1.,0.]], seconds=[30.], modes=[0])
        self.assertFalse(carrier.certify(d)['feasible'])

    def test_known_initial_conflicts_with_immediate_contact(self):
        self.assertFalse(carrier.certify(plan(seconds=[30.,700.,30.]), {0:[1.,0.]})['feasible'])

    def test_known_initial_reachability_before_first_contact(self):
        d = plan(r=[[-1.,0.],[-1.,0.],[-1.,0.]], seconds=[200.,30.], modes=[-1,0])
        self.assertTrue(carrier.certify(d)['feasible'])
        self.assertFalse(carrier.certify(d, {0:[1.,0.]})['feasible'])
        result = carrier.certify(d, {0:[-1.,0.]})
        self.assertTrue(result['feasible'])
        carrier.check_constructed(d, result)

    def test_unused_region_and_independent_carriers(self):
        d = plan(r=[[0.,0.],[0.,0.],[4.,0.],[4.,0.]], modes=[0,-1,1],
                 regions=[dict(o=[0.,0.],rho=1.),dict(o=[4.,0.],rho=1.),dict(o=[8.,0.],rho=1.)])
        result = carrier.certify(d, {2:[8.,.5]})
        self.assertTrue(result['feasible'])
        carrier.check_constructed(d, result)
        self.assertTrue(all(p == [8.,.5] for p in result['carriers'][2]['positions']))

    def test_region_violation_and_wrong_initial_region(self):
        d = plan(seconds=[30.,700.,30.])
        d['instance']['regions'][0]['rho'] = .5
        self.assertFalse(carrier.certify(d)['feasible'])
        self.assertFalse(carrier.certify(plan(), {0:[3.,0.]})['feasible'])
        with self.assertRaises(ValueError):
            carrier.certify(plan(), {1:[0.,0.]})

    def test_approximate_mode_is_not_certified(self):
        d = plan()
        d['solution']['c'][0] -= 1e-8
        with self.assertRaises(ValueError):
            carrier.certify(d)

    def test_nonfinite_or_inconsistent_input(self):
        for key, value in [('s',[float('nan'),.1,.1]), ('c',[float('inf'),0.,0.]),
                           ('s',[0.,.1,.1]), ('s',[.1])]:
            d = plan()
            d['solution'][key] = value
            with self.assertRaises(ValueError):
                carrier.certify(d)
        d = plan()
        d['solution']['r'][0][0] = float('nan')
        with self.assertRaises(ValueError):
            carrier.certify(d)

    def test_independent_check_detects_tampered_certificate(self):
        d = plan(seconds=[30.,700.,30.])
        result = carrier.certify(d)
        self.assertTrue(result['feasible'])
        bad = copy.deepcopy(result)
        bad['carriers'][0]['positions'][1] = [10.,0.]
        with self.assertRaises(AssertionError):
            carrier.check_constructed(d, bad)


if __name__ == '__main__':
    unittest.main(verbosity=2)
