"""AL with an (almost) exact inner solver, to separate inner-solver stagnation from AL/model effects.

Uses the unchanged Rust model through the C ABI bridge of ../2026-11-14-reproduction.
The inner solver is a trust-region Newton method with a finite-difference Hessian of the
analytic gradient and an exact eigenvalue-based subproblem solve. It is a diagnostic tool,
not the paper's L-BFGS. Needs NumPy/SciPy.
"""

import argparse
import json
import sys
from pathlib import Path
from time import monotonic

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / '2026-11-14-reproduction'))
from independent_al import Model  # noqa: E402


def fd_hessian(grad, y, step=1e-6):
    n = len(y)
    H = np.empty((n, n))
    for i in range(n):
        e = np.zeros(n)
        e[i] = step
        H[:, i] = (grad(y + e) - grad(y - e)) / (2 * step)
    return (H + H.T) / 2


def tr_step(w, V, g, delta):
    """Minimiser of g.p + p.H.p/2 over |p| <= delta, with H = V diag(w) V^T."""
    gt = V.T @ g
    if w[0] > 0:
        p = -gt / w
        if np.linalg.norm(p) <= delta:
            return V @ p, False
    lo = max(0.0, -w[0]) + 1e-14 * max(1.0, abs(w[0]))
    hi = max(lo * 2, 1.0)
    norm = lambda sig: np.linalg.norm(gt / (w + sig))
    if norm(lo) <= delta:  # hard case: move along the lowest eigenvector to the boundary
        p = -gt / (w + lo)
        t = np.sqrt(max(delta**2 - p @ p, 0.0))
        p[0] += t if gt[0] <= 0 else -t
        return V @ p, True
    while norm(hi) > delta:
        hi *= 4
    for _ in range(200):
        mid = np.sqrt(lo * hi) if lo > 0 else (lo + hi) / 2
        if norm(mid) > delta:
            lo = mid
        else:
            hi = mid
        if hi - lo <= 1e-12 * hi:
            break
    return V @ (-gt / (w + hi)), True


def tr_newton(fg, y, gtol=1e-6, max_iter=200, delta=1.0):
    f, g = fg(y)
    evals, status = 1, 'max_iter'
    grad = lambda p: fg(p)[1]
    w = None
    for it in range(max_iter):
        if np.max(np.abs(g)) <= gtol:
            status = 'converged'
            break
        H = fd_hessian(grad, y)
        evals += 2 * len(y)
        w, V = np.linalg.eigh(H)
        accepted = False
        for _ in range(60):
            p, boundary = tr_step(w, V, g, delta)
            pred = -(g @ p + 0.5 * p @ H @ p)
            fn, gn = fg(y + p)
            evals += 1
            # Near the solution f - fn is lost to rounding; fall back to the gradient norm.
            if pred <= 1e-13 * max(1.0, abs(f)):
                ok = np.linalg.norm(gn) < np.linalg.norm(g)
                ratio = 1.0 if ok else 0.0
            else:
                ratio = (f - fn) / pred
            if ratio < 0.25:
                delta = 0.25 * np.linalg.norm(p)
            elif ratio > 0.75 and boundary:
                delta = min(2 * delta, 1e3)
            if ratio > 1e-4:
                y, f, g, accepted = y + p, fn, gn, True
                break
            if delta < 1e-14:
                break
        if not accepted:
            status = 'stuck'
            break
    else:
        it = max_iter
    return dict(y=y, f=f, g=g, iters=it, evals=evals, status=status,
                eig=None if w is None else (float(w[0]), float(w[-1])))


def kkt(model, y, lam, mu):
    model.eval(y, lam, mu, 0.0)
    return dict(stat=float(np.max(np.abs(model.grad))),
                feas=float(max(np.max(np.abs(model.h)), np.max(model.g), 0.0)),
                comp=float(np.max(np.abs(np.minimum(mu, -model.g)))))


def degeneracy(model, y):
    """Smallest gradient norm (scaled variables) among task and mode equalities."""
    jac = model.jacobian(y)
    ns = model.stamps - 1
    norms = np.linalg.norm(jac, axis=1)
    task = norms[ns:model.me - ns]
    mode = norms[model.me - ns:model.me]
    return float(task.min()), float(mode.min())


def solve(args):
    model = Model(args.tau, args.seed, args.library)
    y = model.y.copy()
    lam, mu, rho = np.zeros(model.me), np.zeros(model.mi), args.rho0
    rows, start, total_evals = [], monotonic(), 0
    ns = model.stamps - 1
    out = open(args.out, 'w') if args.out else None
    for stage in range(args.start_stage, args.start_stage + args.stages):
        eps, p = max(.0005, .2 * .6**stage), min(12., 2. * 1.2**stage)
        model.stage(eps, p)
        if args.reset:
            lam, mu, rho = np.zeros(model.me), np.zeros(model.mi), args.rho0
        previous = np.inf
        last = stage + 1 == args.start_stage + args.stages
        for outer in range(args.final_outer if last else args.outer):
            if args.backend == 'rust':
                # The repository's own L-BFGS, called on the same model through the bridge.
                result = np.empty(5)
                y = np.ascontiguousarray(y)
                model.lib.uav_rust_inner(model.ctx, model.ptr(y), model.ptr(lam), model.ptr(mu),
                                         rho, args.inner, model.ptr(result))
                res = dict(y=y, status=('converged', 'max_iter', 'stalled', 'line_search')[int(result[4])],
                           iters=int(result[2]), evals=int(result[3]), eig=None)
            else:
                res = tr_newton(lambda q: model.eval(q, lam, mu, rho), y, gtol=args.gtol,
                                max_iter=args.inner)
            y = np.ascontiguousarray(res['y'])
            total_evals += res['evals']
            model.eval(y, lam, mu, 0.0)
            lam = lam + rho * model.h
            mu = np.maximum(0.0, mu + rho * model.g)
            k = kkt(model, y, lam, mu)
            task, mode = degeneracy(model, y)
            row = dict(stage=stage + 1, outer=outer + 1, eps=eps, p=p, rho=rho,
                       objective=float(model.objective[0]), **k,
                       inner=res['status'], iters=res['iters'], evals=res['evals'],
                       eig_min=res['eig'][0] if res['eig'] else None,
                       eig_max=res['eig'][1] if res['eig'] else None,
                       lam_task=float(np.max(np.abs(lam[ns:model.me - ns]))),
                       lam_mode=float(np.max(np.abs(lam[model.me - ns:]))),
                       grad_task=task, grad_mode=mode, elapsed=monotonic() - start)
            row['converged'] = all(k[v] <= args.tol for v in ('stat', 'feas', 'comp'))
            rows.append(row)
            if out:
                out.write(json.dumps(row) + '\n')
                out.flush()
            if args.verbose:
                print('st{stage:>2} it{outer:>2} rho {rho:.0e} f {objective:.6f} stat {stat:.1e} feas {feas:.1e} '
                      'comp {comp:.1e} {inner} n{iters} eig[{eig_min:.1e},{eig_max:.1e}] '
                      'lam t{lam_task:.1e} m{lam_mode:.1e} |dh| t{grad_task:.1e} m{grad_mode:.1e}'.format(**{
                          **row, 'eig_min': row['eig_min'] or 0, 'eig_max': row['eig_max'] or 0}), flush=True)
            if row['converged']:
                break
            violation = max(k['feas'], k['comp'])
            if violation > .25 * previous:
                rho = min(rho * args.rho_mult, args.rho_max)
            previous = violation
            if monotonic() - start > args.timeout:
                break
        if not args.verbose:
            print(json.dumps(rows[-1]), flush=True)
        if monotonic() - start > args.timeout:
            break
    if args.state:
        np.savez(args.state, y=y, lam=lam, mu=mu, rho=rho)
    if args.summary:
        sol = model.solution(y)
        keep = ('objective', 'viol', 'viol_task', 'viol_mode', 'viol_dyn', 'viol_speed', 'viol_bounds')
        final = rows[-1]
        Path(args.summary).write_text(json.dumps(dict(
            tau=args.tau, seed=args.seed, backend=args.backend, stamps=model.stamps, variables=model.n,
            reached_final_stage=final['stage'] == args.start_stage + args.stages,
            kkt_converged=bool(final['converged'] and final['stage'] == args.start_stage + args.stages),
            stat=final['stat'], feas=final['feas'], comp=final['comp'], rho=final['rho'],
            lam_task=final['lam_task'], lam_mode=final['lam_mode'],
            outer_total=len(rows), evals=total_evals, seconds=monotonic() - start,
            timed_out=monotonic() - start > args.timeout, modes=sol['modes'],
            metrics={k: sol['metrics'][k] for k in keep}, arguments=vars(args),
            y=y.tolist(), lam=lam.tolist(), mu=mu.tolist())) + '\n')
    model.close()
    return rows


if __name__ == '__main__':
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument('--tau', type=int, default=1, help='0 selects fig1')
    a.add_argument('--seed', type=int, default=0)
    a.add_argument('--library', required=True)
    a.add_argument('--stages', type=int, default=13)
    a.add_argument('--start-stage', type=int, default=0)
    a.add_argument('--outer', type=int, default=10)
    a.add_argument('--final-outer', type=int, default=30)
    a.add_argument('--inner', type=int, default=200)
    a.add_argument('--gtol', type=float, default=1e-6)
    a.add_argument('--tol', type=float, default=1e-6)
    a.add_argument('--rho0', type=float, default=10.)
    a.add_argument('--rho-mult', type=float, default=10.)
    a.add_argument('--rho-max', type=float, default=1e8)
    a.add_argument('--timeout', type=float, default=600.)
    a.add_argument('--reset', action='store_true')
    a.add_argument('--verbose', action='store_true')
    a.add_argument('--out')
    a.add_argument('--state')
    a.add_argument('--summary')
    a.add_argument('--backend', choices=['newton', 'rust'], default='newton')
    solve(a.parse_args())
