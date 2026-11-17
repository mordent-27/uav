import unittest
from types import SimpleNamespace
import numpy as np
from fast_hessian import gradient_only


class Native:
    def __init__(self):self.calls=0
    def eval(self,q,lam,mu,rho):
        self.calls+=1;assert rho==0
        self.h=np.array([q[0]-3*q[1]]);self.g=np.array([2*q[0]+q[1]])
        return 0.,q+np.array([lam[0]+2*mu[0],-3*lam[0]+mu[0]])


class GradientTests(unittest.TestCase):
    def test_scaled_gradient_and_caches(self):
        native=Native();m=SimpleNamespace(kind='R',ratio=np.array([2.,.5]),wh=np.array([3.]),wg=np.array([4.]),native=native)
        result=gradient_only(m,np.array([1.,2.]),np.array([5.]),np.array([-2.]))
        np.testing.assert_array_equal(result,np.array([2.,-26.]))
        np.testing.assert_array_equal(m.h,[-3.]);np.testing.assert_array_equal(m.g,[20.])
        self.assertEqual(native.calls,1)

    def test_other_variants_rejected(self):
        with self.assertRaises(AssertionError):gradient_only(SimpleNamespace(kind='N'),None,None,None)


if __name__=='__main__':unittest.main()
