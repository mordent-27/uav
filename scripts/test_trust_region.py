"""Numerical contracts, analytic answers and independent low-dimensional checks."""
import ast
import os
from pathlib import Path
import unittest
import numpy as np
from trust_region import tr_step

ROOT=Path(__file__).resolve().parents[1]


def legacy_step():
    # Extract only the function so the regression has no UAV/native dependencies.
    source=ROOT/'experiments/2026-11-14-conditioning/newton_al.py'
    tree=ast.parse(source.read_text())
    function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='tr_step')
    module=ast.Module(body=[function],type_ignores=[]);namespace={'np':np}
    exec(compile(module,str(source),'exec'),namespace)
    return namespace['tr_step']


class TestTrustRegion(unittest.TestCase):
    def solve(self,H,g,delta):
        w,V=np.linalg.eigh(H);p,boundary=tr_step(w,V,np.array(g,dtype=float),delta)
        return p,boundary

    def contract(self,H,g,delta,p,boundary,tol=2e-10):
        g=np.asarray(g);norm=float(np.linalg.norm(p))
        self.assertTrue(np.all(np.isfinite(p)))
        self.assertLessEqual(norm,delta*(1+tol)+1e-15)
        if boundary:self.assertAlmostEqual(norm,delta,delta=tol*max(1.,delta))
        model=float(g@p+.5*p@H@p)
        scale=max(1.,np.linalg.norm(g)*max(1.,delta),np.linalg.norm(H,2)*max(1.,delta**2))
        self.assertLessEqual(model,tol*scale)  # zero is always feasible
        if norm==0:
            self.assertLessEqual(np.linalg.norm(g),tol*scale)
            return
        # Global TR certificate: shifted Hessian PSD, stationarity,
        # nonnegative multiplier and complementary slackness.
        multiplier=-float(p@(g+H@p))/(p@p) if boundary else 0.
        self.assertGreaterEqual(multiplier,-tol*scale)
        self.assertGreaterEqual(np.linalg.eigvalsh(H)[0]+multiplier,-tol*scale)
        self.assertLessEqual(np.linalg.norm(g+H@p+multiplier*p),tol*scale)
        self.assertLessEqual(abs(multiplier*(norm-delta)),tol*scale)

    def test_regression_nonzero_lowest_component(self):
        H=np.diag([-1.,2.]);g=np.array([-1e-15,.6]);delta=1.
        function=legacy_step() if os.environ.get('UAV_TEST_TR_IMPL')=='legacy' else tr_step
        p,b=function(np.diag(H),np.eye(2),g,delta)
        self.contract(H,g,delta,p,b)

    def test_spd_interior_known_answer(self):
        H=np.diag([2.,4.]);g=np.array([2.,-4.]);p,b=self.solve(H,g,10.)
        np.testing.assert_allclose(p,[-1.,1.],atol=1e-12);self.assertFalse(b)
        self.contract(H,g,10.,p,b)

    def test_spd_boundary_known_answer(self):
        H=np.eye(2);g=np.array([3.,4.]);p,b=self.solve(H,g,2.)
        np.testing.assert_allclose(p,[-1.2,-1.6],atol=2e-12)
        self.contract(H,g,2.,p,b)

    def test_indefinite_hard_case_known_answer(self):
        H=np.diag([-2.,1.]);g=np.array([0.,1.]);p,b=self.solve(H,g,1.)
        self.assertAlmostEqual(abs(p[0]),np.sqrt(8/9),places=12)
        self.assertAlmostEqual(p[1],-1/3,places=12);self.contract(H,g,1.,p,b)

    def test_zero_gradient_negative_curvature(self):
        H=np.diag([-2.,3.]);g=np.zeros(2);p,b=self.solve(H,g,1.)
        self.assertAlmostEqual(abs(p[0]),1.);self.contract(H,g,1.,p,b)

    def test_singular_and_repeated_eigenvalues(self):
        for eigen,g in [([0.,2.],[0.,1.]),([0.,0.],[1.,2.]),([-2.,-2.,3.],[0.,0.,1.])]:
            with self.subTest(eigen=eigen):
                H=np.diag(eigen);p,b=self.solve(H,g,1.);self.contract(H,g,1.,p,b)

    def test_zero_radius(self):
        p,b=self.solve(np.eye(2),[1.,2.],0.)
        np.testing.assert_array_equal(p,[0.,0.]);self.assertTrue(b)

    def test_near_zero_eigenvalues(self):
        for eigen in [[-1e-10,1.,1e6],[0.,1e-12,2.],[1e-12,1.,1e6]]:
            with self.subTest(eigen=eigen):
                H=np.diag(eigen);g=np.array([0.,.2,.3]);p,b=self.solve(H,g,1.)
                self.contract(H,g,1.,p,b)

    def test_rotation_invariance(self):
        rng=np.random.default_rng(20261116);Q,_=np.linalg.qr(rng.normal(size=(4,4)))
        H=np.diag([-2.,.5,2.,5.]);g=np.array([.3,-.6,.9,.4])
        p,b=self.solve(H,g,1.);rotated,rb=self.solve(Q@H@Q.T,Q@g,1.)
        np.testing.assert_allclose(rotated,Q@p,atol=2e-11,rtol=2e-11)
        self.contract(Q@H@Q.T,Q@g,1.,rotated,rb)

    def test_random_two_dimensional_certificate_and_grid(self):
        rng=np.random.default_rng(20261117)
        angle=np.linspace(0,2*np.pi,16384,endpoint=False)
        circle=np.column_stack([np.cos(angle),np.sin(angle)])
        for i in range(32):
            with self.subTest(case=i):
                A=rng.normal(size=(2,2));H=(A+A.T)/2;g=rng.normal(size=2)
                delta=float(rng.uniform(.05,3.));p,b=self.solve(H,g,delta)
                self.contract(H,g,delta,p,b)
                points=delta*circle
                grid=points@g+.5*np.einsum('bi,ij,bj->b',points,H,points)
                self.assertLessEqual(float(g@p+.5*p@H@p),float(grid.min())+1e-9)

    def test_invalid_inputs(self):
        for w,V,g,delta in [([1.],np.eye(2),[1.],1.),([2.,1.],np.eye(2),[1.,1.],1.),
            ([1.],np.eye(1),[np.nan],1.),([1.],np.eye(1),[1.],-1.),([1.],np.eye(1),[1.],np.inf)]:
            with self.subTest(delta=delta,w=w):
                with self.assertRaises(ValueError):tr_step(w,V,g,delta)


if __name__=='__main__':unittest.main()
