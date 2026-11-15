"""One fixed-branch restoration of a final common-KKT point, with the acceptance rule of PLAN.md.

The solve is the previous restore.py (same Ipopt options). The acceptance is a separate function so
that a saved solver point can be judged again without solving (see rejudge_r1.py).
"""
import copy
import json
import math
from time import monotonic

import numpy as np
import helpers as h

RESIDUAL_LIMIT = 1e-6   # original constraints after the duration correction (km and h)
CORRECTION_LIMIT = 1e-6  # duration added to meet the speed limits exactly (h)
KKT_LIMIT = 1e-6

fb = h.load_from(h.ROOT/'experiments/2026-11-14-restoration', 'fixed_branch')
OPTIONS = dict(print_time=False, ipopt=dict(print_level=0, sb='yes', hessian_approximation='exact',
    tol=1e-10, dual_inf_tol=1e-8, constr_viol_tol=1e-11, compl_inf_tol=1e-9,
    acceptable_iter=0, max_iter=1500, max_wall_time=30., nlp_scaling_method='none',
    bound_relax_factor=0., mu_strategy='adaptive'))


def accept(model, data, point, lam, lam_x):
    """Return (accepted, report, output document). No solve; raises nothing."""
    positions, durations = model.decode(point)
    before = durations.copy()
    for k, mode in enumerate(model.modes):
        speed = model.p['v_c'] if mode >= 0 else model.p['v_d']
        durations[k] = max(durations[k], model.p['s_min'], math.dist(positions[k], positions[k+1])/speed)
    output = copy.deepcopy(data)
    output.pop('experiment', None)
    output['solution'] = dict(r=positions.tolist(), s=durations.tolist(),
        c=[float(t) if mode >= 0 else 0. for t, mode in zip(durations, model.modes)])
    report = dict(duration_correction=float(max(abs(durations-before))), objective=float(sum(durations)))
    try:
        output['solution']['e'] = fb.diag.replay(output)
    except ValueError as error:
        return False, dict(report, reason='battery replay: '+str(error)), None
    energy = output['solution']['e']
    check = fb.diag.residuals(output)
    final_point = np.r_[positions[model.free].ravel(), np.array(energy[1:])*model.range, durations*model.p['v_d']]
    final_kkt = model.kkt(final_point, lam, lam_x)
    tasks_exact = all(output['solution']['r'][stamp] == task
                      for task, stamp in zip(output['instance']['tasks'], output['task_stamp']))
    report.update(original_residuals=check, min_energy=float(min(energy)), max_energy=float(max(energy)),
        final_kkt=final_kkt, tasks_exact=tasks_exact)
    checks = dict(correction=report['duration_correction'] <= CORRECTION_LIMIT,
        residual=check['viol'] <= RESIDUAL_LIMIT, energy=min(energy) >= 0. and max(energy) <= 1.,
        tasks=tasks_exact, branch_kkt=max(final_kkt.values()) <= KKT_LIMIT)
    if all(checks.values()):
        fb.build_history(output)
        checks['dense_energy'] = min(output['history']['e']) >= 0. and max(output['history']['e']) <= 1.
    report['checks'] = checks
    return all(checks.values()), report, output


def main():
    raw = json.loads((h.HERE/'result.json').read_text())
    if not raw['final_common_pass']:
        h.write(h.HERE/'restoration-skipped.json', dict(reason='no stage-13 common-KKT point',
            last_stage=raw['stage'], last_common_pass=raw['common_pass']))
        return
    import casadi as ca
    folder = h.HERE/'restored'
    folder.mkdir(exist_ok=False)
    data = fb.restore_source(json.loads((h.HERE/'solution.json').read_text()))
    result = dict(accepted=False, source='solution.json', source_objective=raw['objective'],
        source_common_kkt=raw['common_kkt'], source_paper_units_kkt=raw['paper_units_kkt'],
        limits=dict(residual=RESIDUAL_LIMIT, correction=CORRECTION_LIMIT, kkt=KKT_LIMIT))
    start = monotonic()
    try:
        model = fb.FixedBranch(data, moving=True)
        solver = ca.nlpsol('restore', 'ipopt', dict(x=model.v, f=model.objective, g=model.constraints), OPTIONS)
        answer = solver(x0=model.x0, lbx=model.lb, ubx=model.ub,
            lbg=np.r_[np.zeros(model.me), np.full(model.mi, -np.inf)], ubg=np.zeros(model.me+model.mi))
        point = np.array(answer['x']).ravel()
        lam, lam_x = np.array(answer['lam_g']).ravel(), np.array(answer['lam_x']).ravel()
        residual = model.kkt(point, lam, lam_x)
        result.update(solver_status=solver.stats()['return_status'], solver_success=bool(solver.stats()['success']),
            iterations=solver.stats()['iter_count'], raw_kkt=residual)
        h.write(folder/'solver.json', dict(point=point.tolist(), lam=lam.tolist(), lam_x=lam_x.tolist(),
            options=OPTIONS, **result))
        if not (result['solver_success'] and max(residual.values()) <= KKT_LIMIT):
            result['reason'] = 'solver flag or fixed-branch KKT of the returned point'
        else:
            accepted, report, output = accept(model, data, point, lam, lam_x)
            result.update(report)
            if accepted:
                result.update(accepted=True, time_change_seconds=float((report['objective']-raw['objective'])*3600),
                    roundoff_time_correction=report['duration_correction'])
                output['stages'] = []
                output['metrics'] = dict(objective=report['objective'], init_objective=sum(output['init']['s']),
                    converged=False, stamps=model.n, seconds=monotonic()-start, **report['original_residuals'])
                output['diagnostic'] = dict(method='exact original fixed-branch restoration', paper_algorithm=False,
                    branch_kkt=report['final_kkt'], branch_kkt_pass=True, source='solution.json',
                    energy_buffer=fb.ENERGY_BUFFER, acceptance_limits=result['limits'])
                h.write(folder/'solution.json', output)
            else:
                result['reason'] = report.get('reason') or 'failed checks: '+', '.join(
                    name for name, ok in report['checks'].items() if not ok)
    except (AssertionError, RuntimeError, ValueError) as error:
        result['reason'] = 'exception: '+str(error)
    result['seconds'] = monotonic()-start
    h.write(folder/'result.json', result)
    print(json.dumps({k: result.get(k) for k in ['accepted', 'objective', 'solver_status', 'iterations', 'reason']}), flush=True)


if __name__ == '__main__':
    main()
