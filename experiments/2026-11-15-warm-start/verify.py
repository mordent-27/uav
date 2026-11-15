"""Read-only verification of AL traces, independent final KKT, and restored outputs."""
import gzip
import json
import math
from pathlib import Path

import numpy as np
import controls as c
import restore as restoration


def close(actual, expected, tol=1e-9):
    np.testing.assert_allclose(actual, expected, rtol=tol, atol=tol)


def main():
    model, original = (c.tr.Model(0, 0, c.tr.LIBRARIES[k]) for k in ['normalized', 'original'])
    source, seed = c.load_seed(model)
    folders = sorted((c.HERE / 'runs').glob('*'))
    for name in ['newton', 'newton-default']:
        if (c.HERE / name).exists():
            folders.append(c.HERE / name)
    checked = []
    for folder in folders:
        initial = json.loads((folder / 'initial.json').read_text())
        final = json.loads((folder / 'result.json').read_text())
        seed_kind = initial.get('seed_kind', 'good')
        active_source, active_seed = c.load_seed(model, seed_kind)
        if not folder.name.startswith('newton'):
            close(initial['y'], active_seed, 1e-14)
            assert not any(initial['lam']) and not any(initial['mu'])
        else:
            parent = json.loads((c.HERE / initial['parent']).read_text())
            assert all(initial[k] == parent[k] for k in ['y', 'lam', 'mu', 'rho'])
        with gzip.open(folder / 'outer.jsonl.gz', 'rt') as log:
            rows = [json.loads(line) for line in log]
        previous = initial
        for row in rows:
            model.stage(row['eps'], row['p'])
            original.stage(row['eps'], row['p'])
            y, lam, mu = (np.array(row[k]) for k in ['y', 'lam', 'mu'])
            old_lam, old_mu = (np.array(previous[k]) for k in ['lam', 'mu'])
            assert row['rho'] == 1e4
            model.eval(y, old_lam, old_mu, 0.)
            close(lam, old_lam + 1e4*model.h)
            close(mu, np.maximum(0., old_mu + 1e4*model.g))
            expected = c.assess(model, original, y, lam, mu, active_source, row['eps'], row['p'])
            for key in ['normalized_kkt', 'original_kkt']:
                close(list(row[key].values()), list(expected[key].values()))
            close(row['objective'], expected['objective'])
            assert [r['winner'] for r in row['selection']['modes']] == [r['winner'] for r in expected['selection']['modes']]
            previous = row
        assert len(rows) == final['outer_total']
        assert all(previous[k] == final[k] for k in ['y', 'lam', 'mu', 'rho'])
        # Independent stationarity calculation from the original Jacobian and gradient.
        y, lam, mu = (np.array(final[k]) for k in ['y', 'lam', 'mu'])
        model.stage(final['eps'], final['p'])
        original.stage(final['eps'], final['p'])
        mapped = c.tr.original_multipliers(model, y, active_source, mu)
        jac = original.jacobian(y)
        _, gf = original.eval(y, np.zeros(original.me), np.zeros(original.mi), 0.)
        gradient = gf + jac[:original.me].T@lam + jac[original.me:].T@mapped
        close(max(abs(gradient)), final['original_kkt']['stat'], 1e-8)
        assert final['kkt_converged'] == (final['stage'] == 13 and max(final['original_kkt'].values()) <= 1e-6)
        checked.append(dict(name=folder.name, rows=len(rows), independent_stationarity=float(max(abs(gradient)))))
    model.close()
    original.close()
    proofs = json.loads((c.HERE / 'prefix-certificates.json').read_text())
    prefix_failures = []
    for name, proof in proofs.items():
        if not proof['infeasible']:
            continue
        path = (c.HERE.parent / '2026-11-15-library-trace/runs' / name.removeprefix('previous-')) if name.startswith('previous-') else c.HERE / 'runs' / name
        doc = json.loads((path / 'solution.json').read_text())
        first = proof['first_charging_segment']
        assert all(m < 0 for m in doc['modes'][:first])
        stamps = [doc['task_stamp'][i] for i in proof['prefix_tasks']]
        assert stamps == sorted(stamps) == proof['prefix_task_stamps'] and max(stamps) <= first
        points = [doc['instance']['r0']] + [doc['instance']['tasks'][i] for i in proof['prefix_tasks']]
        distance = sum(math.dist(points[i], points[i+1]) for i in range(len(points)-1))
        p = doc['phys']
        capacity = p['v_d']*(p['e_max']-p['e_min'])/p['zeta']
        assert abs(distance-proof['distance_lower_bound_km']) < 1e-12 and distance > capacity
        prefix_failures.append(name)
    physical = []
    for folder in sorted((c.HERE / 'restored').glob('*')):
        result = json.loads((folder / 'result.json').read_text())
        if not result['accepted']:
            assert not (folder / 'solution.json').exists()
            continue
        doc = json.loads((folder / 'solution.json').read_text())
        raw = json.loads((folder / 'solver.json').read_text())
        assert c.tr.diag.residuals(doc)['viol'] < 1e-10
        replay = c.tr.diag.replay(doc)
        close(replay, doc['solution']['e'], 1e-14)
        assert min(replay) >= 0. and max(replay) <= 1.
        fb = restoration.fb.FixedBranch(doc, moving=True)
        trajectory = doc['solution']
        point = np.r_[np.array(trajectory['r'])[fb.free].ravel(),
            np.array(trajectory['e'][1:])*fb.range, np.array(trajectory['s'])*fb.p['v_d']]
        kkt = fb.kkt(point, np.array(raw['lam']), np.array(raw['lam_x']))
        assert max(kkt.values()) <= 1e-6
        close(list(kkt.values()), list(result['final_kkt'].values()))
        rawdoc = json.loads((c.ROOT / result['source'] / 'solution.json').read_text())
        assert doc['modes'] == rawdoc['modes'] and doc['task_stamp'] == rawdoc['task_stamp']
        physical.append(dict(name=folder.name, objective=sum(trajectory['s']), kkt=kkt))
    c.tr.write(c.HERE / 'verification.json', dict(identical_seed_within_each_group=True, raw=checked, restored=physical,
        prefix_infeasible_certificates=prefix_failures,
        original_jacobian_stationarity=True, al_updates=True, pure_battery_replay=True))
    print(json.dumps(dict(raw=len(checked), states=sum(r['rows'] for r in checked), restored=len(physical))))


if __name__ == '__main__':
    main()
