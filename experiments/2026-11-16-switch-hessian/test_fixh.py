from decimal import Decimal as D,localcontext
import unittest
import numpy as np
import fixh

PHYS=dict(e_max=1.,e_th=.7,kappa=4.625)


class TestFixH(unittest.TestCase):
    def test_margin_hand_example(self):
        # ns=2, layout r(2) e(2) s(2) c(2). Segment 0 starts from e_max=1>=e_th and is excluded.
        # Segment 1 starts from e0=0.5 and has c1 at the switch (0.7-0.5)/4.625 up to binary64 rounding.
        ns=2;y=[0.,0.,.5,.4,.1,.1,.01,(.7-.5)/4.625];rows=fixh.margins(y,[1.]*8,PHYS,ns)
        self.assertEqual([r['segment'] for r in rows],[1]);self.assertLess(abs(rows[1-1]['margin']),D('1e-16'))
        rows=fixh.margins([0.,0.,.5,.4,.1,.1,.01,.01],[1.]*8,PHYS,ns)
        with localcontext() as ctx:
            ctx.prec=80;expected=D.from_float(.01)-(D.from_float(.7)-D.from_float(.5))/D.from_float(4.625)
        self.assertLess(abs(rows[0]['margin']-expected),D('1e-70'));self.assertLess(rows[0]['margin'],0)

    def test_negative_charge_is_excluded(self):
        ns=2;y=[0.,0.,.5,.4,.1,.1,.01,-.02];self.assertEqual(fixh.margins(y,[1.]*8,PHYS,ns),[])

    def test_straddling_rule(self):
        ns=2;scale=[1.]*8;rows=[dict(segment=1,margin=D('5e-8'))]
        J,reasons=fixh.straddling(rows,scale,PHYS,ns,1e-7)
        self.assertEqual(J,[7]);self.assertEqual(reasons[0]['coordinate'],'c1')  # e0 needs |m|<=1e-7/4.625
        J,_=fixh.straddling([dict(segment=1,margin=D('1e-8'))],scale,PHYS,ns,1e-7);self.assertEqual(J,[2,7])
        J,_=fixh.straddling([dict(segment=1,margin=D('2e-7'))],scale,PHYS,ns,1e-7);self.assertEqual(J,[])

    def test_replace_columns_symmetric_and_untouched(self):
        H=np.arange(16.).reshape(4,4);H=(H+H.T)/2;c1=np.array([10.,11.,12.,13.]);c3=np.array([20.,21.,22.,23.])
        F=fixh.replace_columns(H,[1,3],[c1,c3])
        np.testing.assert_array_equal(F,F.T)
        self.assertEqual(F[0,1],10.);self.assertEqual(F[2,3],22.);self.assertEqual(F[1,3],(c3[1]+c1[3])/2)
        np.testing.assert_array_equal(F[np.ix_([0,2],[0,2])],H[np.ix_([0,2],[0,2])])

    def test_gate(self):
        self.assertTrue(fixh.gate([1.0005,.9991]));self.assertFalse(fixh.gate([1.0005,1.0011]));self.assertFalse(fixh.gate([1.999889]))


if __name__=='__main__':unittest.main()
