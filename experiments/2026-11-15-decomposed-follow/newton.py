"""Previous diagnostic trust-region Newton with accepted-point/time accounting."""
from time import monotonic
import numpy as np
import helpers as h


def solve(frozen, y, deadline, record=lambda row: None):
    counts = dict(gradient_calls=0, jacobian_calls=0)
    scalar_calls, start = 0, monotonic()
    def fg(point):
        nonlocal scalar_calls
        if monotonic() >= deadline:
            raise TimeoutError()
        scalar_calls += 1
        return frozen.eval(point)
    # Always obtain a valid initial state, even if setup exhausted the deadline;
    # the guarded loop then returns it as a timeout without taking a step.
    scalar_calls += 1
    f, g = frozen.eval(y)
    status, accepted_total, delta, w, iterations = 'max_iter', 0, 1., None, 0
    record(dict(kind='input', y=y.tolist(), value=f, gradient_inf=float(max(abs(g)))))
    try:
        for it in range(300):
            iterations = it
            if monotonic() >= deadline:
                raise TimeoutError()
            if max(abs(g)) <= 1e-8:
                status = 'converged'
                break
            H, _ = h.decomposition.hessian_of_al(frozen, y, 1e-7, counts)
            w, V = np.linalg.eigh(H)
            accepted = False
            for _ in range(60):
                step, boundary = h.stage4.old.newton.tr_step(w, V, g, delta)
                pred = -(g@step+.5*step@H@step)
                fn, gn = fg(y+step)
                fallback = pred <= 1e-13*max(1., abs(f))
                if fallback:
                    ratio = 1. if np.linalg.norm(gn) < np.linalg.norm(g) else 0.
                else:
                    ratio = (f-fn)/pred
                if ratio < .25:
                    delta = .25*np.linalg.norm(step)
                elif ratio > .75 and boundary:
                    delta = min(2*delta, 1e3)
                if ratio > 1e-4:
                    y, f, g, accepted = y+step, fn, gn, True
                    accepted_total += 1
                    record(dict(kind='accepted', iteration=accepted_total, y=y.tolist(),
                        value=float(f), gradient_inf=float(max(abs(g))), delta=float(delta),
                        ratio=float(ratio), prediction=float(pred), gradient_fallback=bool(fallback),
                        eigen_min=float(w[0]), eigen_max=float(w[-1]), seconds=monotonic()-start))
                    break
                if delta < 1e-14:
                    break
            if not accepted:
                status = 'stuck'
                break
        else:
            iterations = 300
    except TimeoutError:
        status = 'timeout'
    return dict(y=y, value=float(f), gradient=g, gradient_inf=float(max(abs(g))), status=status,
        iterations=iterations, accepted=accepted_total, scalar_calls=scalar_calls,
        hessian_gradient_calls=counts['gradient_calls'], jacobian_calls=counts['jacobian_calls'],
        seconds=monotonic()-start, eig=None if w is None else [float(w[0]), float(w[-1])])


def preflight():
    import json
    assert not (h.HERE/'preflight.json').exists()
    source = json.loads(h.SOURCE.read_text())
    f = h.stage4.Frozen(source)
    measured = f.m.metrics(np.array(source['y']), np.array(source['lam']), np.array(source['mu']))
    for key in ['common_kkt', 'paper_units_kkt']:
        np.testing.assert_allclose(list(measured[key].values()), list(source[key].values()), atol=1e-10, rtol=1e-8)
    assert max(measured['common_kkt'].values()) <= 1e-6
    f.close()
    folder = h.PRIOR/'cases/stalled/newton-decomposed'
    original_input = json.loads((folder/'initial.json').read_text())
    original_result = json.loads((folder/'result.json').read_text())
    f = h.stage4.Frozen(original_input)
    result = solve(f, f.anchor.copy(), monotonic()+45)
    np.testing.assert_allclose(result['y'], original_result['y'], atol=1e-12, rtol=1e-12)
    np.testing.assert_allclose(result['gradient'], original_result['gradient'], atol=1e-12, rtol=1e-9)
    assert result['status'] == original_result['status'] and result['iterations'] == original_result['iterations']
    h.write(h.HERE/'preflight.json', dict(source=str(h.SOURCE.relative_to(h.ROOT)),
        source_common_kkt=measured['common_kkt'], source_paper_units_kkt=measured['paper_units_kkt'],
        instrumented_Newton_same_point=True, same_gradient=True,
        status=result['status'], iterations=result['iterations'], gradient_inf=result['gradient_inf']))
    print('Preflight: saved stage-4 KKT and identical instrumented Newton output verified', flush=True)
    f.close()


if __name__ == '__main__':
    preflight()
