"""Supply the accepted input-only initialization to the unchanged G runner."""
import json
import traceback
import numpy as np
import helpers as h


def main():
    initialized = json.loads((h.INIT/'result.json').read_text())
    assert initialized['accepted'], 'initialization was not accepted'
    h.HERE.mkdir(parents=True, exist_ok=False)
    source = json.loads((h.INIT/'source.json').read_text())
    m = h.fidelity.Variant('R')
    nr = 2*(m.stamps-2)
    assert np.array_equal(np.array(source['y'])[:nr], m.native.y[:nr])
    base = json.loads((h.R2B/'cases/G'/h.CASE/'source.json').read_text())
    np.testing.assert_allclose(base['y'], m.native.y, atol=1e-12, rtol=1e-12)
    h.write(h.SOURCE, source)
    h.write(h.HERE/'preflight.json', dict(case=h.CASE, same_positions=True,
        same_instance_and_scale=True, baseline_initial_state_verified=True,
        initial_charge_state=str(h.INIT.relative_to(h.ROOT))))
    m.close()
    steps = {}
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
