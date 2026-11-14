"""Check the exact branch's charging law against Rust and its full Jacobian."""
import ctypes as ct
import json
from pathlib import Path
import unittest

import casadi as ca
import numpy as np
from fixed_branch import FixedBranch,charge_expr,restore_source,ROOT


class BranchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=restore_source(json.loads((ROOT/'experiments/2026-11-14-final-continuation/fig1-accurate/raw.json').read_text()))

    def test_charge_value_and_derivatives_against_original_rust(self):
        lib=ct.CDLL('/tmp/uav-restoration-battery.so')
        lib.charge_value_gradient.argtypes=[ct.c_double,ct.c_double,ct.POINTER(ct.c_double)]
        e,t=ca.SX.sym('e'),ca.SX.sym('t');value=charge_expr(self.data['phys'],e,t)
        evaluate=ca.Function('check_charge',[e,t],[value,ca.gradient(value,e),ca.gradient(value,t)])
        points=[(e,t) for e in [0.,.4,.7-1e-9,.7,.7+1e-9,.99,1.] for t in [0.,30/3600,.1,1.]]
        for e in [0.,.2,.69]:
            threshold=(.7-e)/4.625
            points.extend((e,threshold+dt) for dt in [-1e-9,0.,1e-9])
        rng=np.random.default_rng(190)
        points.extend(zip(rng.uniform(0.,1.,100),rng.uniform(0.,1.,100)))
        for energy,time in points:
            out=(ct.c_double*3)();lib.charge_value_gradient(energy,time,out)
            symbolic=np.array([float(v) for v in evaluate(energy,time)])
            np.testing.assert_allclose(symbolic,np.array(out),rtol=1e-12,atol=1e-12)

    def test_original_charge_modes_and_task_assignment_unchanged(self):
        for moving in [False,True]:
            model=FixedBranch(self.data,moving)
            self.assertEqual(model.modes,self.data['modes']);self.assertEqual(model.stamps,self.data['task_stamp'])
            for task,k in zip(self.data['instance']['tasks'],model.stamps):
                np.testing.assert_array_equal(model.initial_positions[k],task)
                self.assertNotIn(k,model.free)

    def test_exact_branch_jacobians(self):
        rng=np.random.default_rng(876)
        for moving in [False,True]:
            model=FixedBranch(self.data,moving)
            point=model.x0+rng.uniform(-1e-3,1e-3,len(model.x0))
            _,_,_,jac=model.evaluate(point);jac=np.array(jac)
            for i in range(len(point)):
                plus,minus=point.copy(),point.copy();plus[i]+=1e-6;minus[i]-=1e-6
                fd=(np.array(model.evaluate(plus)[1]).ravel()-np.array(model.evaluate(minus)[1]).ravel())/2e-6
                self.assertLess(np.max(abs(fd-jac[:,i])/(1+abs(fd))),1e-5,(moving,i))


if __name__=='__main__':unittest.main(verbosity=2)
