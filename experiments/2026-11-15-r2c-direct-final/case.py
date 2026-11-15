"""One direct start, using the unchanged final AL and original input trajectory."""
import json
import traceback

import numpy as np
import helpers as h


def main():
    h.HERE.mkdir(parents=True, exist_ok=False)
    m = h.fidelity.Variant('R')
    y = m.native.y.copy()
    baseline = json.loads((h.R2B/'cases/G'/h.CASE/'source.json').read_text())
    np.testing.assert_array_equal(y, baseline['y'])
    m.stage(.0005, 12.)
    lam, mu, rho = np.zeros(m.me), np.zeros(m.mi), 1e4
    value, gradient = m.eval(y, lam, mu, rho)
    le, mi = lam+rho*m.h, np.maximum(0., mu+rho*m.g)
    jac = m.jacobian(y)
    _, gf = m.eval(y, np.zeros(m.me), np.zeros(m.mi), 0.)
    independent = gf+jac[:m.me].T@le+jac[m.me:].T@mi
    np.testing.assert_allclose(gradient, independent, atol=1e-9, rtol=1e-8)
    class Wrap:
        pass
    wrap = Wrap()
    wrap.m = m
    source = dict(h.state(y, lam, mu, rho, 0), eps=.0005, p=12., **h.assess(wrap, y, lam, mu),
        note='original Rust Index initialization, final-stage smoothing; no charge preprocessing')
    h.write(h.SOURCE, source)
    h.write(h.HERE/'preflight.json', dict(case=h.CASE, same_original_initial_state=True,
        stamps=m.stamps, variables=m.n, final_stage=[.0005, 12.], initial_al_value=value,
        initial_al_gradient_inf=float(max(abs(gradient))), independent_Jacobian_gradient_verified=True))
    m.close()
    steps = {}
    for name, action in [('run', lambda: h.load_from(h.BASE, 'run').main()),
                         ('restore', lambda: h.load_from(h.R2A, 'restore').main()),
                         ('verify', lambda: h.load_from(h.BASE, 'verify').main())]:
        try:
            action()
            steps[name] = 'ok'
        except Exception:
            steps[name] = traceback.format_exc()
            print(steps[name], flush=True)
            if name == 'run':
                break
    h.write(h.HERE/'steps.json', steps)


if __name__ == '__main__':
    main()
