"""Read-only check of every saved AL update and final common-coordinate KKT."""
import gzip
import json
from pathlib import Path
import numpy as np
import run as r


def close(a, b, tol=1e-9):
    np.testing.assert_allclose(a, b, rtol=tol, atol=tol)


def main():
    checked, initial_x = [], None
    for folder in sorted((r.HERE/'cases').glob('*')):
        initial = json.loads((folder/'initial.json').read_text())
        result = json.loads((folder/'result.json').read_text())
        model = r.Variant(initial['kind'])
        assert initial['rho'] == 1e4 and not any(initial['lam']) and not any(initial['mu'])
        if initial_x is None:
            initial_x = initial['physical_variables']
        assert initial['physical_variables'] == initial_x
        close(np.array(initial['y'])*np.array(initial['scale']), initial_x, 1e-14)
        with gzip.open(folder/'outer.jsonl.gz', 'rt') as handle:
            rows = [json.loads(line) for line in handle]
        previous, current_stage, passed = initial, None, {}
        for row in rows:
            stage = row['stage']
            if stage != current_stage:
                entry = json.loads((folder/f'stage{stage:02d}-start.json').read_text())
                assert all(entry[k] == previous[k] for k in ['y', 'lam', 'mu'])
                current_stage = stage
            assert row['rho'] == 1e4
            assert row['eps'] == max(.0005, .2*.6**(stage-1))
            assert row['p'] == min(12., 2.*1.2**(stage-1))
            model.stage(row['eps'], row['p'])
            y, lam, mu = (np.array(row[k]) for k in ['y', 'lam', 'mu'])
            old_lam, old_mu = np.array(previous['lam']), np.array(previous['mu'])
            value, gradient = model.eval(y, old_lam, old_mu, 1e4)
            close(value, row['inner']['value'])
            close(max(abs(gradient)), row['inner']['gradient_inf'])
            close(lam, old_lam+1e4*model.h)
            close(mu, np.maximum(0., old_mu+1e4*model.g))
            metrics = model.metrics(y, lam, mu)
            for key in ['common_kkt', 'paper_units_kkt']:
                close(list(metrics[key].values()), list(row[key].values()))
            selection = r.tr.describe(model, y, model.source, row['eps'], row['p'])
            assert [v['winner'] for v in selection['modes']] == [v['winner'] for v in row['selection']['modes']]
            previous = row
            passed[stage] = max(row['common_kkt'].values()) <= 1e-6
        assert len(rows) == result['total_outer']
        assert all(previous[k] == result[k] for k in ['y', 'lam', 'mu'])
        assert sum(s['completed_outer'] for s in result['stages']) == len(rows)
        assert result['passed_stages'] == sum(s['common_kkt_pass'] for s in result['stages'])
        for stage in result['stages']:
            expected_limit = (30 if stage['stage'] == 13 else 10) if initial['budget'] == 'short' else (300 if stage['stage'] == 13 else 100)
            assert stage['budget'] == expected_limit and stage['completed_outer'] <= expected_limit
        model.stage(result['eps'], result['p'])
        y, lam, mu = (np.array(result[k]) for k in ['y', 'lam', 'mu'])
        q, le, mi = model.reference_state(y, lam, mu)
        ref = model.reference
        jac = ref.jacobian(q)
        _, gf = ref.eval(q, np.zeros(ref.me), np.zeros(ref.mi), 0.)
        gradient = gf+jac[:ref.me].T@le+jac[ref.me:].T@mi
        close(max(abs(gradient)), result['common_kkt']['stat'], 1e-8)
        close(max(abs(gradient/ref.scale)), result['paper_units_kkt']['stat'], 1e-8)
        assert result['final_kkt_pass'] == (result['completed_schedule'] and max(result['common_kkt'].values()) <= 1e-6)
        checked.append(dict(case=folder.name, states=len(rows), final_stage=result['stage'], stop=result['stop'],
            independent_common_stationarity=float(max(abs(gradient))), independent_physical_stationarity=float(max(abs(gradient/ref.scale)))))
        model.close()
    assert len(checked) == 8
    r.tr.write(r.HERE/'verification.json', dict(same_initial_physical_point=True, rows=sum(c['states'] for c in checked),
        cases=checked, al_updates=True, common_coordinate_kkt=True, physical_coordinate_kkt=True))
    print(json.dumps(dict(cases=len(checked), states=sum(c['states'] for c in checked))))


if __name__ == '__main__':
    main()
