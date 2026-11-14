"""Check diagnostic ABI, AL gradient, and Jacobian before expanded experiments."""
import json
import unittest

import numpy as np
from independent_al import Model


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.m = Model(1,0)
    def tearDown(self):
        self.m.close()

    def test_initial_values(self):
        d = self.m.solution(self.m.y)
        self.assertEqual(self.m.stamps,7)
        self.assertAlmostEqual(sum(d['init']['s']),d['metrics']['init_objective'],places=8)
        self.assertEqual(d['init']['r'],d['solution']['r'])

    def test_augmented_gradient(self):
        m = self.m
        rng = np.random.default_rng(34)
        y = m.y+rng.uniform(-.1,.1,m.n)
        lam,mu = rng.normal(size=m.me),rng.uniform(0.,1.,m.mi)
        for rho in [0.,10.]:
            _, grad = m.eval(y,lam,mu,rho)
            for i in range(m.n):
                h = 1e-6
                yp,ym = y.copy(),y.copy()
                yp[i]+=h;ym[i]-=h
                fd = (m.eval(yp,lam,mu,rho)[0]-m.eval(ym,lam,mu,rho)[0])/(2*h)
                self.assertLess(abs(fd-grad[i])/(1+abs(fd)),1e-5,(rho,i,fd,grad[i]))

    def test_large_penalty_chain_rule_without_scalar_cancellation(self):
        m = self.m
        rng = np.random.default_rng(34)
        y = m.y+rng.uniform(-.1,.1,m.n)
        lam,mu = rng.normal(size=m.me),rng.uniform(0.,1.,m.mi)
        jac = m.jacobian(y)
        _,gf = m.eval(y,np.zeros(m.me),np.zeros(m.mi),0.)
        h,g = m.h.copy(),m.g.copy()
        for rho in [1e6,1e8]:
            _,grad = m.eval(y,lam,mu,rho)
            expected = gf+jac[:m.me].T@(lam+rho*h)+jac[m.me:].T@np.maximum(0,mu+rho*g)
            self.assertLess(np.max(np.abs(expected-grad)/(1+np.abs(grad))),1e-10)

    def test_constraint_jacobian(self):
        m = self.m
        y = m.y+np.random.default_rng(12).uniform(-.1,.1,m.n)
        lam,mu = np.zeros(m.me),np.zeros(m.mi)
        jac = m.jacobian(y)
        for i in range(m.n):
            h = 1e-6
            yp,ym = y.copy(),y.copy()
            yp[i]+=h;ym[i]-=h
            m.eval(yp,lam,mu,0.);plus=np.r_[m.h,m.g].copy()
            m.eval(ym,lam,mu,0.);minus=np.r_[m.h,m.g].copy()
            error = np.abs((plus-minus)/(2*h)-jac[:,i])/(1+np.abs(jac[:,i]))
            self.assertLess(error.max(),1e-5,(i,error.max()))


if __name__ == '__main__':
    unittest.main(verbosity=2)
