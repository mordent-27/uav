"""Re-evaluate saved states, AL updates, KKT and paired inner solves; no optimization."""
import gzip
import json
import math
from pathlib import Path
import numpy as np
import trace as tr


def close(actual, expected, tolerance=1e-9):
    np.testing.assert_allclose(actual, expected, rtol=tolerance, atol=tolerance)


def main():
    original = tr.Model(0, 0, tr.LIBRARIES['original'])
    model = tr.Model(0, 0, tr.LIBRARIES['normalized'])
    template = model.solution(model.y)
    first = None
    counts = {}
    for backend in tr.BACKENDS:
        folder = tr.HERE / 'runs' / backend
        initial = json.loads((folder / 'initial.json').read_text())
        if first is None:
            first = initial
        assert initial == first
        final = json.loads((folder / 'result.json').read_text())
        with gzip.open(folder / 'outer.jsonl.gz', 'rt') as handle:
            rows = [json.loads(line) for line in handle]
        assert len(rows) == final['outer_total']
        states = {}
        for row in rows:
            stage = row['stage']
            if stage not in states:
                states[stage] = json.loads((folder / f'stage{stage:02d}-start.json').read_text())
                if stage > 1:
                    prior = json.loads((folder / f'stage{stage-1:02d}-end.json').read_text())
                    assert all(states[stage][key] == prior[key] for key in ['y', 'lam', 'mu', 'rho'])
            before = states[stage]
            assert row['outer'] == before.get('outer', 0) + 1
            assert row['rho'] == 1e4
            eps, p = max(.0005, .2*.6**(stage-1)), min(12., 2.*1.2**(stage-1))
            assert row['eps'] == eps and row['p'] == p
            y, lam, mu = (np.array(row[key]) for key in ['y', 'lam', 'mu'])
            old_lam, old_mu = (np.array(before[key]) for key in ['lam', 'mu'])
            model.stage(eps, p)
            original.stage(eps, p)
            value, gradient = model.eval(y, old_lam, old_mu, row['rho'])
            close(value, row['inner']['value'])
            close(max(abs(gradient)), row['inner']['gradient_inf'])
            close(lam, old_lam + row['rho']*model.h)
            close(mu, np.maximum(0., old_mu + row['rho']*model.g))
            model.eval(y, lam, mu, 0.)
            recorded_equalities = np.array([r['phi'] - eps for r in row['selection']['tasks'] + row['selection']['modes']])
            close(model.h[model.stamps-1:], recorded_equalities, 1e-12)
            expected = tr.kkt(model, y, lam, mu)
            close(list(expected.values()), list(row['normalized_kkt'].values()))
            canonical = tr.kkt(original, y, lam, tr.original_multipliers(model, y, template, mu))
            close(list(canonical.values()), list(row['original_kkt'].values()))
            assert abs(row['objective'] - sum(tr.decode(model, y, template)['s'])) < 1e-12
            states[stage] = row
        for stage, row in states.items():
            end = json.loads((folder / f'stage{stage:02d}-end.json').read_text())
            assert all(row[key] == end[key] for key in ['y', 'lam', 'mu', 'rho'])
        counts[backend] = dict(rows=len(rows), stages=final['stage'], stop=final['stop'])
    probes = json.loads((tr.HERE / 'probe-summary.json').read_text())
    checked = 0
    for record in probes:
        if record.get('missing'):
            continue
        folder = tr.HERE / 'probes' / f'{record["representation"]}-stage{record["stage"]:02d}'
        initial = json.loads((folder / 'input.json').read_text())
        saved = json.loads((folder / f'{record["backend"]}.json').read_text())
        m = model if record['representation'] == 'normalized' else original
        m.stage(initial['eps'], initial['p'])
        lam, mu = np.array(initial['lam']), np.array(initial['mu'])
        y = np.array(saved['y'])
        value, gradient = m.eval(y, lam, mu, initial['rho'])
        close(value, saved['value'])
        close(max(abs(gradient)), saved['gradient_inf'])
        initial_value, initial_gradient = m.eval(np.array(initial['y']), lam, mu, initial['rho'])
        close(initial_value, saved['initial_value'])
        close(max(abs(initial_gradient)), saved['initial_gradient_inf'])
        assert saved['gradient_pass'] == (saved['gradient_inf'] <= 1e-6)
        assert value <= initial_value + 1e-9*(1+abs(initial_value))
        checked += 1
    original.close()
    model.close()
    certificate = json.loads((tr.HERE / 'bfgs-prefix-certificate.json').read_text())
    doc = json.loads((tr.HERE / 'runs/scipy-bfgs/solution.json').read_text())
    k = certificate['first_charging_segment']
    assert all(mode < 0 for mode in doc['modes'][:k]) and doc['modes'][k] >= 0
    tasks = [doc['instance']['tasks'][i] for i in certificate['prefix_task_indices']]
    stamps = [doc['task_stamp'][i] for i in certificate['prefix_task_indices']]
    assert stamps == sorted(stamps) == certificate['prefix_task_stamps'] and max(stamps) <= k
    points = [doc['instance']['r0']] + tasks
    distance = sum(math.dist(points[i], points[i+1]) for i in range(len(points)-1))
    ph = doc['phys']
    capacity = ph['v_d']*(ph['e_max']-ph['e_min'])/ph['zeta']
    assert distance > capacity and abs(distance-certificate['distance_lower_bound_km']) < 1e-12
    assert abs(capacity-certificate['battery_range_km']) < 1e-12
    tr.write(tr.HERE / 'verification.json', dict(identical_initial_state=True, runs=counts,
        paired_inner_results=checked, al_updates=True, original_kkt=True, recorded_choice_equalities=True,
        bfgs_prefix_infeasible_after_exact_task_restoration=True))
    print(json.dumps(dict(runs=counts, paired_inner_results=checked)))


if __name__ == '__main__':
    main()
