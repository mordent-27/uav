"""Five inner solvers/value evaluations on three frozen stage-4 AL problems."""
import ctypes as ct
import gzip
import json
from time import monotonic

import numpy as np
from scipy.optimize import minimize
import support as s

METHODS = ['rust', 'scipy-lbfgs', 'scipy-bfgs', 'newton', 'stable-bfgs']
CALLBACK = ct.CFUNCTYPE(ct.c_double, ct.POINTER(ct.c_double), ct.POINTER(ct.c_double))


def solve(problem, method, state, suffix='', maxiter=None):
    folder = s.HERE/'cases'/problem/(method+suffix)
    folder.mkdir(parents=True, exist_ok=False)
    s.write(folder/'initial.json', state)
    frozen = s.Frozen(state)
    start, calls, accepted, interrupted = monotonic(), 0, 0, False
    y = frozen.anchor.copy()
    last = y.copy()
    stable = method == 'stable-bfgs'
    hessian_counts = dict(gradient_calls=0, jacobian_calls=0)
    original_fd = s.old.newton.fd_hessian
    with gzip.open(folder/'evaluations.jsonl.gz', 'wt', compresslevel=1) as log, gzip.open(folder/'accepted.jsonl.gz', 'wt', compresslevel=1) as iterlog:
        def fg(point):
            nonlocal calls
            if method != 'rust' and monotonic()-start > 45:
                raise TimeoutError()
            value, gradient = frozen.eval(point, stable=stable)
            calls += 1
            log.write(json.dumps(dict(evaluation=calls, value=value,
                gradient_inf=float(max(abs(gradient))), seconds=monotonic()-start))+'\n')
            return value, gradient
        def callback(point):
            nonlocal last, accepted
            last = point.copy()
            accepted += 1
            iterlog.write(json.dumps(dict(iteration=accepted, y=last.tolist()))+'\n')
        try:
            if method == 'rust':
                lib = ct.CDLL('/tmp/uav-stage4-callback.so')
                lib.minimize.argtypes = [ct.c_size_t, ct.POINTER(ct.c_double), CALLBACK, ct.POINTER(ct.c_double)]
                lib.minimize.restype = None
                @CALLBACK
                def evaluate(yp, gp):
                    point = np.ctypeslib.as_array(yp, shape=(len(y),))
                    value, gradient = fg(point)
                    np.ctypeslib.as_array(gp, shape=(len(y),))[:] = gradient
                    return value
                output = np.empty(5)
                lib.minimize(len(y), y.ctypes.data_as(ct.POINTER(ct.c_double)), evaluate,
                    output.ctypes.data_as(ct.POINTER(ct.c_double)))
                status = ['gradient', 'max_iter', 'stalled', 'line_search'][int(output[4])]
                iterations, evaluations, success = int(output[2]), int(output[3]), output[4] == 0
            elif method in ['newton', 'newton-decomposed']:
                if method == 'newton-decomposed':
                    from decomposition import hessian_of_al
                    s.old.newton.fd_hessian = lambda grad, point, step: hessian_of_al(frozen, point, step, hessian_counts)[0]
                res = s.old.newton.tr_newton(fg, y, gtol=1e-8, max_iter=300, hessian_step=1e-7)
                y = np.ascontiguousarray(res['y'])
                status, iterations, evaluations = res['status'], int(res['iters']), int(res['evals'])
                success = status == 'converged'
            else:
                options = dict(gtol=1e-8, maxiter=2000 if maxiter is None else maxiter)
                if method == 'scipy-lbfgs':
                    options.update(ftol=1e-14, maxcor=20, maxls=65, maxfun=300000)
                res = minimize(fg, y, jac=True, callback=callback,
                    method='L-BFGS-B' if method == 'scipy-lbfgs' else 'BFGS', options=options)
                y = np.ascontiguousarray(res.x)
                status, iterations, evaluations, success = str(res.message), int(res.nit), int(res.nfev), bool(res.success)
        except TimeoutError:
            y, interrupted, status, success = last, True, 'timeout; last accepted SciPy iterate / Newton input', False
            iterations, evaluations = accepted if not method.startswith('newton') else None, calls
        finally:
            s.old.newton.fd_hessian = original_fd
    value, gradient = frozen.eval(y)
    centered, same_gradient = frozen.eval(y, stable=True)
    assert np.array_equal(gradient, same_gradient)
    m = frozen.m
    # Measure both the frozen-dual Lagrangian and one hypothetical AL update.
    lam1, mu1 = frozen.lam+frozen.rho*m.h, np.maximum(0., frozen.mu+frozen.rho*m.g)
    result = dict(problem=problem, method=method+suffix, y=y.tolist(), lam=frozen.lam.tolist(),
        mu=frozen.mu.tolist(), rho=frozen.rho, stage=4, eps=state['eps'], p=state['p'],
        value=value, centered_value=centered, gradient=gradient.tolist(),
        gradient_inf=float(max(abs(gradient))), gradient_pass=bool(not interrupted and max(abs(gradient)) <= 1e-8),
        inner_sufficient=bool(not interrupted and max(abs(gradient)) <= 1e-6),
        solver_success=bool(success), status=status, iterations=iterations, evaluations=evaluations,
        observed_evaluations=calls, seconds=monotonic()-start, interrupted=interrupted,
        hessian_gradient_calls=hessian_counts['gradient_calls'], hessian_jacobian_calls=hessian_counts['jacobian_calls'],
        fixed_dual_kkt=m.metrics(y, frozen.lam, frozen.mu),
        one_update_kkt=m.metrics(y, lam1, mu1))
    s.write(folder/'result.json', result)
    q = np.ascontiguousarray(y*m.scale/m.reference.scale)
    doc = m.reference.solution(q)
    doc['init'] = s.old.fidelity.tr.decode(m, frozen.anchor, m.source)
    doc['metrics'].update(converged=False, seconds=result['seconds'], init_objective=sum(doc['init']['s']))
    doc['experiment'] = dict(name='frozen-stage4-inner', method=method+suffix, problem=problem,
        paper_algorithm=False, y_full_precision=q.tolist(), variant_y=y.tolist(),
        gradient_inf=result['gradient_inf'], gradient_pass=result['gradient_pass'])
    s.write(folder/'solution.json', doc)
    print(json.dumps({key: result[key] for key in ['problem', 'method', 'gradient_inf', 'gradient_pass',
        'status', 'iterations', 'observed_evaluations', 'seconds']}), flush=True)
    frozen.close()
    return result


def follow(result):
    if not result['gradient_pass']:
        s.write(s.HERE/'follow-skipped.json', dict(reason='prespecified stalled stable-bfgs did not reach 1e-8'))
        return
    parent = json.loads((s.PRIOR/'result.json').read_text())
    folder = s.HERE/'follow'
    folder.mkdir(exist_ok=False)
    s.write(folder/'initial.json', parent)
    y, lam, mu = (np.array(parent[key]) for key in ['y', 'lam', 'mu'])
    rho = parent['rho']
    previous = max(parent['common_kkt']['feas'], parent['common_kkt']['comp'])
    start, stop, records = monotonic(), 'outer_limit', []
    with gzip.open(folder/'outer.jsonl.gz', 'wt') as log:
        for outer in range(200):
            if monotonic()-start >= 120:
                stop = 'timeout'
                break
            frozen = s.Frozen(dict(parent, y=y.tolist(), lam=lam.tolist(), mu=mu.tolist(), rho=rho))
            last = y.copy()
            def fg(point):
                if monotonic()-start >= 120:
                    raise TimeoutError()
                return frozen.eval(point, stable=True)
            def callback(point):
                nonlocal last
                last = point.copy()
            try:
                res = minimize(fg, y, jac=True, method='BFGS', callback=callback,
                    options=dict(gtol=1e-8, maxiter=2000))
            except TimeoutError:
                s.write(folder/'interrupted.json', dict(y=last.tolist(), completed_outer=outer))
                frozen.close()
                stop = 'timeout'
                break
            y = np.ascontiguousarray(res.x)
            value, gradient = frozen.eval(y)
            m = frozen.m
            lam += rho*m.h
            mu = np.maximum(0., mu+rho*m.g)
            metrics = m.metrics(y, lam, mu)
            violation = max(metrics['common_kkt']['feas'], metrics['common_kkt']['comp'])
            passed = max(metrics['common_kkt'].values()) <= 1e-6
            increased = violation > 1e-6 and violation > .25*previous and max(abs(gradient)) <= 1e-6 and not passed
            next_rho = min(1e8, 10*rho) if increased else rho
            row = dict(y=y.tolist(), lam=lam.tolist(), mu=mu.tolist(), rho=rho, rho_next=next_rho,
                stage=4, eps=parent['eps'], p=parent['p'], outer=201+outer, inner_gradient=float(max(abs(gradient))),
                inner_value=value, inner_status=str(res.message), inner_iterations=int(res.nit),
                **metrics, seconds=monotonic()-start)
            records.append(row)
            log.write(json.dumps(row)+'\n')
            log.flush()
            s.write(folder/'checkpoint.json', row)
            frozen.close()
            previous, rho = violation, next_rho
            if passed:
                stop = 'kkt'
                break
        final = records[-1] if records else parent
        s.write(folder/'result.json', dict(**final, stop=stop, additional_outer=len(records)))
        f = s.Frozen(dict(final, y=y.tolist(), lam=lam.tolist(), mu=mu.tolist(), rho=rho))
        m = f.m
        q = np.ascontiguousarray(y*m.scale/m.reference.scale)
        doc = m.reference.solution(q)
        doc['init'] = s.old.fidelity.tr.decode(m, np.array(parent['y']), m.source)
        doc['metrics'].update(converged=False, seconds=monotonic()-start, init_objective=sum(doc['init']['s']))
        doc['experiment'] = dict(name='stage4-stable-follow', paper_algorithm=False,
            stage=4, y_full_precision=q.tolist(), variant_y=y.tolist())
        s.write(folder/'solution.json', doc)
        f.close()
        print(json.dumps(dict(follow=stop, outer=len(records), common_kkt=final['common_kkt'])), flush=True)


def main():
    assert (s.HERE/'preflight.json').exists()
    assert not (s.HERE/'cases').exists(), 'refuse to overwrite'
    states = json.loads((s.HERE/'inputs.json').read_text())
    results = []
    for problem, state in states.items():
        for method in METHODS:
            result = solve(problem, method, state)
            results.append(result)
            if method == 'scipy-bfgs' and result['iterations'] == 2000 and 'maximum number' in result['status'].lower():
                continued = dict(state, y=result['y'])
                results.append(solve(problem, method, continued, suffix='-extra', maxiter=8000))
    s.write(s.HERE/'results.json', results)
    follow(next(r for r in results if r['problem'] == 'stalled' and r['method'] == 'stable-bfgs'))


if __name__ == '__main__':
    main()
