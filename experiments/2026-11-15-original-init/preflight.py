"""Checks before solving: the start point, the unchanged Newton, and one outer step of the old run."""
import gzip
import json
from time import monotonic

import numpy as np
import helpers as h

newton = h.load('newton')


def main():
    assert not (h.HERE/'preflight.json').exists(), 'refuse to overwrite preflight'
    # 1. Start point: the Rust initial trajectory in full precision; nothing saved is read into it.
    m = h.stage4.old.fidelity.Variant('R')
    y = m.native.y.copy()
    np.testing.assert_array_equal(m.scale, m.native.scale)
    seed = json.loads((h.HERE.parent/'2026-11-15-warm-start/default-seed.json').read_text())
    decoded = h.tr.decode(m, y, m.source)
    for key in ['r', 'e', 's', 'c']:
        np.testing.assert_allclose(decoded[key], seed['init'][key], atol=1e-9, rtol=0)
    objective = float(sum(decoded['s']))
    good = np.linalg.norm(y-m.y0)
    assert good > 1., 'the start must not be the saved good solution'
    m.stage(.2, 2.)
    lam, mu = np.zeros(m.me), np.zeros(m.mi)
    source = dict(h.state(y, lam, mu, 1e4, 0), **h.assess(_Wrap(m), y, lam, mu),
        note='original Rust initial trajectory; metrics at stage-1 smoothing; stage 0 means before any solve')
    m.close()
    # 2. The loaded Newton reproduces the previous fixed stage-4 AL.
    folder = h.PRIOR/'cases/stalled/newton-decomposed'
    old_input = json.loads((folder/'initial.json').read_text())
    old_result = json.loads((folder/'result.json').read_text())
    f = h.stage4.Frozen(old_input)
    result = newton.solve(f, f.anchor.copy(), monotonic()+45)
    np.testing.assert_allclose(result['y'], old_result['y'], atol=1e-12, rtol=1e-12)
    np.testing.assert_allclose(result['gradient'], old_result['gradient'], atol=1e-12, rtol=1e-9)
    assert result['status'] == old_result['status'] and result['iterations'] == old_result['iterations']
    f.close()
    # 3. One outer step of this runner's sequence on the previous stage-5 start equals the saved row.
    follow_source = json.loads(h.FOLLOW_SOURCE.read_text())
    with gzip.open(h.FOLLOW/'stages/stage05/outer.jsonl.gz', 'rt') as stream:
        row = json.loads(stream.readline())
    y5 = np.array(follow_source['y'])
    context = h.state(y5, np.zeros(len(follow_source['lam'])), np.zeros(len(follow_source['mu'])), 1e4, 5)
    f = h.stage4.Frozen(context)
    f.m.current_stage = 5
    step = newton.solve(f, y5.copy(), monotonic()+120)
    point = np.ascontiguousarray(step['y'])
    f.eval(point)
    lam5, mu5 = 1e4*f.m.h, np.maximum(0., 1e4*f.m.g)
    assert row['outer'] == 1 and row['rho'] == 1e4
    np.testing.assert_allclose(point, row['y'], atol=1e-12, rtol=1e-12)
    np.testing.assert_allclose(lam5, row['lam'], atol=1e-10, rtol=1e-10)
    np.testing.assert_allclose(mu5, row['mu'], atol=1e-10, rtol=1e-10)
    assert step['status'] == row['inner']['status'] and step['accepted'] == row['inner']['accepted']
    f.close()
    h.write(h.SOURCE, source)
    h.write(h.HERE/'preflight.json', dict(start='uav_initial through the bridge, full precision',
        start_objective_hours=objective, start_matches_warm_start_default_seed=True,
        distance_from_saved_good_solution_scaled=float(good),
        start_common_kkt=source['common_kkt'], start_charging_segments=source['selection']['charging_segments'],
        newton_same_fixed_stage4_output=True, newton_iterations=result['iterations'],
        same_first_outer_of_previous_stage5=True, previous_stage5_first_inner_accepted=step['accepted']))
    print(json.dumps(dict(preflight=True, start_objective_hours=objective,
        start_charging_segments=source['selection']['charging_segments'])), flush=True)


class _Wrap:
    """h.assess expects an object with the model in `.m`."""
    def __init__(self, m):
        self.m = m


if __name__ == '__main__':
    main()
