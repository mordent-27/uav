"""One physical restoration per final output, with original modes/task stamps frozen."""
import copy
import importlib.util
import json
import math
from pathlib import Path
from time import monotonic

import casadi as ca
import numpy as np
import controls as c

SPEC = importlib.util.spec_from_file_location('fixed_branch', c.HERE.parent / '2026-11-14-restoration/fixed_branch.py')
fb = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fb)


def restore(folder):
    destination = c.HERE / 'restored' / folder.name
    destination.mkdir(parents=True, exist_ok=False)
    result = dict(name=folder.name, source=str(folder.relative_to(c.ROOT)), accepted=False)
    data = json.loads((folder / 'solution.json').read_text())
    raw = json.loads((folder / 'result.json').read_text())
    bridge = c.tr.Model(0, 0, c.tr.LIBRARIES['normalized'])
    data['solution'] = c.tr.decode(bridge, np.array(raw['y']), data)
    bridge.close()
    result['source_objective'] = raw['objective']
    result['source_original_kkt'] = raw['original_kkt']
    start = monotonic()
    try:
        model = fb.FixedBranch(data, moving=True)
        options = dict(print_time=False, ipopt=dict(print_level=0, sb='yes', hessian_approximation='exact',
            tol=1e-10, dual_inf_tol=1e-8, constr_viol_tol=1e-11, compl_inf_tol=1e-9, acceptable_iter=0,
            max_iter=1500, max_wall_time=5., nlp_scaling_method='none', bound_relax_factor=0., mu_strategy='adaptive'))
        solver = ca.nlpsol('restore', 'ipopt', dict(x=model.v, f=model.objective, g=model.constraints), options)
        solution = solver(x0=model.x0, lbx=model.lb, ubx=model.ub,
            lbg=np.r_[np.zeros(model.me), np.full(model.mi, -np.inf)], ubg=np.zeros(model.me+model.mi))
        point = np.array(solution['x']).ravel()
        lam, lam_x = np.array(solution['lam_g']).ravel(), np.array(solution['lam_x']).ravel()
        raw_kkt = model.kkt(point, lam, lam_x)
        result.update(solver_status=solver.stats()['return_status'], solver_success=bool(solver.stats()['success']),
            iterations=solver.stats()['iter_count'], raw_kkt=raw_kkt)
        c.tr.write(destination / 'solver.json', dict(point=point.tolist(), lam=lam.tolist(), lam_x=lam_x.tolist(),
            options=options, **result))
        assert result['solver_success'], result['solver_status']
        assert max(raw_kkt.values()) <= 1e-6, raw_kkt
        r, s = model.decode(point)
        before = s.copy()
        for k, mode in enumerate(model.modes):
            speed = model.p['v_c'] if mode >= 0 else model.p['v_d']
            s[k] = max(s[k], model.p['s_min'], math.dist(r[k], r[k+1])/speed)
        assert max(abs(s-before)) < 1e-10
        output = copy.deepcopy(data)
        output.pop('experiment', None)
        output['solution'] = dict(r=r.tolist(), s=s.tolist(),
            c=[float(t) if m >= 0 else 0. for t, m in zip(s, model.modes)])
        output['solution']['e'] = fb.diag.replay(output)
        residuals = fb.diag.residuals(output)
        assert residuals['viol'] < 1e-10
        assert min(output['solution']['e']) >= 0. and max(output['solution']['e']) <= 1.
        for task, stamp in zip(output['instance']['tasks'], output['task_stamp']):
            assert output['solution']['r'][stamp] == task
        final_point = np.r_[r[model.free].ravel(), np.array(output['solution']['e'][1:])*model.range, s*model.p['v_d']]
        final_kkt = model.kkt(final_point, lam, lam_x)
        assert max(final_kkt.values()) <= 1e-6
        result.update(accepted=True, objective=float(sum(s)),
            time_change_seconds=float((sum(s)-raw['objective'])*3600), final_kkt=final_kkt,
            original_residuals=residuals, min_energy=min(output['solution']['e']),
            roundoff_time_correction=float(max(abs(s-before))))
        output['stages'] = []
        output['metrics'] = dict(objective=float(sum(s)), init_objective=sum(output['init']['s']),
            converged=False, stamps=model.n, seconds=monotonic()-start, **residuals)
        output['diagnostic'] = dict(method='exact original fixed-branch restoration', paper_algorithm=False,
            branch_kkt=final_kkt, branch_kkt_pass=True, source=result['source'],
            source_original_kkt=result['source_original_kkt'], energy_buffer=fb.ENERGY_BUFFER)
        fb.build_history(output)
        assert min(output['history']['e']) >= 0. and max(output['history']['e']) <= 1.
        c.tr.write(destination / 'solution.json', output)
    except (AssertionError, RuntimeError, ValueError) as error:
        result['reason'] = str(error)
    result['seconds'] = monotonic()-start
    c.tr.write(destination / 'result.json', result)
    print(json.dumps(result, allow_nan=False), flush=True)
    return result


if __name__ == '__main__':
    import sys
    default_only = sys.argv[1:] == ['--default-only']
    assert not sys.argv[1:] or default_only
    folders = sorted((c.HERE / 'runs').glob('*-default-direct' if default_only else '*'))
    continuation = 'newton-default' if default_only else 'newton'
    if (c.HERE / continuation / 'result.json').exists():
        folders.append(c.HERE / continuation)
    assert len(folders) in ([3, 4] if default_only else [6, 7])
    assert all(not (c.HERE / 'restored' / f.name).exists() for f in folders), 'refuse to overwrite restorations'
    results = [restore(folder) for folder in folders]
    c.tr.write(c.HERE / ('default-restoration-summary.json' if default_only else 'restoration-summary.json'), results)
