"""Optimize initial durations/energy with initial geometry and modes fixed."""
import copy
import json
import math
from time import monotonic

import casadi as ca
import numpy as np
import helpers as h


def main():
    h.INIT.mkdir(parents=True, exist_ok=False)
    m = h.fidelity.Variant('R')
    original = m.native.y.copy()
    data = copy.deepcopy(m.source)
    trajectory = h.tr.decode(m, original, m.source)
    data['init'] = copy.deepcopy(trajectory)
    data['solution'] = trajectory
    # Avoid snapping a fixed position to the 9-digit JSON representation.
    data['instance']['tasks'] = [trajectory['r'][stamp] for stamp in data['task_stamp']]
    fb = h.load_from(h.ROOT/'experiments/2026-11-14-restoration', 'fixed_branch')
    start = monotonic()
    result = dict(case=h.CASE, accepted=False, initial_objective=float(sum(trajectory['s'])),
        initial_min_energy=min(trajectory['e']), stamps=m.stamps,
        input_only=True, moving_geometry=False)
    try:
        model = fb.FixedBranch(data, moving=False)
        assert np.array_equal(model.initial_positions, np.array(trajectory['r']))
        assert all((trajectory['c'][k] == trajectory['s'][k]) if mode >= 0 else trajectory['c'][k] == 0.
                   for k, mode in enumerate(model.modes))
        options = dict(print_time=False, ipopt=dict(print_level=0, sb='yes', hessian_approximation='exact',
            tol=1e-10, dual_inf_tol=1e-8, constr_viol_tol=1e-11, compl_inf_tol=1e-9,
            acceptable_iter=0, max_iter=1500, max_wall_time=10., nlp_scaling_method='none',
            bound_relax_factor=0., mu_strategy='adaptive'))
        solver = ca.nlpsol('charge_init', 'ipopt', dict(x=model.v, f=model.objective, g=model.constraints), options)
        answer = solver(x0=model.x0, lbx=model.lb, ubx=model.ub,
            lbg=np.r_[np.zeros(model.me), np.full(model.mi, -np.inf)], ubg=np.zeros(model.me+model.mi))
        point = np.array(answer['x']).ravel()
        lam, lam_x = np.array(answer['lam_g']).ravel(), np.array(answer['lam_x']).ravel()
        raw_kkt = model.kkt(point, lam, lam_x)
        result.update(solver_success=bool(solver.stats()['success']), solver_status=solver.stats()['return_status'],
            iterations=solver.stats()['iter_count'], raw_kkt=raw_kkt)
        h.write(h.INIT/'solver.json', dict(point=point.tolist(), lam=lam.tolist(), lam_x=lam_x.tolist(), options=options))
        positions, durations = model.decode(point)
        before = durations.copy()
        for k, mode in enumerate(model.modes):
            speed = model.p['v_c'] if mode >= 0 else model.p['v_d']
            durations[k] = max(durations[k], model.p['s_min'], math.dist(positions[k], positions[k+1])/speed)
        output = copy.deepcopy(data)
        output['solution'] = dict(r=positions.tolist(), s=durations.tolist(),
            c=[float(t) if mode >= 0 else 0. for t, mode in zip(durations, model.modes)])
        output['solution']['e'] = fb.diag.replay(output)
        residual = fb.diag.residuals(output)
        energy = output['solution']['e']
        final_point = np.r_[np.array(energy[1:])*model.range, durations*model.p['v_d']]
        final_kkt = model.kkt(final_point, lam, lam_x)
        correction = float(max(abs(durations-before)))
        accepted = result['solver_success'] and max(raw_kkt.values()) <= 1e-6 and max(final_kkt.values()) <= 1e-6
        accepted = accepted and correction <= 1e-10 and residual['viol'] <= 1e-6 and min(energy) >= 0. and max(energy) <= 1.
        result.update(accepted=bool(accepted), objective=float(sum(durations)), final_kkt=final_kkt,
            original_residuals=residual, min_energy=float(min(energy)), max_energy=float(max(energy)),
            duration_correction=correction)
        y = np.r_[positions[1:-1].ravel(), energy[1:], durations, output['solution']['c']]/m.scale
        nr = 2*(m.stamps-2)
        assert np.array_equal(y[:nr], original[:nr])
        assert np.array_equal(positions, np.array(trajectory['r']))
        assert output['modes'] == data['modes'] and output['task_stamp'] == data['task_stamp']
        result['same_full_initial_state'] = bool(np.array_equal(y, original))
        result['same_positions_and_modes'] = True
        m.stage(.2, 2.)
        zero_lam, zero_mu = np.zeros(m.me), np.zeros(m.mi)
        class Wrap:
            pass
        wrap = Wrap()
        wrap.m = m
        source = dict(h.state(y, zero_lam, zero_mu, 1e4, 0), eps=.2, p=2.,
            **h.assess(wrap, y, zero_lam, zero_mu),
            note='input-only fixed-geometry/fixed-mode duration-energy initialization')
        h.write(h.INIT/'source.json', source)
        output['metrics'] = dict(objective=result['objective'], init_objective=result['initial_objective'],
            converged=False, stamps=m.stamps, seconds=monotonic()-start, **residual)
        output['stages'] = []
        output['experiment'] = dict(name='fixed-geometry-charge-initialization', paper_algorithm=False,
            y_full_precision=y.tolist(), variant_y=y.tolist())
        fb.build_history(output)
        h.write(h.INIT/'solution.json', output)
    except (AssertionError, RuntimeError, ValueError) as error:
        result['reason'] = str(error)
    result['seconds'] = monotonic()-start
    h.write(h.INIT/'result.json', result)
    m.close()
    print(json.dumps(result, allow_nan=False), flush=True)


if __name__ == '__main__':
    main()
