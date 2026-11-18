"""No solves: the constraint functions at the returned point agree with experiment 1."""
import json, math, sys, unittest
import numpy as np
from solve import Branch, ROOT, TARGETS, initial_carriers
sys.path.insert(0, str(ROOT/'scripts')); import carrier_certificate as carrier

index = {p['case']: p for p in json.loads((ROOT/'experiments/2026-11-18-r3s-carrier/source-index.json').read_text())['points']}
def load(c): return json.loads((ROOT/index[c]['path']).read_text())

class T(unittest.TestCase):
    def test_base_feasible_at_returned_point(self):
        for c in TARGETS:
            b = Branch(load(c), False); _, con, _, _ = b.evaluate(b.x0); con = np.array(con).ravel()
            self.assertLess(max(abs(con[:b.me])), 1e-6, c); self.assertLess(max(con[b.me:]), 1e-6, c)
    def test_carrier_violation_matches_certificate(self):
        for c in TARGETS:
            d = load(c); b = Branch(d, True); _, con, _, _ = b.evaluate(b.x0); con = np.array(con).ravel()
            cert = carrier.certify(d)
            late = max(f['excess_km'] for x in cert['carriers'] for f in x['failures'] if f['kind'] == 'unreachable')
            # interpolated carrier: worst segment excess <= worst anchor-pair excess, and > 0 when late
            self.assertGreater(max(con[b.me:]), 1e-6, c); self.assertLessEqual(max(con[b.me:]), late+1e-6, c)
    def test_initial_carrier_hits_anchors_and_stays_in_disk(self):
        d = load(TARGETS[0]); used = sorted({m for m in d['modes'] if m >= 0}); q = initial_carriers(d, used)
        for j in used:
            reg = d['instance']['regions'][j]
            for k, m in enumerate(d['modes']):
                if m == j:
                    self.assertLess(math.dist(q[j][k], d['solution']['r'][k]), 1e-12)
            self.assertLess(max(math.dist(x, reg['o']) for x in q[j]) - reg['rho'], 1e-6)

if __name__ == '__main__':
    unittest.main()
