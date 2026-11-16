from decimal import Decimal as D,localcontext
import unittest
from reference import charge,delta


class TestReference(unittest.TestCase):
    def params(self):
        return dict(e_max=D(1),e_th=D('.7'),kappa=D('4.625'),sigma=D('.3')/D('4.625'),span=D('.3'))

    def test_identity(self):
        with localcontext() as ctx:
            ctx.prec=80;p=self.params()
            for e in [D('.3'),D('.7'),D('.9'),D(1),D('1.01')]:self.assertEqual(charge(p,e,D(0)),e)

    def test_cc_signed_line(self):
        p=self.params()
        self.assertEqual(charge(p,D('.3'),D('.01')),D('.34625'))
        self.assertEqual(charge(p,D('.3'),D('-.01')),D('.25375'))

    def test_cv_known_exponential(self):
        with localcontext() as ctx:
            ctx.prec=80;p=self.params()
            expected=D(1)-D('.1')*D(-1).exp()
            self.assertEqual(charge(p,D('.9'),p['sigma']),expected)

    def test_signed_inverse_across_threshold(self):
        with localcontext() as ctx:
            ctx.prec=80;p=self.params();e=D('.65');t=D('.05')
            result=charge(p,charge(p,e,t),-t)
            self.assertLess(abs(result-e),D('1e-75'))

    def test_phr_switch_and_linear_quadratic(self):
        metadata=dict(rho=2.,n_segments=1,lam=[2.],mu=[0.,.5])
        eq,ineq=delta([D('.125')],[D('-.25')],[D('.5')],[D('.75')],metadata,80)
        self.assertEqual(eq,D('.984375'));self.assertEqual(ineq,D(1))


if __name__=='__main__':unittest.main()
