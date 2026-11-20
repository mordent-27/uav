import copy
import json
import math
import unittest
import casadi as ca
import numpy as np
from model import ReducedBranch, TARGETS, ROOT, load
from verify_point import check, carriers


class Tests(unittest.TestCase):
    def test_literal_R_and_gap_indices_on_all_cases(self):
        for case in TARGETS:
            d=load(case);b=ReducedBranch(d);p=d['phys'];v=np.array(b.eval_revisit(b.x0)).ravel()
            r=d['solution']['r'];s=b.x0[b.nr+b.ns:]/p['v_d']
            expected=[]
            for j,a,z in b.pairs:
                self.assertEqual(d['modes'][a],j);self.assertEqual(d['modes'][z],j)
                self.assertTrue(all(d['modes'][k]!=j for k in range(a+1,z)))
                distance=math.dist(r[z],r[a+1]);bound=p['v_c']*sum(s[a+1:z])
                expected.append((distance**2-bound**2)/(math.sqrt(distance**2+1e-6)+math.sqrt(bound**2+1e-6)))
            np.testing.assert_allclose(v,expected,atol=1e-12,rtol=1e-12)
            self.assertTrue(any(v>1e-6),case)

    def test_independent_interpolated_carrier_matches_accepted_old_points(self):
        for case in TARGETS:
            d=json.loads((ROOT/f'experiments/2026-11-18-carrier-nlp/runs/{case}/carrier.json').read_text())
            status=next(r for r in json.loads((ROOT/'experiments/2026-11-18-carrier-nlp/results.json').read_text()) if r['case']==case)['carrier']['accepted']
            self.assertEqual(check(d,load(case))['accepted'],status)
            d['carrier_positions']=carriers(d)
            self.assertEqual(check(d,load(case))['accepted'],status)

    def test_R_derivative_and_Hessian_vector_by_finite_difference(self):
        b=ReducedBranch(load(TARGETS[1]));x=b.x0.copy();rng=np.random.default_rng(120)
        x[:b.nr]+=rng.normal(0,.03,b.nr)
        weight=ca.DM(rng.normal(size=len(b.pairs)));f=ca.dot(weight,b.revisit)
        fn=ca.Function('test_derivatives',[b.v],[f,ca.gradient(f,b.v),ca.hessian(f,b.v)[0]])
        value,gradient,hessian=fn(x);g=np.array(gradient).ravel();h=np.array(hessian)
        eps=2e-6;direction=rng.normal(size=len(x));direction/=np.linalg.norm(direction)
        plus=fn(x+eps*direction);minus=fn(x-eps*direction)
        self.assertAlmostEqual(float((plus[0]-minus[0])/(2*eps)),float(g@direction),places=6)
        np.testing.assert_allclose((np.array(plus[1]).ravel()-np.array(minus[1]).ravel())/(2*eps),h@direction,atol=2e-5,rtol=2e-5)

    def test_independent_check_rejects_broken_energy_or_carrier(self):
        path=ROOT/f'experiments/2026-11-18-carrier-nlp/runs/{TARGETS[1]}/carrier.json'
        good=json.loads(path.read_text());self.assertTrue(check(good)['accepted'])
        d=copy.deepcopy(good);d['solution']['e'][-1]+=.01;self.assertFalse(check(d)['accepted'])
        d=copy.deepcopy(good);key=next(iter(d['carrier_positions']));d['carrier_positions'][key][0][0]+=100
        self.assertFalse(check(d)['accepted'])


if __name__=='__main__':unittest.main()
