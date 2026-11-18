"""Independent recomputation (does not import carrier_certificate): segment-wise, numpy."""
import csv
import json
import numpy as np
from common import ROOT, HERE, read, sha

TOL = 1e-9
index = read(HERE/'source-index.json')
saved = {r['case']: r for r in csv.DictReader(open(HERE/'cases.csv'))}
summary = read(HERE/'summary.json')
assert summary['source_index_sha256'] == sha(HERE/'source-index.json')
mismatch, checked, late = [], 0, 0
for p in index['points']:
    d = read(ROOT/p['path']); assert sha(ROOT/p['path']) == p['sha256']
    r = np.array(d['solution']['r'], float); s = np.array(d['solution']['s'], float); c = np.array(d['solution']['c'], float)
    m = np.array(d['modes']); vc = d['phys']['v_c']
    assert np.all(np.where(m < 0, np.abs(c), np.abs(c-s)) <= 1e-12)
    start = np.r_[0., np.cumsum(s)[:-1]]; end = np.cumsum(s)
    worst = 0.; region_max = 0.
    for j, reg in enumerate(d['instance']['regions']):
        seg = np.flatnonzero(m == j)
        for k in seg:  # moving with the UAV inside a charging segment
            worst = max(worst, np.hypot(*(r[k+1]-r[k])) - vc*s[k])
            for q in (r[k], r[k+1]):
                region_max = max(region_max, np.hypot(*(q-np.array(reg['o']))) - reg['rho'])
        for a, b in zip(seg, seg[1:]):  # leave at the end of a, meet at the start of b
            worst = max(worst, np.hypot(*(r[b]-r[a+1])) - vc*(start[b]-end[a]))
    assert region_max <= 1e-6
    status = 'carrier_late' if worst > TOL else ('feasible' if region_max <= TOL else 'region_tolerance_only')
    late += status == 'carrier_late'
    row = saved[p['case']]
    if row['status'] != status or abs(max(worst, 0.) - float(row['max_excess_km'])) > 1e-12:
        mismatch.append((p['case'], row['status'], status, row['max_excess_km'], worst))
    checked += 1
assert late == summary['all']['carrier_late']
out = dict(checked=checked, carrier_late=late, mismatches=mismatch, tolerance_km=TOL,
           method='segment-wise numpy recomputation, no import of scripts/carrier_certificate.py')
(HERE/'verification.json').write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1)[:2000])
assert not mismatch
