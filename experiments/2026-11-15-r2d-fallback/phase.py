"""Initialize one phase, then use the earlier runner/restoration/verifier unchanged."""
import json
import traceback
import numpy as np
import helpers as h


def start():
    if h.PHASE == 'G':
        h.load_from(h.R2B, 'case').start()
    else:
        h.HERE.mkdir(parents=True, exist_ok=False)
    m = h.fidelity.Variant('R')
    y = m.native.y.copy()
    eps, p = (.2, 2.) if h.PHASE == 'G' else (.0005, 12.)
    m.stage(eps, p)
    lam, mu, rho = np.zeros(m.me), np.zeros(m.mi), 1e4
    baseline_path = h.SOURCE if h.PHASE == 'G' else (h.BASE/'cases/G'/h.CASE/'source.json')
    if not baseline_path.exists():
        baseline_path = h.R2B/'cases/G'/h.CASE/'source.json'
    baseline = json.loads(baseline_path.read_text())
    np.testing.assert_array_equal(y, baseline['y'])
    value, gradient = m.eval(y, lam, mu, rho)
    le, mi = lam+rho*m.h, np.maximum(0., mu+rho*m.g)
    jac = m.jacobian(y)
    _, gf = m.eval(y, np.zeros(m.me), np.zeros(m.mi), 0.)
    independent = gf+jac[:m.me].T@le+jac[m.me:].T@mi
    np.testing.assert_allclose(gradient, independent, atol=1e-9, rtol=1e-8)
    if h.PHASE == 'direct':
        class Wrap:
            pass
        wrap = Wrap()
        wrap.m = m
        source = dict(h.state(y, lam, mu, rho, 0), eps=eps, p=p, **h.assess(wrap, y, lam, mu),
            note='same original Rust Index initial state; direct final NLP after G was not accepted')
        h.write(h.SOURCE, source)
        preflight = dict(case=h.CASE, stamps=m.stamps, variables=m.n, start='original Rust initialization')
    else:
        preflight = json.loads((h.HERE/'preflight.json').read_text())
    preflight.update(phase=h.PHASE, same_original_initial_state=True,
        smoothing=[eps, p], initial_al_value=value, initial_al_gradient_inf=float(max(abs(gradient))),
        independent_Jacobian_gradient_verified=True, baseline_source=str(baseline_path.relative_to(h.ROOT)))
    h.write(h.HERE/'preflight.json', preflight)
    m.close()


def main():
    start()
    folder = h.R2B if h.PHASE == 'G' else h.DIRECT
    steps = {}
    try:
        for name, action in [('run', lambda: h.load_from(folder, 'run').main()),
                             ('restore', lambda: h.load_from(h.R2A, 'restore').main()),
                             ('verify', lambda: h.load_from(folder, 'verify').main())]:
            try:
                action()
                steps[name] = 'ok'
            except Exception:
                steps[name] = traceback.format_exc()
                raise
    finally:
        h.write(h.HERE/'steps.json', steps)


if __name__ == '__main__':
    main()
