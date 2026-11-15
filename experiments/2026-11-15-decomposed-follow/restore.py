"""One conditional original fixed-branch restoration of a final common-KKT point."""
import copy
import importlib.util
import json
import math
from time import monotonic

import numpy as np
import helpers as h


def main():
    raw = json.loads((h.HERE/'result.json').read_text())
    if not raw['final_common_pass']:
        h.write(h.HERE/'restoration-skipped.json', dict(reason='no stage-13 common-KKT point',
            last_stage=raw['stage'], last_common_pass=raw['common_pass']))
        return
    import casadi as ca
    spec = importlib.util.spec_from_file_location('follow_fixed_branch', h.HERE.parent/'2026-11-14-restoration/fixed_branch.py')
    fb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fb)
    folder = h.HERE/'restored'
    folder.mkdir(exist_ok=False)
    data = fb.restore_source(json.loads((h.HERE/'solution.json').read_text()))
    result = dict(accepted=False, source='solution.json', source_objective=raw['objective'],
        source_common_kkt=raw['common_kkt'], source_paper_units_kkt=raw['paper_units_kkt'])
    start = monotonic()
    try:
        model = fb.FixedBranch(data, moving=True)
        options = dict(print_time=False, ipopt=dict(print_level=0, sb='yes', hessian_approximation='exact',
            tol=1e-10, dual_inf_tol=1e-8, constr_viol_tol=1e-11, compl_inf_tol=1e-9,
            acceptable_iter=0, max_iter=1500, max_wall_time=30., nlp_scaling_method='none',
            bound_relax_factor=0., mu_strategy='adaptive'))
        solver = ca.nlpsol('restore', 'ipopt', dict(x=model.v, f=model.objective, g=model.constraints), options)
        answer = solver(x0=model.x0, lbx=model.lb, ubx=model.ub,
            lbg=np.r_[np.zeros(model.me), np.full(model.mi, -np.inf)], ubg=np.zeros(model.me+model.mi))
        point = np.array(answer['x']).ravel()
        lam, lam_x = np.array(answer['lam_g']).ravel(), np.array(answer['lam_x']).ravel()
        residual = model.kkt(point, lam, lam_x)
        result.update(solver_status=solver.stats()['return_status'], solver_success=bool(solver.stats()['success']),
            iterations=solver.stats()['iter_count'], raw_kkt=residual)
        h.write(folder/'solver.json', dict(point=point.tolist(), lam=lam.tolist(), lam_x=lam_x.tolist(),
            options=options, **result))
        assert result['solver_success'] and max(residual.values()) <= 1e-6, result
        positions, durations = model.decode(point)
        before = durations.copy()
        for k, mode in enumerate(model.modes):
            speed = model.p['v_c'] if mode >= 0 else model.p['v_d']
            durations[k] = max(durations[k], model.p['s_min'], math.dist(positions[k], positions[k+1])/speed)
        assert max(abs(durations-before)) < 1e-10
        output = copy.deepcopy(data)
        output.pop('experiment', None)
        output['solution'] = dict(r=positions.tolist(), s=durations.tolist(),
            c=[float(t) if mode >= 0 else 0. for t, mode in zip(durations, model.modes)])
        output['solution']['e'] = fb.diag.replay(output)
        check = fb.diag.residuals(output)
        assert check['viol'] < 1e-10 and min(output['solution']['e']) >= 0. and max(output['solution']['e']) <= 1.
        for task, stamp in zip(output['instance']['tasks'], output['task_stamp']):
            assert output['solution']['r'][stamp] == task
        final_point = np.r_[positions[model.free].ravel(), np.array(output['solution']['e'][1:])*model.range,
            durations*model.p['v_d']]
        final_kkt = model.kkt(final_point, lam, lam_x)
        assert max(final_kkt.values()) <= 1e-6
        result.update(accepted=True, objective=float(sum(durations)), final_kkt=final_kkt,
            time_change_seconds=float((sum(durations)-raw['objective'])*3600),
            original_residuals=check, min_energy=min(output['solution']['e']),
            roundoff_time_correction=float(max(abs(durations-before))))
        output['stages'] = []
        output['metrics'] = dict(objective=result['objective'], init_objective=sum(output['init']['s']),
            converged=False, stamps=model.n, seconds=monotonic()-start, **check)
        output['diagnostic'] = dict(method='exact original fixed-branch restoration', paper_algorithm=False,
            branch_kkt=final_kkt, branch_kkt_pass=True, source='solution.json', energy_buffer=fb.ENERGY_BUFFER)
        fb.build_history(output)
        assert min(output['history']['e']) >= 0. and max(output['history']['e']) <= 1.
        h.write(folder/'solution.json', output)
    except (AssertionError, RuntimeError, ValueError) as error:
        result['reason'] = str(error)
    result['seconds'] = monotonic()-start
    h.write(folder/'result.json', result)
    print(json.dumps(result, allow_nan=False), flush=True)


if __name__ == '__main__':
    main()
