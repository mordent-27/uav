"""Checks before solving (PLAN.md). Run once per case with UAV_R2_CASE; writes preflight/<case>.json."""
import itertools
import json
import math
import subprocess
import tempfile

import numpy as np
import helpers as h


def order_of(traj, tasks):
    """Task indices in the order in which the trajectory first reaches them."""
    first = [next(k for k, r in enumerate(traj['r']) if math.dist(r, t) < 1e-9) for t in tasks]
    return [int(i) for i in np.argsort(first)], first


def main():
    out = h.BASE/'preflight'/f'{h.CASE}.json'
    assert not out.exists(), 'refuse to overwrite'
    m = h.fidelity.Variant('R')
    y_index, y_near = m.native.y.copy(), h.nearest_start(m)
    index, near = h.tr.decode(m, y_index, m.source), h.tr.decode(m, y_near, m.source)
    inst = m.source['instance']
    tasks = inst['tasks']
    length = lambda order: sum(math.dist(a, b) for a, b in zip([inst['r0']]+[tasks[i] for i in order],
                                                               [tasks[i] for i in order]+[inst['rf']]))
    # The main binary must produce the same nearest-order initial trajectory (its JSON has 9 digits).
    with tempfile.TemporaryDirectory() as folder:
        cmd = [str(h.ROOT/'target/release/uav'), 'solve', '--order', 'nearest', '--outer', '1', '--final-outer', '1',
               '--inner', '1', '--out', folder+'/x.json'] + (['--fig1'] if h.TAU == 0 else ['--tau', str(h.TAU), '--seed', str(h.SEED)])
        subprocess.run(cmd, check=True, capture_output=True)
        binary = json.loads(open(folder+'/x.json').read())['init']
    for key in ['r', 'e', 's', 'c']:
        np.testing.assert_allclose(near[key], binary[key], atol=2e-9, rtol=0)
    m.stage(.2, 2.)
    zero = (np.zeros(m.me), np.zeros(m.mi))

    class Wrap:
        pass
    w = Wrap()
    w.m = m
    charging = lambda y: h.assess(w, y, *zero)['selection']['charging_segments']
    order_i, _ = order_of(index, tasks)
    order_n, _ = order_of(near, tasks)
    report = dict(case=h.CASE, stamps=m.stamps, variables=m.n, identical_start=bool(np.array_equal(y_index, y_near)),
        index_order=order_i, nearest_order=order_n,
        route_km=dict(index=length(order_i), nearest=length(order_n),
                      best=min(length(o) for o in itertools.permutations(range(len(tasks))))),
        start_hours=dict(index=float(sum(index['s'])), nearest=float(sum(near['s']))),
        start_charging_segments=dict(index=charging(y_index), nearest=charging(y_near)),
        matches_main_binary_nearest_init=True)
    m.close()
    out.parent.mkdir(exist_ok=True)
    h.write(out, report)
    print(json.dumps({k: report[k] for k in ['case', 'identical_start', 'index_order', 'nearest_order', 'route_km', 'start_hours']}), flush=True)


if __name__ == '__main__':
    main()
