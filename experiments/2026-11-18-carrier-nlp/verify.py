"""Independent check of every saved solution (no solve.py / diagnose_solution / carrier_certificate imports)."""
import json, math
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
def charge(p, e, c):
    span = p['e_max']-p['e_th']; sig = span/p['kappa']
    if e < p['e_th']:
        tt = (p['e_th']-e)/p['kappa']
        return e+p['kappa']*c if c <= tt else p['e_max']-span*math.exp(-(c-tt)/sig)
    return p['e_max']-(p['e_max']-e)*math.exp(-c/sig)

def check(d):
    p, tr, inst = d['phys'], d['solution'], d['instance']
    r = np.array(tr['r']); s = np.array(tr['s']); m = d['modes']; out = {}
    e = [p['e_max']]
    for k in range(len(s)):
        e.append(charge(p, e[-1], s[k]) if m[k] >= 0 else e[-1]-p['zeta']*s[k])
    out['energy_gap'] = float(max(abs(np.array(e)-np.array(tr['e']))))
    out['min_energy'] = min(e)
    out['tasks'] = max(float(np.linalg.norm(r[k]-np.array(a))) for a, k in zip(inst['tasks'], d['task_stamp']))
    out['endpoints'] = max(float(np.linalg.norm(r[0]-inst['r0'])), float(np.linalg.norm(r[-1]-inst['rf'])))
    sp = [np.linalg.norm(r[k+1]-r[k])-(p['v_c'] if m[k] >= 0 else p['v_d'])*s[k] for k in range(len(s))]
    out['uav_speed'] = float(max(sp)); out['s_bounds'] = float(max(max(p['s_min']-s), max(s-p['s_max'])))
    disk = [np.linalg.norm(r[k0]-inst['regions'][m[k]]['o'])-inst['regions'][m[k]]['rho'] for k in range(len(s)) if m[k] >= 0 for k0 in (k, k+1)]
    out['contact_disk'] = float(max(disk, default=0.))
    out['c_exact'] = float(max(abs(c-(s[k] if m[k] >= 0 else 0.)) for k, c in enumerate(tr['c'])))
    late = 0.  # anchor pairs from UAV points only
    for j, reg in enumerate(inst['regions']):
        seg = [k for k in range(len(s)) if m[k] == j]
        t = np.r_[0., np.cumsum(s)]
        for a, b in zip(seg, seg[1:]):
            late = max(late, float(np.linalg.norm(r[b]-r[a+1])-p['v_c']*(t[b]-t[a+1])))
    out['carrier_late_km'] = late
    if 'carrier_positions' in d:
        sq = reg_ex = cont = 0.
        for j, q in d['carrier_positions'].items():
            q = np.array(q); j = int(j); reg = inst['regions'][j]
            sq = max(sq, float(max(np.linalg.norm(q[1:]-q[:-1], axis=1)-p['v_c']*s)))
            reg_ex = max(reg_ex, float(max(np.linalg.norm(q-reg['o'], axis=1))-reg['rho']))
            cont = max([cont]+[float(np.linalg.norm(q[k0]-r[k0])) for k in range(len(s)) if m[k] == j for k0 in (k, k+1)])
        out.update(carrier_speed=sq, carrier_disk=reg_ex, carrier_contact=cont)
    return out

rows = json.loads((HERE/'results.json').read_text()); report = {}
for row in rows:
    for name in ('base', 'carrier'):
        d = json.loads((HERE/'runs'/row['case']/f'{name}.json').read_text()); c = check(d)
        ok = (c['energy_gap'] < 1e-12 and c['min_energy'] >= d['phys']['e_min'] and c['tasks'] < 1e-12 and c['endpoints'] < 1e-12
              and c['uav_speed'] <= 1e-10 and c['s_bounds'] <= 1e-11 and c['contact_disk'] <= 1e-10 and c['c_exact'] == 0.)
        if name == 'carrier':
            ok = ok and max(c['carrier_speed'], c['carrier_disk'], c['carrier_contact']) <= 1e-9 and c['carrier_late_km'] <= 1e-9
        assert ok == row[name]['accepted'], (row['case'], name, c)
        assert abs(sum(d['solution']['s'])-row[name]['objective_hours']) < 1e-12
        report[f"{row['case']}/{name}"] = dict(independent_accept=bool(ok), **{k: float(v) for k, v in c.items()})
(HERE/'verification.json').write_text(json.dumps(report, indent=1)+'\n')
print(json.dumps({k: v['independent_accept'] for k, v in report.items()}, indent=0))
