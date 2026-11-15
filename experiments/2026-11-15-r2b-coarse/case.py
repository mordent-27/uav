"""R2a case.py with the runner and verifier of this folder; restoration is the R2a file unchanged."""
import json
import traceback

import numpy as np
import helpers as h


def start():
    assert not (h.HERE/'preflight.json').exists(), 'refuse to overwrite a case'
    h.HERE.mkdir(parents=True, exist_ok=True)
    m = h.fidelity.Variant('R')
    y = m.native.y.copy()
    m.stage(.2, 2.)
    lam, mu = np.zeros(m.me), np.zeros(m.mi)

    class Wrap:
        pass
    w = Wrap()
    w.m = m
    source = dict(h.state(y, lam, mu, 1e4, 0), **h.assess(w, y, lam, mu),
        note='original Rust initial trajectory of this case; metrics at stage-1 smoothing')
    h.write(h.SOURCE, source)
    h.write(h.HERE/'preflight.json', dict(case=h.CASE, tau=h.TAU, seed=h.SEED, stamps=m.stamps, variables=m.n,
        start='uav_initial through the bridge, full precision',
        start_objective_hours=float(sum(m.source['solution']['s'])),
        start_charging_segments=source['selection']['charging_segments'],
        instance=m.source['instance']))
    m.close()


def main():
    steps = {}
    start()
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
