from time import monotonic
import json
import unittest
import numpy as np
import replay


def native(point):return float(point@point),2*point


class TestReplay(unittest.TestCase):
    def test_matches_inner_solve_trial_order(self):
        # f=x^2 with a deliberately small model Hessian 0.01: the boundary trial is rejected, the shrunken one accepted.
        y=np.array([.5]);H=np.array([[.01]]);f,g=native(y)
        rows=replay.replay(native,H,y,f,g,1.)
        self.assertEqual([r['legacy_accepted'] for r in rows],[False,True])
        trace=[]
        replay.onesided.inner.solve(lambda p,d:(*native(p),None),lambda p,c:H,y.copy(),monotonic()+5,trace.append)
        accepted=next(r for r in trace if r['kind']=='accepted')
        self.assertEqual(accepted['y'],(y+np.array([-rows[1]['step_norm']])).tolist())
        self.assertEqual(accepted['ratio'],rows[1]['legacy_ratio'])

    def test_stops_when_radius_collapses(self):
        # The model predicts decrease along a direction where the function increases: every trial is rejected.
        y=np.array([.5]);g=np.array([1.]);H=np.array([[1.]])
        rows=replay.replay(lambda p:(10.+float(p[0])**2+5*float(abs(p[0]-.5)),np.array([1.])),H,y,10.25,g,1.)
        self.assertFalse(any(r['legacy_accepted'] for r in rows));self.assertLess(rows[-1]['next_radius'],1e-14)

    def test_precise_ratio_and_verdict(self):
        self.assertIsNone(replay.precise_ratio(1.,0.));self.assertEqual(replay.precise_ratio(1.,4.),.25)
        base=dict(legacy_accepted=False)
        self.assertEqual(replay.verdict([dict(base,precise_ratio=None),dict(base,precise_ratio=2e-4)]),'acceptance_rule')
        self.assertEqual(replay.verdict([dict(base,precise_ratio=5e-5),dict(base,precise_ratio=None)]),'model')
        self.assertEqual(replay.verdict([dict(legacy_accepted=True,precise_ratio=1.)]),'replay_disagrees')

    def test_relative_gap(self):
        self.assertEqual(replay.relative_gap(2.,1.),1.);self.assertAlmostEqual(replay.relative_gap(1e6+1,1e6),1e-6)


if __name__=='__main__':unittest.main()
