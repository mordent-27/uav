"""Which constraint holds the feasibility plateau of a failed case. Reads saved states; solves nothing."""
import gzip
import json
import sys

import numpy as np
import helpers as h


def label(m, i, equality):
    ns = m.stamps-1
    if equality:
        if i < ns:
            return f'dynamics seg {i}'
        if i < m.me-ns:
            return f'task {i-ns}'
        return f'mode seg {i-(m.me-ns)}'
    return ['speed', 'e>=0', 'e<=1', 's>=smin', 's<=smax', 'c>=0'][i//ns]+f' seg {i % ns}'


def main():
    folder = sorted((h.HERE/'stages').glob('stage*'))[-1]
    with gzip.open(folder/'outer.jsonl.gz', 'rt') as stream:
        rows = [json.loads(line) for line in stream]
    last = rows[-1]
    f = h.stage4.Frozen(last)
    m = f.m
    y, lam, mu = (np.array(last[k]) for k in ['y', 'lam', 'mu'])
    q, le, mi = m.reference_state(y, lam, mu)
    ref = m.reference
    ref.eval(q, le, mi, 0.)
    hh, gg = ref.h.copy(), ref.g.copy()
    jac = ref.jacobian(q)
    norms = np.linalg.norm(jac, axis=1)
    report = dict(case=h.CASE, stage=last['stage'], outer=last['outer'], rho=last['rho'], common_kkt=last['common_kkt'], worst=[])
    order = np.argsort(-np.r_[abs(hh), np.maximum(gg, 0)])[:4]
    x = q*ref.scale
    ns = m.stamps-1
    s, c = x[-2*ns:-ns], x[-ns:]
    for j in order:
        eq = j < m.me
        i = j if eq else j-m.me
        value = hh[i] if eq else gg[i]
        history = [(r['lam'][i] if eq else r['mu'][i]) for r in rows[-41::10]]
        item = dict(constraint=label(m, i, eq), value=float(value), gradient_norm=float(norms[j]),
            multiplier_common=float(le[i] if eq else mi[i]), variant_multiplier_every_10_outers=history)
        if eq and i >= m.me-ns:
            k = i-(m.me-ns)
            mode = last['selection']['modes'][k]
            item.update(s_seconds=float(s[k]*3600), c_seconds=float(c[k]*3600), z=mode['z'], winner=mode['winner'],
                eps=last['eps'], p=last['p'])
        report['worst'].append(item)
    f.close()
    h.write(h.HERE/'plateau.json', report)
    print(json.dumps(report, indent=1)[:3500])


if __name__ == '__main__':
    main()
