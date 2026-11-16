from decimal import Decimal as D,localcontext
import importlib.util
from pathlib import Path
from time import monotonic
import unittest
import numpy as np
import loop

spec=importlib.util.spec_from_file_location('precise_inner_loop',Path(__file__).resolve().parent.parent/'2026-11-16-precise-inner/inner.py')
inner=importlib.util.module_from_spec(spec);spec.loader.exec_module(inner)


def quartic(p):
    """f=sum(x^4)/4+x^2/2: H below is deliberately too small so some trials are rejected."""
    return float(np.sum(p**4)/4+np.sum(p**2)/2),p**3+p


def strip(rows):return [{k:v for k,v in r.items() if k!='seconds'} for r in rows]


class TestLoop(unittest.TestCase):
    def test_legacy_factors_match_inner_solve(self):
        y=np.array([2.,-1.5,.7]);H=lambda p,c:np.diag(.3*np.ones(3))
        a,b=[],[]
        r1=inner.solve(lambda p,d:(*quartic(p),None),H,y.copy(),monotonic()+5,a.append)
        r2=loop.solve(lambda p,d:quartic(p),H,y.copy(),monotonic()+5,b.append)
        self.assertEqual(strip(a),strip(b))
        for k in ['y','gradient','value','gradient_inf','status','iterations','accepted','scalar_calls','trials']:self.assertEqual(r1[k],r2[k],k)
        self.assertGreater(r2['trials'],r2['accepted'])  # the test exercises rejections

    def test_exact_acceptance_rules(self):
        d=loop.assess_exact(1.,.2,1.,1.,True);self.assertTrue(d.accepted);self.assertEqual(d.radius,.25)
        d=loop.assess_exact(1.,.9,1.,1.,True);self.assertEqual(d.radius,2.)
        d=loop.assess_exact(1.,.9,1.,.5,False);self.assertEqual(d.radius,1.)
        d=loop.assess_exact(1.,5e-5,1.,1.,True);self.assertFalse(d.accepted)
        d=loop.assess_exact(0.,1.,1.,1.,True);self.assertFalse(d.accepted);self.assertEqual(d.ratio,0.)
        d=loop.assess_exact(1.,.9,800.,800.,True);self.assertEqual(d.radius,1e3)

    def test_exact_acceptance_ignores_huge_constant(self):
        # The value carries a 1e8 constant: binary64 differences vanish, the Decimal difference does not.
        def exact(p):
            with localcontext() as c:
                c.prec=80;return D(10)**8+sum(D.from_float(float(v))**2/2 for v in p)
        r=loop.solve(lambda p,d:(1e8+float(p@p)/2,p.copy()),lambda p,c:np.eye(2),np.array([1e-6,-2e-6]),monotonic()+5,exact_value=exact)
        self.assertEqual(r['status'],'converged');self.assertGreater(r['decimal_calls'],1)

    def test_floor_threshold(self):
        H=np.diag([1e9,1.]);y=np.array([1.5,2.5]);u=np.spacing(y)
        self.assertAlmostEqual(loop.floor_estimate(H,y),1e9*u[0]/np.sqrt(12),delta=1e-22)
        self.assertEqual(loop.floor_threshold(np.eye(2),y),1e-8)
        self.assertAlmostEqual(loop.floor_threshold(H,y),2*1e9*u[0]/np.sqrt(12),delta=1e-22)

    def test_floor_stop(self):
        # Gradient stays at 1e-7, above 1e-8 but below 2F for H=1e10*I at y=1.5: stop 1 ends at once, stop 0 does not.
        g=lambda p:(0.,np.array([1e-7]));H=lambda p,c:np.array([[1e10]])
        r=loop.solve(lambda p,d:g(p),H,np.array([1.5]),monotonic()+5,floor_stop=True)
        self.assertEqual(r['status'],'converged_floor');self.assertEqual(r['accepted'],0);self.assertGreater(r['stop']['threshold'],1e-7)


if __name__=='__main__':unittest.main()
