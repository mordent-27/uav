from decimal import Decimal as D,localcontext
import unittest
import numpy as np
import lowcurv as cv


class TestCurvature(unittest.TestCase):
    def test_decimal_point_passthrough(self):
        x=cv.to_decimal([0.1,D('1.00000000000000000000000001')])
        self.assertEqual(x[0],D.from_float(0.1))
        self.assertEqual(x[1],D('1.00000000000000000000000001'))

    def test_shift_is_not_rounded_to_binary64(self):
        plus,minus=cv.shifted(cv.to_decimal([1.]),[1.],'1e-30',80)
        self.assertEqual(plus[0],D('1.000000000000000000000000000001'))
        self.assertEqual(minus[0],D('0.999999999999999999999999999999'))
        self.assertEqual(cv.nearest_binary(plus)[0],1.)

    def test_second_difference_known_answers(self):
        def f(p):return 3*p[0]**2+p[1]**4
        x=cv.to_decimal([1.,1.])
        with localcontext() as ctx:
            ctx.prec=80
            for v,expected in [([1.,0.],D(6)),([0.,1.],D(12))]:
                plus,minus=cv.shifted(x,v,'1e-20',80)
                q=cv.second_quotient(f(plus),f(x),f(minus),'1e-20',80)
                self.assertLess(abs(q-expected),D('1e-35'))

    def test_hessian_action_of_quadratic(self):
        A=[[D(2),D(1)],[D(1),D(3)]]
        def grad(p):
            with localcontext() as ctx:
                ctx.prec=80;return [sum(A[i][j]*p[j] for j in range(2)) for i in range(2)]
        hv=cv.hessian_action(grad,cv.to_decimal([.3,-.7]),[1.,-2.],'1e-10',80)
        self.assertEqual([float(a) for a in hv],[0.,-5.])

    def test_spectral_split_and_projection(self):
        H=np.diag([4.,1e-20,-1.]);w,V,keep,cut=cv.spectral_split(H,1e-15)
        self.assertEqual(cut,4e-15);self.assertEqual(int(keep.sum()),2)
        d,low=cv.newton_step(w,V,keep,np.array([2.,3.,1.]))
        np.testing.assert_allclose(d,[-.5,0.,1.],atol=1e-15)
        np.testing.assert_allclose(low,[0.,3.,0.],atol=1e-15)

    def test_newton_reaches_quadratic_stationary_point(self):
        A=np.array([[3.,1.],[1.,2.]]);b=np.array([1.,-1.])
        x=cv.to_decimal([5.,7.])
        def grad(p):return A@cv.nearest_binary(p)-b
        w,V,keep,_=cv.spectral_split(A,1e-15);d,low=cv.newton_step(w,V,keep,grad(x))
        with localcontext() as ctx:
            ctx.prec=80;x=[a+D.from_float(float(s)) for a,s in zip(x,d)]
        self.assertLess(float(max(abs(grad(x)))),1e-14);self.assertEqual(float(max(abs(low))),0.)

    def test_nearest_binary_rounding(self):
        half=D(2)**-53
        with localcontext() as ctx:
            ctx.prec=80
            self.assertEqual(cv.nearest_binary([D(1)+half])[0],1.)  # tie goes to even
            self.assertEqual(cv.nearest_binary([D(1)+half+D('1e-40')])[0],np.nextafter(1.,2.))
            self.assertEqual(cv.nearest_binary([D(1)+half/2])[0],1.)

    def test_rounding_floor_hand_example(self):
        H=np.array([[1e9,0.],[0.,1.]]);floors=cv.rounding_floors(H,[1.,2.])
        u=np.spacing(1.)
        self.assertAlmostEqual(floors['worst_half_ulp'],1e9*u/2,delta=1e-22)
        self.assertAlmostEqual(floors['single_half_ulp'],1e9*u/2,delta=1e-22)
        self.assertAlmostEqual(floors['uniform_rms'],1e9*u/np.sqrt(12),delta=1e-22)

    def test_step_in_ulps(self):
        s=cv.step_in_ulps(np.array([np.spacing(1.)/4,3*np.spacing(2.)]),cv.to_decimal([1.,2.]))
        self.assertEqual(s['below_half_ulp'],1);self.assertAlmostEqual(s['max_ulps'],3.)

    def test_classification_rules(self):
        self.assertEqual(cv.curvature_class(-2e-12,1e-12),'negative')
        self.assertEqual(cv.curvature_class(1e-12,1e-12),'near_zero')
        self.assertEqual(cv.curvature_class(-1e-12,1e-12),'near_zero')
        self.assertEqual(cv.curvature_class(3e-12,1e-12),'positive')
        self.assertEqual(cv.rounding_verdict(2e-8,1e-9,1e-8),'high_precision_point_not_reached')
        self.assertEqual(cv.rounding_verdict(1e-9,2e-7,1e-8),'rounding_blocks_target')
        self.assertEqual(cv.rounding_verdict(1e-9,5e-9,1e-8),'binary64_point_reaches_target')


if __name__=='__main__':unittest.main()
