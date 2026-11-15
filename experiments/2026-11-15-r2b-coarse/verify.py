"""R2a verify.py with the stage rules taken from helpers (PLAN.md)."""
import gzip
import importlib.util
import json

import numpy as np
import helpers as h


def close(a, b, tol=1e-9):
    np.testing.assert_allclose(a, b, atol=tol, rtol=tol)


def rows(path):
    with gzip.open(path, 'rt') as handle:
        return [json.loads(line) for line in handle]


def audit_inner(path, expected, completed=None):
    log = rows(path)
    context = log[0]
    assert context['kind'] == 'context'
    assert all(context[key] == expected[key] for key in ['y', 'lam', 'mu', 'rho', 'stage', 'eps', 'p'])
    f = h.stage4.Frozen(context)
    point = np.array(context['y'])
    value, gradient = f.eval(point)
    assert log[1]['kind'] == 'input' and log[1]['y'] == context['y']
    close(value, log[1]['value'])
    close(max(abs(gradient)), log[1]['gradient_inf'])
    accepted = 0
    for entry in log[2:]:
        assert entry['kind'] == 'accepted' and entry['iteration'] == accepted+1
        next_point = np.array(entry['y'])
        next_value, next_gradient = f.eval(next_point)
        close(next_value, entry['value'])
        close(max(abs(next_gradient)), entry['gradient_inf'], 1e-8)
        fallback = entry['prediction'] <= 1e-13*max(1., abs(value))
        assert fallback == entry['gradient_fallback']
        if fallback:
            assert np.linalg.norm(next_gradient) < np.linalg.norm(gradient)
            close(entry['ratio'], 1.)
        else:
            close((value-next_value)/entry['prediction'], entry['ratio'], 1e-8)
            assert entry['ratio'] > 1e-4
        value, gradient, point = next_value, next_gradient, next_point
        accepted += 1
    if completed is not None:
        assert point.tolist() == completed['y']
        assert accepted == completed['inner']['accepted']
        close(max(abs(gradient)), completed['inner']['gradient_inf'], 1e-8)
        assert completed['inner']['hessian_gradient_calls'] == (1+2*f.m.n)*completed['inner']['jacobian_calls']
    f.close()
    return accepted, point.tolist()


def independent_stationarity(f, saved):
    y, lam, mu = (np.array(saved[key]) for key in ['y', 'lam', 'mu'])
    q, le, mi = f.m.reference_state(y, lam, mu)
    ref = f.m.reference
    jac = ref.jacobian(q)
    _, gf = ref.eval(q, np.zeros(ref.me), np.zeros(ref.mi), 0.)
    gradient = gf+jac[:ref.me].T@le+jac[ref.me:].T@mi
    close(max(abs(gradient)), saved['common_kkt']['stat'], 1e-8)
    close(max(abs(gradient/ref.scale)), saved['paper_units_kkt']['stat'], 1e-8)


def main():
    source = json.loads(h.SOURCE.read_text())
    last_stage, checks, total_outer, accepted_points, interrupted_points = source, [], 0, 0, 0
    for folder in sorted((h.HERE/'stages').glob('stage*')):
        initial = json.loads((folder/'initial.json').read_text())
        result = json.loads((folder/'result.json').read_text())
        assert initial['y'] == last_stage['y'] and (last_stage['stage'] == 0 or last_stage['stage_pass'] or h.advance_anyway(last_stage['stage'], last_stage['stop']))
        assert initial['stage'] == last_stage['stage']+1
        assert initial['rho'] == 1e4 and not any(initial['lam']) and not any(initial['mu'])
        previous, previous_v, expected_rho = initial, None, initial['rho']
        saved = rows(folder/'outer.jsonl.gz')
        for row in saved:
            context = dict(previous, rho=expected_rho)
            count, _ = audit_inner(folder/f"inner{row['outer']:04d}.jsonl.gz", context, row)
            accepted_points += count
            f = h.stage4.Frozen(context)
            y = np.array(row['y'])
            value, gradient = f.eval(y)
            close(value, row['inner']['value'])
            close(row['lam'], f.lam+row['rho']*f.m.h)
            close(row['mu'], np.maximum(0., f.mu+row['rho']*f.m.g))
            measured = f.m.metrics(y, np.array(row['lam']), np.array(row['mu']))
            for key in ['common_kkt', 'paper_units_kkt']:
                close(list(measured[key].values()), list(row[key].values()))
            violation = max(measured['common_kkt']['feas'], measured['common_kkt']['comp'])
            common = max(measured['common_kkt'].values()) <= h.tolerance(row['stage'])
            physical = max(measured['paper_units_kkt'].values()) <= 1e-6
            passed = common and (row['stage'] != 13 or physical)
            assert row['common_pass'] == common and row['physical_pass'] == physical and row['stage_pass'] == passed
            assert row['previous_violation'] == previous_v and row['rho'] == expected_rho
            increase = violation > h.tolerance(row['stage']) and previous_v is not None and violation > .25*previous_v and max(abs(gradient)) <= 1e-6 and not passed
            expected_rho = min(1e8, 10*row['rho']) if increase else row['rho']
            assert expected_rho == row['rho_next']
            previous, previous_v = row, violation
            f.close()
        assert result['completed_outer'] == len(saved)
        assert all(result[key] == previous[key] for key in ['y', 'lam', 'mu']) and result['rho'] == expected_rho
        if (folder/'interrupted-inner.json').exists():
            interrupted = json.loads((folder/'interrupted-inner.json').read_text())
            count, point = audit_inner(folder/f'inner{len(saved)+1:04d}.jsonl.gz', dict(previous, rho=expected_rho))
            assert point == interrupted['last_accepted_y']
            interrupted_points += count
        f = h.stage4.Frozen(result)
        independent_stationarity(f, result)
        document = json.loads((folder/'solution.json').read_text())
        assert document['init'] == h.tr.decode(f.m, np.array(initial['y']), f.m.source)
        assert document['metrics']['converged'] == (result['stage'] == 13 and result['common_pass'])
        check = dict(stage=result['stage'], outer=len(saved), common_pass=result['common_pass'],
            physical_pass=result['physical_pass'], stop=result['stop'])
        checks.append(check)
        total_outer += len(saved)
        last_stage = result
        f.close()
    overall = json.loads((h.HERE/'result.json').read_text())
    assert overall['total_outer'] == total_outer
    assert all(overall[key] == last_stage[key] for key in ['y', 'lam', 'mu', 'rho', 'stage'])
    restored = None
    if (h.HERE/'restored/result.json').exists():
        restored = json.loads((h.HERE/'restored/result.json').read_text())
        assert overall['final_common_pass']
        if restored['accepted']:
            spec = importlib.util.spec_from_file_location('verify_follow_branch', h.ROOT/'experiments/2026-11-14-restoration/fixed_branch.py')
            fb = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(fb)
            raw = fb.restore_source(json.loads((h.HERE/'solution.json').read_text()))
            model = fb.FixedBranch(raw, moving=True)
            data = json.loads((h.HERE/'restored/solution.json').read_text())
            solver = json.loads((h.HERE/'restored/solver.json').read_text())
            measured = model.kkt(np.array(solver['point']), np.array(solver['lam']), np.array(solver['lam_x']))
            close(list(measured.values()), list(restored['raw_kkt'].values()))
            assert max(measured.values()) <= 1e-6
            assert raw['modes'] == data['modes'] and raw['task_stamp'] == data['task_stamp']
            replay = fb.diag.replay(data)
            close(replay, data['solution']['e'], 1e-12)
            assert min(replay) >= 0. and max(replay) <= 1.
            assert min(data['history']['e']) >= 0. and max(data['history']['e']) <= 1.
            assert fb.diag.residuals(data)['viol'] <= 1e-6
    h.write(h.HERE/'verification.json', dict(stages=checks, completed_outer=total_outer,
        accepted_inner_points=accepted_points, interrupted_accepted_points=interrupted_points,
        original_jacobian_stationarity_verified=True, restoration=restored))
    print(json.dumps(dict(stages=len(checks), completed_outer=total_outer,
        accepted_inner_points=accepted_points, interrupted_accepted_points=interrupted_points,
        final_common_pass=overall['final_common_pass'], final_both_scales_pass=overall['final_both_scales_pass'],
        restoration_accepted=restored['accepted'] if restored else False)))


if __name__ == '__main__':
    main()
