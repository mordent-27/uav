"""Is the branch chosen by a stalled final point feasible for the original problem? One Ipopt solve per case.

Run with UAV_R2B_COND=G UAV_R2_CASE=<case>; helpers and the acceptance function come from the earlier folders.
"""
import itertools
import json
import math
import sys
from pathlib import Path
from time import monotonic

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent/'2026-11-15-r2b-coarse'))
import helpers as h  # noqa: E402

restore = h.load_from(h.R2A, 'restore')
fb = restore.fb


def route_bound(data):
    """Shortest flight distance over all visiting orders, and for the index order (straight legs)."""
    inst = data['instance']
    tasks = inst['tasks']
    length = lambda order: sum(math.dist(a, b) for a, b in zip([inst['r0']]+[tasks[i] for i in order],
                                                               [tasks[i] for i in order]+[inst['rf']]))
    best = min(length(order) for order in itertools.permutations(range(len(tasks))))
    return dict(index_order_km=length(range(len(tasks))), best_order_km=best,
        range_km=data['phys']['v_d']*data['phys']['e_max']/data['phys']['zeta'])


def main():
    import casadi as ca
    out = HERE/'cases'/f'{h.CASE}.json'
    assert not out.exists(), 'refuse to overwrite'
    source = h.BASE/'cases'/'G'/h.CASE
    raw = json.loads((source/'result.json').read_text())
    data = fb.restore_source(json.loads((source/'solution.json').read_text()))
    modes = data['modes']
    result = dict(case=h.CASE, source=str(source.relative_to(h.ROOT)), source_objective=raw['objective'],
        source_common_kkt=raw['common_kkt'], modes=modes, task_stamp=data['task_stamp'],
        charging_segments=sum(m >= 0 for m in modes), route=route_bound(data))
    if result['charging_segments'] == 0:
        result['no_charging_branch_infeasible_by_bound'] = result['route']['best_order_km'] > result['route']['range_km']
    start = monotonic()
    try:
        model = fb.FixedBranch(data, moving=True)
        solver = ca.nlpsol('branch', 'ipopt', dict(x=model.v, f=model.objective, g=model.constraints), restore.OPTIONS)
        answer = solver(x0=model.x0, lbx=model.lb, ubx=model.ub,
            lbg=np.r_[np.zeros(model.me), np.full(model.mi, -np.inf)], ubg=np.zeros(model.me+model.mi))
        point = np.array(answer['x']).ravel()
        lam, lam_x = np.array(answer['lam_g']).ravel(), np.array(answer['lam_x']).ravel()
        stats = solver.stats()
        result.update(solver_status=stats['return_status'], solver_success=bool(stats['success']),
            iterations=stats['iter_count'], raw_kkt=model.kkt(point, lam, lam_x))
        accepted, report, _ = restore.accept(model, data, point, lam, lam_x)
        result.update(accepted=bool(accepted and result['solver_success'] and max(result['raw_kkt'].values()) <= restore.KKT_LIMIT),
            returned_point=report)
    except (AssertionError, RuntimeError, ValueError) as error:
        result.update(accepted=False, exception=str(error))
    result['seconds'] = monotonic()-start
    out.parent.mkdir(exist_ok=True)
    h.write(out, result)
    r = result.get('returned_point', {})
    print(json.dumps(dict(case=h.CASE, charging=result['charging_segments'], status=result.get('solver_status'),
        accepted=result['accepted'], feas=result.get('raw_kkt', {}).get('feas'),
        residual=r.get('original_residuals', {}).get('viol'), min_energy=r.get('min_energy'),
        objective=r.get('objective'), route=result['route'], exception=result.get('exception'))), flush=True)


if __name__ == '__main__':
    main()
