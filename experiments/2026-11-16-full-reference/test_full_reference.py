from decimal import Decimal as D,localcontext
import unittest
from reference import evaluate,al_difference,psi,smooth_min
from battery_reference import binary


class TestFullReference(unittest.TestCase):
    def metadata(self):
        return dict(phys=dict(e_max=1.,e_th=.5,e_min=0.,v_d=4.,v_c=20.,zeta=2.,kappa=1.,
            s_min=.25,s_max=2.,range=2.,sigma=.5,span=.5),
            scale=[1.,1.,1.],wh=[1.]*3,wg=[1.]*6,n_segments=1,eps=.125,p=2.,smoothing_delta=.001,
            instance=dict(r0=[0.,0.],rf=[3.,4.],tasks=[[0.,0.]],regions=[dict(o=[0.,0.],rho=10.)]),
            lam=[0.]*3,mu=[0.]*6,rho=2.)

    def test_smooth_min_known_answer(self):
        with localcontext() as ctx:
            ctx.prec=80
            self.assertLess(abs(smooth_min([D(3),D(4)],D(2))-D('2.4')),D('1e-70'))

    def test_psi_boundaries_and_center(self):
        self.assertEqual(psi(D(-1),D(1)),D(0))
        self.assertEqual(psi(D(0),D(1)),D('.25'))
        self.assertEqual(psi(D(1),D(1)),D(1))
        self.assertEqual(psi(D(2),D(1)),D(2))

    def test_smooth_min_homogeneity(self):
        with localcontext() as ctx:
            ctx.prec=80;z=[D('.2'),D('1.3'),D(7)];p=D(12)
            self.assertLess(abs(smooth_min([3*x for x in z],p)-3*smooth_min(z,p)),D('1e-70'))

    def test_full_constraint_layout_and_known_geometry(self):
        with localcontext() as ctx:
            ctx.prec=80;m=self.metadata();f,h,g=evaluate([.75,.5,0.],m,80);eps=D('.125')
            self.assertEqual(f,D('.5'));self.assertEqual(h[0],D('1.5'))
            expected_task=(1/eps**2+1/(25+eps**2)).sqrt()**-1-eps
            expected_mode=(1/eps**2+1/(D('.25')+eps**2)).sqrt()**-1-eps
            self.assertLess(abs(h[1]-expected_task),D('1e-70'))
            self.assertLess(abs(h[2]-expected_mode),D('1e-70'))
            width=binary(.001);expected_speed=21/((25+width**2).sqrt()+(4+width**2).sqrt())
            self.assertLess(abs(g[0]-expected_speed),D('1e-70'))
            self.assertEqual(g[1:],[D('-1.5'),D('-.5'),D(-1),D(-6),D(0)])

    def test_signed_speed_does_not_admit_negative_duration(self):
        m=self.metadata();positive=evaluate([.75,.5,0.],m,80)[2][0]
        negative=evaluate([.75,-.5,0.],m,80)[2][0]
        self.assertGreater(negative,positive);self.assertGreater(negative,0)

    def test_decimal_perturbation_is_not_rounded_to_binary64(self):
        with localcontext() as ctx:
            ctx.prec=80;m=self.metadata();e=D('.75')+D('1e-30')
            battery=evaluate([e,D('.5'),D(0)],m,80)[1][0]
            self.assertEqual(battery,D('1.5')+D('2e-30'))

    def test_factored_delta_matches_independent_direct_al_values(self):
        with localcontext() as ctx:
            ctx.prec=80;m=self.metadata();a=evaluate([.75,.5,0.],m,80);b=evaluate([.76,.51,.01],m,80)
            def direct(v):
                f,h,g=v;return f+sum(x*x for x in h)+sum(max(D(0),x)**2 for x in g)
            value,parts=al_difference(a,b,m,80)
            self.assertLess(abs(value-(direct(b)-direct(a))),D('1e-70'))
            self.assertEqual(value,sum(parts.values(),D(0)))


if __name__=='__main__':unittest.main()
