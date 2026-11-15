"""R2b case.py started from the nearest-order initial trajectory; runner, verifier and restoration unchanged."""
import json
import traceback

import numpy as np
import helpers as h


def start():
    assert not (h.HERE/'preflight.json').exists(), 'refuse to overwrite a case'
    h.HERE.mkdir(parents=True, exist_ok=True)
    m = h.fidelity.Variant('R')
    y = h.nearest_start(m)
    m.stage(.2, 2.)
    lam, mu = np.zeros(m.me), np.zeros(m.mi)

    class Wrap:
        pass
    w = Wrap()
    w.m = m
    source = dict(h.state(y, lam, mu, 1e4, 0), **h.assess(w, y, lam, mu),
        note='Rust initial trajectory with Order::Nearest; metrics at stage-1 smoothing')
    h.write(h.SOURCE, source)
    h.write(h.HERE/'preflight.json', dict(case=h.CASE, tau=h.TAU, seed=h.SEED, stamps=m.stamps, variables=m.n,
        start='Order::Nearest initial trajectory through bridge-nearest.rs, full precision',
        start_objective_hours=float(sum(h.tr.decode(m, y, m.source)['s'])),
        identical_to_index_order_start=bool(np.array_equal(y, m.native.y)),
        start_charging_segments=source['selection']['charging_segments'],
        instance=m.source['instance']))
    m.close()


def main():
    steps = {}
    start()
    for name, action in [('run', lambda: h.load_from(h.R2B, 'run').main()),
                         ('restore', lambda: h.load_from(h.R2A, 'restore').main()),
                         ('verify', lambda: h.load_from(h.R2B, 'verify').main())]:
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
