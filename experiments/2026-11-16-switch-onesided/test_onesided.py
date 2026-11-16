import unittest
import numpy as np
import helpers as h
import onesided


class FakeModel:
    """f = 0.5*a*x0^2 (x0<0) or 0.5*b*x0^2 (x0>=0) + 0.5*x1^2, no constraints; switch at x0=0."""
    me=0;mi=0
    def __init__(self,a,b):self.a,self.b=a,b;self.h=np.zeros(0);self.g=np.zeros(0)
    def eval(self,y,lam,mu,rho):
        k=self.a if y[0]<0 else self.b
        return .5*k*y[0]**2+.5*y[1]**2,np.array([k*y[0],y[1]])
    def jacobian(self,y):return np.zeros((0,2))


class FakeFrozen:
    def __init__(self,a,b):self.m=FakeModel(a,b);self.lam=np.zeros(0);self.mu=np.zeros(0);self.rho=0.


class TestOneSided(unittest.TestCase):
    def setUp(self):self.f=FakeFrozen(0.,6.);self.y=np.array([1e-14,1.])

    def stats(self):return dict(builds=0,triggered=0,max_coordinates=0)

    def test_central_difference_averages_both_sides(self):
        H,_=h.decomposition.hessian_of_al(self.f,self.y,1e-7)
        self.assertAlmostEqual(H[0,0],3.,delta=1e-6)  # (0+6)/2

    def test_onesided_recovers_the_point_side(self):
        stats=self.stats();H,_=onesided.hessian_onesided(h.decomposition.hessian_of_al,self.f,self.y,1e-7,None,lambda y:{0:1},stats)
        old,_=h.decomposition.hessian_of_al(self.f,self.y,1e-7)
        self.assertAlmostEqual(H[0,0],6.,delta=1e-6);self.assertEqual(H[1,1],old[1,1]);self.assertEqual(stats['triggered'],1)
        y=np.array([-1e-14,1.]);H,_=onesided.hessian_onesided(h.decomposition.hessian_of_al,self.f,y,1e-7,None,lambda y:{0:-1},self.stats())
        self.assertAlmostEqual(H[0,0],0.,delta=1e-6)

    def test_no_trigger_is_bitwise_identical(self):
        old,_=h.decomposition.hessian_of_al(self.f,self.y,1e-7)
        new,_=onesided.hessian_onesided(h.decomposition.hessian_of_al,self.f,self.y,1e-7,None,lambda y:{},self.stats())
        np.testing.assert_array_equal(old,new)

    def test_side_from_margin_sign(self):
        # ns=2 layout r(2) e(2) s(2) c(2); segment 1 starts from e0=0.5; c1 slightly above / below the switch.
        phys=dict(e_max=1.,e_th=.7,kappa=4.625);sw=(.7-.5)/4.625
        rule=onesided.switch_rule([1.]*8,phys,2,1e-7)
        self.assertEqual(rule([0.,0.,.5,.4,.1,.1,.01,sw+1e-12]),{2:1,7:1})
        self.assertEqual(rule([0.,0.,.5,.4,.1,.1,.01,sw-1e-12]),{2:-1,7:-1})
        self.assertEqual(rule([0.,0.,.5,.4,.1,.1,.01,sw+1e-3]),{})


if __name__=='__main__':unittest.main()
