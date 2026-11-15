"""Controlled changes of row scaling, speed representation, variable scaling and budget."""
import gzip
import importlib.util
import json
from pathlib import Path
from time import monotonic

import numpy as np
from scipy.optimize import minimize

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SPEC = importlib.util.spec_from_file_location('trace_helpers', HERE.parent/'2026-11-15-library-trace/trace.py')
tr = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tr)
LIB = {'normalized': '/tmp/uav-fidelity-speed.so', 'original': '/tmp/uav-fidelity-original.so'}
SEED = HERE.parent/'2026-11-14-resume/fixed-modes/default-fig1-fixed-modes.json'


class Variant:
    def __init__(self, kind):
        assert kind in ['N', 'R', 'Q', 'U']
        self.kind = kind
        self.native = tr.Model(0, 0, LIB['normalized' if kind in ['N', 'R'] else 'original'])
        self.reference = tr.Model(0, 0, LIB['original'])
        self.n, self.me, self.mi, self.stamps = (getattr(self.native, key) for key in ['n', 'me', 'mi', 'stamps'])
        self.scale = self.native.scale.copy() if kind != 'U' else np.ones(self.n)
        self.ratio = self.scale/self.native.scale
        ns = self.stamps-1
        self.raw_h = np.r_[np.full(ns, 1/14.4), np.ones(self.me-ns)]
        self.raw_g = np.r_[np.ones(ns), np.full(2*ns, 1/14.4), np.full(3*ns, 1/36)]
        self.wh = np.ones(self.me) if kind == 'N' else self.raw_h.copy()
        self.wg = np.ones(self.mi) if kind == 'N' else self.raw_g.copy()
        self.source = json.loads(SEED.read_text())
        template = self.native.solution(self.native.y)
        assert self.source['instance'] == template['instance'] and self.source['phys'] == template['phys']
        trajectory = self.source['solution']
        self.x0 = np.r_[np.array(trajectory['r'][1:-1]).ravel(), trajectory['e'][1:], trajectory['s'], trajectory['c']]
        self.y0 = np.ascontiguousarray(self.x0/self.scale)
        self.h, self.g = np.zeros(self.me), np.zeros(self.mi)

    def stage(self, eps, p):
        self.eps, self.p = eps, p
        self.native.stage(eps, p)
        self.reference.stage(eps, p)

    def eval(self, y, lam, mu, rho):
        q = np.ascontiguousarray(y*self.ratio)
        if self.kind == 'N':
            value, gradient = self.native.eval(q, lam, mu, rho)
            self.h, self.g = self.native.h.copy(), self.native.g.copy()
            return value, gradient*self.ratio
        self.native.eval(q, np.zeros(self.me), np.zeros(self.mi), 0.)
        objective = float(self.native.objective[0])
        h, g = self.native.h*self.wh, self.native.g*self.wg
        ih = lam + rho*h
        ig = np.maximum(0., mu+rho*g) if rho else mu
        _, gradient = self.native.eval(q, np.ascontiguousarray(self.wh*ih), np.ascontiguousarray(self.wg*ig), 0.)
        value = objective + lam@h
        if rho:
            value += .5*rho*(h@h) + ((ig@ig)-(mu@mu))/(2*rho)
        else:
            value += mu@g
        self.h, self.g = h.copy(), g.copy()
        return float(value), gradient*self.ratio

    def jacobian(self, y):
        jac = self.native.jacobian(np.ascontiguousarray(y*self.ratio))
        return jac*np.r_[self.wh, self.wg][:, None]*self.ratio

    def reference_state(self, y, lam, mu):
        q = np.ascontiguousarray(y*self.scale/self.reference.scale)
        le, mi = lam*self.wh, mu*self.wg
        if self.kind in ['N', 'R']:
            mi = tr.original_multipliers(self, y, self.source, mi)
        return q, np.ascontiguousarray(le), np.ascontiguousarray(mi)

    def metrics(self, y, lam, mu):
        q, le, mi = self.reference_state(y, lam, mu)
        self.reference.eval(q, le, mi, 0.)
        r = self.reference
        common = dict(stat=float(max(abs(r.grad))), feas=float(max(max(abs(r.h)), max(r.g), 0.)),
                      comp=float(max(abs(np.minimum(mi, -r.g)))), dual=float(max(0., -min(mi))))
        hg, gg, paper_mu = r.h*self.raw_h, r.g*self.raw_g, mi/self.raw_g
        paper = dict(stat=float(max(abs(r.grad/r.scale))), feas=float(max(max(abs(hg)), max(gg), 0.)),
                     comp=float(max(abs(np.minimum(paper_mu, -gg)))), dual=float(max(0., -min(paper_mu))))
        return dict(common_kkt=common, paper_units_kkt=paper,
                    objective=float(r.objective[0]))

    def close(self):
        self.native.close()
        self.reference.close()


def inner(model, y, lam, mu, deadline):
    last, count, iters = y.copy(), 0, 0
    def fg(point):
        nonlocal count
        if monotonic() > deadline:
            raise TimeoutError()
        count += 1
        return model.eval(np.ascontiguousarray(point), lam, mu, 1e4)
    def callback(point):
        nonlocal last, iters
        last = point.copy()
        iters += 1
    start = monotonic()
    try:
        result = minimize(fg, y, jac=True, method='BFGS', callback=callback, options=dict(gtol=1e-8, maxiter=2000))
        point = np.ascontiguousarray(result.x)
        status, success, interrupted = str(result.message), bool(result.success), False
        iters = int(result.nit)
    except TimeoutError:
        point, status, success, interrupted = last, 'timeout; last accepted inner iterate', False, True
    value, gradient = model.eval(point, lam, mu, 1e4)
    return point, dict(value=value, gradient_inf=float(max(abs(gradient))), status=status,
        solver_success=success, gradient_pass=bool(max(abs(gradient)) <= 1e-8), iterations=iters,
        evaluations=count, seconds=monotonic()-start, interrupted=interrupted)


def state(y, lam, mu, stage, eps, p):
    return dict(y=y.tolist(), lam=lam.tolist(), mu=mu.tolist(), rho=1e4, stage=stage, eps=eps, p=p)


def solve(kind, budget, resume=False):
    folder = HERE/'cases'/(kind+'-'+budget)
    if not resume:
        folder.mkdir(parents=True, exist_ok=False)
    model = Variant(kind)
    y, lam, mu = model.y0.copy(), np.zeros(model.me), np.zeros(model.mi)
    if not resume:
        tr.write(folder/'initial.json', dict(**state(y, lam, mu, 1, .2, 2.), scale=model.scale.tolist(),
            wh=model.wh.tolist(), wg=model.wg.tolist(), physical_variables=model.x0.tolist(), kind=kind, budget=budget))
    start, rows, stages, stop, prior_rows, first_stage = monotonic(), [], [], 'outer_limit', 0, 1
    if resume:
        checkpoint = json.loads((folder/'checkpoint.json').read_text())
        y, lam, mu = (np.array(checkpoint[k]) for k in ['y', 'lam', 'mu'])
        stages, prior_rows = checkpoint['stages'], checkpoint['total_outer']
        first_stage = checkpoint['stage']+1
        start -= checkpoint['elapsed']
        assert first_stage <= 13, 'this recovery resumes only before the final stage'
    with gzip.open(folder/'outer.jsonl.gz', 'at' if resume else 'wt') as log:
        for stage in range(first_stage, 14):
            eps, p = max(.0005, .2*.6**(stage-1)), min(12., 2.*1.2**(stage-1))
            model.stage(eps, p)
            entry = dict(**state(y, lam, mu, stage, eps, p), **model.metrics(y, lam, mu),
                         selection=tr.describe(model, y, model.source, eps, p))
            tr.write(folder/f'stage{stage:02d}-start.json', entry)
            limit = (30 if stage == 13 else 10) if budget == 'short' else (300 if stage == 13 else 100)
            completed = 0
            for outer in range(limit):
                if monotonic()-start >= 90:
                    stop = 'timeout'
                    break
                point, info = inner(model, y, lam, mu, start+90)
                if info['interrupted']:
                    tr.write(folder/'interrupted-inner.json', dict(y=point.tolist(), **info))
                    stop = 'timeout'
                    break
                y = point
                model.eval(y, lam, mu, 0.)
                lam += 1e4*model.h
                mu = np.maximum(0., mu+1e4*model.g)
                row = dict(**state(y, lam, mu, stage, eps, p), outer=outer+1, **model.metrics(y, lam, mu),
                    inner=info, selection=tr.describe(model, y, model.source, eps, p), elapsed=monotonic()-start)
                completed += 1
                rows.append(row)
                log.write(json.dumps(row, allow_nan=False)+'\n')
                log.flush()
                if max(row['common_kkt'].values()) <= 1e-6:
                    if stage == 13:
                        stop = 'kkt'
                    break
            final = dict(**state(y, lam, mu, stage, eps, p), **model.metrics(y, lam, mu),
                         selection=tr.describe(model, y, model.source, eps, p))
            passed = max(final['common_kkt'].values()) <= 1e-6
            stages.append(dict(stage=stage, completed_outer=completed, budget=limit, common_kkt_pass=passed,
                common_kkt=final['common_kkt'], paper_units_kkt=final['paper_units_kkt'], objective=final['objective']))
            tr.write(folder/f'stage{stage:02d}-end.json', final)
            tr.write(folder/'checkpoint.json', dict(**final, kind=kind, budget_kind=budget, stages=stages,
                total_outer=prior_rows+len(rows), elapsed=monotonic()-start))
            print(json.dumps(dict(kind=kind, budget_kind=budget, **stages[-1], elapsed=monotonic()-start)), flush=True)
            if stop in ['timeout', 'kkt']:
                break
    final.update(kind=kind, budget=budget, stop=stop, seconds=monotonic()-start, total_outer=prior_rows+len(rows), stages=stages,
        reached_final=stage == 13, completed_schedule=bool(stage == 13 and stop != 'timeout'),
        final_kkt_pass=bool(stage == 13 and stop != 'timeout' and max(final['common_kkt'].values()) <= 1e-6),
        passed_stages=sum(s['common_kkt_pass'] for s in stages))
    tr.write(folder/'result.json', final)
    q = np.ascontiguousarray(y*model.scale/model.reference.scale)
    doc = model.reference.solution(q)
    doc['init'] = model.source['solution']
    doc['metrics'].update(converged=final['final_kkt_pass'], seconds=final['seconds'],
        init_objective=model.source['metrics']['objective'])
    doc['experiment'] = dict(kind=kind, budget=budget, paper_algorithm=False, stop=stop,
        y_full_precision=q.tolist(), variant_y=y.tolist(), variant_scale=model.scale.tolist(),
        final_common_kkt=final['common_kkt'], final_paper_units_kkt=final['paper_units_kkt'])
    tr.write(folder/'solution.json', doc)
    model.close()


if __name__ == '__main__':
    import sys
    resume = sys.argv[1:] == ['--resume']
    assert not sys.argv[1:] or resume
    assert resume or not (HERE/'cases').exists(), 'refuse to overwrite an experiment'
    for kind in ['N', 'R', 'Q', 'U']:
        for budget in ['short', 'expanded']:
            folder = HERE/'cases'/(kind+'-'+budget)
            if resume and (folder/'result.json').exists():
                continue
            solve(kind, budget, resume=resume and folder.exists())
