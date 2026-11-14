"""Resume the AL from a saved state of ../2026-11-14-reproduction with the Newton inner solver.

Answers: from the same failed state (y, multipliers, rho), does the final-stage AL reach the
KKT tolerances once the inner problems are solved accurately?
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

import newton_al as na

a = argparse.ArgumentParser(description=__doc__)
a.add_argument('diagnostic', help='JSON written by independent_al.py')
a.add_argument('--library', required=True)
a.add_argument('--stage', type=int, default=-1, help='index into stage_states')
a.add_argument('--outer', type=int, default=10)
a.add_argument('--inner', type=int, default=300)
a.add_argument('--rho', type=float, help='override the saved penalty')
a.add_argument('--freeze-rho', action='store_true')
a.add_argument('--spectrum', action='store_true')
args = a.parse_args()

doc = json.loads(Path(args.diagnostic).read_text())
ex = doc['experiment']
arg = ex['arguments']
states = ex['stage_states']
index = args.stage % len(states)
st = states[index]
stage = arg['start_stage'] + index
m = na.Model(arg['tau'], arg['seed'], args.library)
eps, p = max(.0005, .2 * .6**stage), min(12., 2. * 1.2**stage)
m.stage(eps, p)
y, lam, mu = (np.array(st[k]) for k in ('y', 'lam', 'mu'))
rho = args.rho or st['rho']
ns = m.stamps - 1
print(f'stage {stage+1} eps {eps:.2e} p {p:.2f} rho {rho:.1e} n {m.n}', na.kkt(m, y, lam, mu))
previous = np.inf
for outer in range(args.outer):
    r = na.tr_newton(lambda q: m.eval(q, lam, mu, rho), y, max_iter=args.inner)
    y = np.ascontiguousarray(r['y'])
    if args.spectrum:
        w = np.linalg.eigvalsh(na.fd_hessian(lambda q: m.eval(q, lam, mu, rho)[1], y))
        print('   spectrum', np.array2string(w, precision=2, max_line_width=250))
    m.eval(y, lam, mu, 0.)
    lam = lam + rho * m.h
    mu = np.maximum(0., mu + rho * m.g)
    k = na.kkt(m, y, lam, mu)
    task, mode = na.degeneracy(m, y)
    print(f'{outer+1:>2} rho {rho:.0e} f {float(m.objective[0]):.6f} stat {k["stat"]:.1e} feas {k["feas"]:.1e} '
          f'comp {k["comp"]:.1e} {r["status"]} n{r["iters"]} eig[{r["eig"][0]:.1e},{r["eig"][1]:.1e}] '
          f'lam t{np.abs(lam[ns:m.me-ns]).max():.1e} m{np.abs(lam[m.me-ns:]).max():.1e} '
          f'|dh| t{task:.1e} m{mode:.1e}', flush=True)
    if all(v <= 1e-6 for v in k.values()):
        print('KKT reached')
        break
    v = max(k['feas'], k['comp'])
    if v > .25 * previous and not args.freeze_rho:
        rho = min(rho * 10, 1e8)
    previous = v
