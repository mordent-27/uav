from decimal import Decimal as D,localcontext
import unittest
import numpy as np
import kink


META=dict(rho=1e4,lam=[.5],mu=[0.,2e-5,.25])


def primal(x):
    """Tiny smooth model: objective, one equality, three inequalities (index 1 is the weakly active one)."""
    with localcontext() as ctx:
        ctx.prec=80;a,b=x
        return a*a+b,[a-b],[a+b-D(3),D('-2e-9')+(b-D(1))/D(1000),-a]


class TestKink(unittest.TestCase):
    def test_true_mode_equals_precise_inner(self):
        for x in [[D('0.7'),D('1.3')],[D(2),D('0.999999')]]:
            p=primal(x)
            self.assertEqual(kink.piece_al(p,META,80),kink.precision.absolute_al(p,META,80))

    def test_pieces_match_on_their_sides_and_join_at_zero(self):
        rho=D(10000)
        for b,mode in [(D('0.5'),'inactive'),(D('1.5'),'active')]:
            p=primal([D('0.4'),b]);s=kink.shifted_values(p,META,80)[1]
            self.assertTrue(kink.side_ok(mode,s))
            self.assertEqual(kink.piece_al(p,META,80,1,mode),kink.piece_al(p,META,80))
        # s=0 exactly: mu+rho*g=0 at g=-mu/rho
        with localcontext() as ctx:
            ctx.prec=80;b0=D(1)+D(1000)*(D('2e-9')-kink.binary(2e-5)/rho)
        p=primal([D('0.4'),b0]);self.assertEqual(kink.shifted_values(p,META,80)[1],0)
        self.assertEqual(kink.piece_al(p,META,80,1,'inactive'),kink.piece_al(p,META,80,1,'active'))
        gi,ga=kink.central_pair(primal,[lambda q:kink.piece_al(q,META,80,1,'inactive'),lambda q:kink.piece_al(q,META,80,1,'active')],
            [D('0.4'),b0],80,'1e-30')
        self.assertLess(max(abs(a-c) for a,c in zip(gi,ga)),D('1e-25'))

    def test_central_pair_matches_precise_inner_gradient(self):
        x=[D('0.4'),D('1.2')];value=lambda q:kink.piece_al(q,META,80)
        g,=kink.central_pair(primal,[value],x,80,'1e-20')
        ref=kink.precision.central_gradient(lambda q:kink.precision.absolute_al(primal(q),META,80),x,80,'1e-20')
        self.assertEqual(g,ref)

    def test_one_dimensional_piecewise_newton_picks_correct_side(self):
        # L(x)=(x-1)^2/2 + max(0,s)^2/(2r), s=r*(x-0.5): minimiser lies on the active side.
        r=100.;x=0.;out={}
        for mode,H in [('inactive',1.),('active',1.+r)]:
            z=x
            for _ in range(5):
                s=r*(z-.5);g=(z-1)+(s if mode=='active' else 0.);z-=g/H
            out[mode]=(z,r*(z-.5))
        self.assertFalse(kink.side_ok('inactive',out['inactive'][1]))
        self.assertTrue(kink.side_ok('active',out['active'][1]))
        self.assertAlmostEqual(out['active'][0],(1+.5*r)/(1+r))

    def test_lattice_search_known_integer_and_limit(self):
        y=np.array([1.5,2.5]);H=np.diag([1e9,1.]);u=np.spacing(y)
        point,k,info=kink.lattice_search(np.array([3.3e9*u[0],0.]),H,y)
        self.assertEqual(k.tolist(),[-3,0]);self.assertEqual(point[0],y[0]-3*u[0])
        point,k,info=kink.lattice_search(np.array([100e9*u[0],0.]),H,y)
        self.assertEqual(k.tolist(),[-8,0]);self.assertEqual(info['max_abs_k'],8)
        self.assertAlmostEqual(info['actual_step_model_gradient_inf'],info['model_gradient_inf'],delta=1e-12)

    def test_lattice_steps_cross_binade_exactly(self):
        below=np.nextafter(2.,0.);self.assertEqual(kink.lattice_steps([below],[2])[0],np.nextafter(2.,3.))

    def test_piece_verdict(self):
        self.assertEqual(kink.piece_verdict(5e-9,'inactive',D('-1e-12'),0,1e-8),('valid',[]))
        self.assertEqual(kink.piece_verdict(5e-9,'inactive',D('1e-12'),0,1e-8),('invalid',['side']))
        self.assertEqual(kink.piece_verdict(2e-8,'active',D('1e-12'),2,1e-8),('invalid',['gradient','other_switches']))


if __name__=='__main__':unittest.main()
