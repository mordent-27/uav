"""Four prespecified continuations from the same updated stage-2 state."""
import gzip
import json
from time import monotonic

import numpy as np
from scipy.optimize import minimize
import common as c


def next_penalty(rho, violation, previous, passed, policy):
    eligible = policy == 'adaptive' or (policy == 'guarded' and violation > 1e-6)
    return min(1e8, rho*10) if eligible and not passed and violation > .25*previous else rho


def inner(m, y, lam, mu, rho, method, deadline):
    last, evaluations, iterations = y.copy(), 0, 0
    def fg(point):
        nonlocal evaluations
        if monotonic() > deadline:
            raise TimeoutError()
        evaluations += 1
        return m.eval(np.ascontiguousarray(point), lam, mu, rho)
    def callback(point):
        nonlocal last, iterations
        last = point.copy()
        iterations += 1
    start = monotonic()
    try:
        if method == 'newton':
            res = c.newton.tr_newton(fg, y.copy(), gtol=1e-8, max_iter=300, hessian_step=1e-7)
            point = np.ascontiguousarray(res['y'])
            status, success, iterations = res['status'], res['status'] == 'converged', int(res['iters'])
        else:
            res = minimize(fg, y, jac=True, method='BFGS', callback=callback, options=dict(gtol=1e-8, maxiter=2000))
            point = np.ascontiguousarray(res.x)
            status, success, iterations = str(res.message), bool(res.success), int(res.nit)
        interrupted = False
    except TimeoutError:
        point, status, success, interrupted = last, 'timeout; last accepted BFGS iterate or Newton input', False, True
    value, gradient = m.eval(point, lam, mu, rho)
    return point, dict(value=value, gradient_inf=float(max(abs(gradient))), gradient_pass=bool(max(abs(gradient)) <= 1e-8),
        status=status, solver_success=success, iterations=iterations, evaluations=evaluations,
        seconds=monotonic()-start, interrupted=interrupted)


def export(folder, m, y, lam, mu, rho, records, stop, elapsed, name, final_required=False):
    metrics = c.assess(m, y, lam, mu)
    passed = max(metrics['common_kkt'].values()) <= 1e-6
    result = dict(**c.state(y, lam, mu, rho, m.current_stage, m.eps, m.p), **metrics,
        name=name, stop=stop, additional_outer=len(records), seconds=elapsed,
        target_kkt_pass=passed, final_kkt_pass=bool(final_required and m.current_stage == 13 and passed))
    c.write(folder/'result.json', result)
    q = np.ascontiguousarray(y*m.scale/m.reference.scale)
    doc = m.reference.solution(q)
    initial = json.loads((folder/'initial.json').read_text())
    doc['init'] = c.fidelity.tr.decode(m, np.array(initial['y']), m.source)
    doc['metrics'].update(converged=result['final_kkt_pass'], seconds=elapsed, init_objective=sum(doc['init']['s']))
    doc['experiment'] = dict(name=name, stage=m.current_stage, paper_algorithm=False, stop=stop,
        y_full_precision=q.tolist(), variant_y=y.tolist(), lam=lam.tolist(), mu=mu.tolist(), rho=rho,
        common_kkt=result['common_kkt'], paper_units_kkt=result['paper_units_kkt'])
    c.write(folder/'solution.json', doc)
    print(json.dumps({k: result[k] for k in ['name', 'stage', 'stop', 'target_kkt_pass', 'final_kkt_pass', 'additional_outer', 'seconds', 'common_kkt']}), flush=True)
    return result


def run(name):
    _, saved = c.source()
    folder = c.HERE/'cases'/name
    folder.mkdir(parents=True, exist_ok=False)
    m = c.model()
    m.current_stage = 2
    y, lam, mu = (np.array(saved[k]) for k in ['y', 'lam', 'mu'])
    rho = 1e5 if name == 'raised-bfgs' else 1e4
    method = 'newton' if name == 'fixed-newton' else 'bfgs'
    policy = 'guarded' if name == 'guarded-bfgs' else ('adaptive' if name == 'adaptive-bfgs' else 'fixed')
    c.write(folder/'initial.json', dict(**c.state(y, lam, mu, rho), method=method,
        policy=policy, parent_outer=100))
    start, records, stop, previous = monotonic(), [], 'outer_limit', np.inf
    with gzip.open(folder/'outer.jsonl.gz', 'wt') as log:
        for extra in range(200):
            if monotonic()-start >= 90:
                stop = 'timeout'
                break
            point, info = inner(m, y, lam, mu, rho, method, start+90)
            if info['interrupted']:
                c.write(folder/'interrupted-inner.json', dict(y=point.tolist(), **info))
                stop = 'timeout'
                break
            y = point
            m.eval(y, lam, mu, 0.)
            lam += rho*m.h
            mu = np.maximum(0., mu+rho*m.g)
            metrics = c.assess(m, y, lam, mu)
            violation = max(metrics['common_kkt']['feas'], metrics['common_kkt']['comp'])
            passed = max(metrics['common_kkt'].values()) <= 1e-6
            next_rho = next_penalty(rho, violation, previous, passed, policy)
            row = dict(**c.state(y, lam, mu, rho), extra_outer=extra+1, phase_outer=101+extra,
                **metrics, inner=info, rho_next=next_rho, previous_violation=None if not np.isfinite(previous) else previous,
                violation=violation, elapsed=monotonic()-start)
            records.append(row)
            log.write(json.dumps(row, allow_nan=False)+'\n')
            log.flush()
            c.write(folder/'checkpoint.json', row)
            if extra % 25 == 0:
                print(json.dumps(dict(name=name, extra_outer=extra+1, rho=rho, common_kkt=row['common_kkt'], elapsed=monotonic()-start)), flush=True)
            if passed:
                stop = 'kkt'
                break
            previous, rho = violation, next_rho
    result = export(folder, m, y, lam, mu, rho, records, stop, monotonic()-start, name)
    m.close()
    return result


def follow_adaptive(name='adaptive-bfgs'):
    parent_path = c.HERE/'cases'/name/'result.json'
    parent = json.loads(parent_path.read_text())
    if not parent['target_kkt_pass']:
        c.write(c.HERE/('follow-guarded-skipped.json' if name == 'guarded-bfgs' else 'follow-skipped.json'),
            dict(reason='prespecified stage-2 continuation did not pass KKT', parent=name))
        return
    policy = 'guarded' if name == 'guarded-bfgs' else 'adaptive'
    label = 'follow-guarded' if name == 'guarded-bfgs' else 'follow'
    folder = c.HERE/label
    folder.mkdir(exist_ok=False)
    y, lam, mu = (np.array(parent[k]) for k in ['y', 'lam', 'mu'])
    rho = parent['rho']
    m = c.model()
    c.write(folder/'initial.json', dict(**c.state(y, lam, mu, rho), parent=f'cases/{name}/result.json', policy=policy))
    start, records, stage_summaries, stop = monotonic(), [], [], 'outer_limit'
    with gzip.open(folder/'outer.jsonl.gz', 'wt') as log:
        for stage in range(3, 14):
            eps, p = max(.0005, .2*.6**(stage-1)), min(12., 2.*1.2**(stage-1))
            m.stage(eps, p)
            m.current_stage = stage
            previous, passed, completed = np.inf, False, 0
            c.write(folder/f'stage{stage:02d}-start.json', c.state(y, lam, mu, rho, stage, eps, p))
            for outer in range(600 if stage == 13 else 200):
                if monotonic()-start >= 300:
                    stop = 'timeout'
                    break
                point, info = inner(m, y, lam, mu, rho, 'bfgs', start+300)
                if info['interrupted']:
                    c.write(folder/'interrupted-inner.json', dict(y=point.tolist(), **info))
                    stop = 'timeout'
                    break
                y = point
                m.eval(y, lam, mu, 0.)
                lam += rho*m.h
                mu = np.maximum(0., mu+rho*m.g)
                metrics = c.assess(m, y, lam, mu)
                passed = max(metrics['common_kkt'].values()) <= 1e-6
                violation = max(metrics['common_kkt']['feas'], metrics['common_kkt']['comp'])
                next_rho = next_penalty(rho, violation, previous, passed, policy)
                row = dict(**c.state(y, lam, mu, rho, stage, eps, p), outer=outer+1, **metrics, inner=info,
                    rho_next=next_rho, previous_violation=None if not np.isfinite(previous) else previous,
                    violation=violation, elapsed=monotonic()-start)
                records.append(row)
                log.write(json.dumps(row, allow_nan=False)+'\n')
                log.flush()
                c.write(folder/'checkpoint.json', row)
                completed += 1
                previous, rho = violation, next_rho
                if passed:
                    break
            stage_summaries.append(dict(stage=stage, passed=passed, completed_outer=completed,
                **m.metrics(y, lam, mu)))
            c.write(folder/f'stage{stage:02d}-end.json', dict(**c.state(y, lam, mu, rho, stage, eps, p), **c.assess(m, y, lam, mu)))
            print(json.dumps(dict(name=label, **stage_summaries[-1], elapsed=monotonic()-start)), flush=True)
            if not passed:
                if stop != 'timeout':
                    stop = 'stage_limit'
                break
            if stage == 13:
                stop = 'kkt'
    result = export(folder, m, y, lam, mu, rho, records, stop, monotonic()-start, label, final_required=True)
    result['stages'] = stage_summaries
    c.write(folder/'result.json', result)
    m.close()


if __name__ == '__main__':
    import sys
    if sys.argv[1:] == ['--guarded']:
        run('guarded-bfgs')
        follow_adaptive('guarded-bfgs')
    else:
        assert not sys.argv[1:]
        assert not (c.HERE/'cases').exists(), 'refuse to overwrite a continuation'
        for name in ['fixed-bfgs', 'fixed-newton', 'raised-bfgs', 'adaptive-bfgs']:
            run(name)
        follow_adaptive()
