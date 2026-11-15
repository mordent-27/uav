"""Independent audits of saved AL updates, penalty decisions, curvature and CLI pairs."""
import gzip
import json
import numpy as np
import common as c
import curvature


def read_rows(folder):
    with gzip.open(folder/'outer.jsonl.gz', 'rt') as handle:
        return [json.loads(line) for line in handle]


def close(a, b, tol=1e-9):
    np.testing.assert_allclose(a, b, atol=tol, rtol=tol)


def main():
    _, source = c.source()
    folders = sorted((c.HERE/'cases').glob('*'))
    folders += [p for p in [c.HERE/'follow', c.HERE/'follow-guarded'] if (p/'result.json').exists()]
    checked = []
    for folder in folders:
        m = c.model()
        initial = json.loads((folder/'initial.json').read_text())
        result = json.loads((folder/'result.json').read_text())
        if folder.parent.name == 'cases':
            assert all(initial[k] == source[k] for k in ['y', 'lam', 'mu'])
            assert initial['rho'] == (1e5 if folder.name == 'raised-bfgs' else 1e4)
        else:
            parent = json.loads((c.HERE/initial['parent']).read_text())
            assert all(initial[k] == parent[k] for k in ['y', 'lam', 'mu', 'rho'])
        previous, previous_stage, previous_v, expected_rho = initial, None, None, initial['rho']
        rows = read_rows(folder)
        for row in rows:
            stage = row['stage']
            if stage != previous_stage:
                if previous_stage is not None:
                    assert max(previous['common_kkt'].values()) <= 1e-6
                previous_v, previous_stage = None, stage
            m.stage(row['eps'], row['p'])
            assert row['rho'] == expected_rho
            y, lam, mu = (np.array(row[k]) for k in ['y', 'lam', 'mu'])
            old_lam, old_mu = np.array(previous['lam']), np.array(previous['mu'])
            value, gradient = m.eval(y, old_lam, old_mu, row['rho'])
            close(value, row['inner']['value'])
            close(max(abs(gradient)), row['inner']['gradient_inf'])
            close(lam, old_lam+row['rho']*m.h)
            close(mu, np.maximum(0., old_mu+row['rho']*m.g))
            metrics = m.metrics(y, lam, mu)
            for key in ['common_kkt', 'paper_units_kkt']:
                close(list(metrics[key].values()), list(row[key].values()))
            violation = max(metrics['common_kkt']['feas'], metrics['common_kkt']['comp'])
            passed = max(metrics['common_kkt'].values()) <= 1e-6
            assert row['previous_violation'] == previous_v
            policy = initial['policy']
            eligible = policy == 'adaptive' or (policy == 'guarded' and violation > 1e-6)
            next_rho = min(1e8, row['rho']*10) if eligible and not passed and previous_v is not None and violation > .25*previous_v else row['rho']
            assert next_rho == row['rho_next']
            previous_v, expected_rho, previous = violation, next_rho, row
        assert len(rows) == result['additional_outer']
        assert all(previous[k] == result[k] for k in ['y', 'lam', 'mu']) and result['rho'] == expected_rho
        y, lam, mu = (np.array(result[k]) for k in ['y', 'lam', 'mu'])
        m.stage(result['eps'], result['p'])
        q, le, mi = m.reference_state(y, lam, mu)
        ref = m.reference
        jac = ref.jacobian(q)
        _, gf = ref.eval(q, np.zeros(ref.me), np.zeros(ref.mi), 0.)
        gradient = gf+jac[:ref.me].T@le+jac[ref.me:].T@mi
        close(max(abs(gradient)), result['common_kkt']['stat'], 1e-8)
        close(max(abs(gradient/ref.scale)), result['paper_units_kkt']['stat'], 1e-8)
        assert result['target_kkt_pass'] == (max(result['common_kkt'].values()) <= 1e-6)
        assert not result['final_kkt_pass']
        doc = json.loads((folder/'solution.json').read_text())
        expected_init = c.fidelity.tr.decode(m, np.array(initial['y']), m.source)
        assert doc['init'] == expected_init
        checked.append(dict(name=folder.name, states=len(rows), target_kkt_pass=result['target_kkt_pass'],
                            independent_common_stationarity=float(max(abs(gradient)))))
        m.close()
    a, b = read_rows(c.HERE/'cases/adaptive-bfgs'), read_rows(c.HERE/'cases/guarded-bfgs')
    for i in range(5):
        assert all(a[i][k] == b[i][k] for k in ['y', 'lam', 'mu', 'rho'])
    assert a[4]['rho_next'] == 1e7 and b[4]['rho_next'] == 1e6
    spectra = json.loads((c.HERE/'curvature.json').read_text())
    reconstruction = json.loads((c.HERE/'reconstruction.json').read_text())
    matrices = np.load(c.HERE/'hessians.npz')
    m = c.model()
    point = reconstruction['point']
    y = np.array(point['y'])
    for row in spectra:
        lam = np.array(reconstruction['previous_lam'] if row['target'] == 'solved' else point['lam'])
        mu = np.array(reconstruction['previous_mu'] if row['target'] == 'solved' else point['mu'])
        H = matrices[row['target']+'_'+str(row['step'])]
        eigen = np.linalg.eigvalsh(H)
        close(eigen, row['eigenvalues'], 1e-7)
        close(H@np.array(row['direction']), row['minimum_eigenvalue']*np.array(row['direction']), 1e-8)
        fg = lambda q: m.eval(np.ascontiguousarray(q), lam, mu, point['rho'])
        if row['step'] == 1e-7:
            recomputed, _ = curvature.hessian(fg, y, row['step'])
            close(recomputed, H, 1e-9)
        f0, _ = fg(y)
        for sample in row['samples']:
            v = np.array(row['direction'])
            plus, _ = fg(y+sample['distance']*v)
            minus, _ = fg(y-sample['distance']*v)
            close(plus-f0, sample['plus_delta'], 1e-12)
            close(minus-f0, sample['minus_delta'], 1e-12)
    m.close()
    pilots = []
    for name in ['tau1', 'tau3', 'fig1']:
        before = json.loads((c.HERE/'native/before'/(name+'.json')).read_text())
        after = json.loads((c.HERE/'native/after'/(name+'.json')).read_text())
        assert all(before[k] == after[k] for k in ['instance', 'phys', 'init'])
        pilots.append(dict(name=name, before_objective=before['metrics']['objective'], after_objective=after['metrics']['objective'],
            before_violation=before['metrics']['viol'], after_violation=after['metrics']['viol'],
            same_trajectory=before['solution'] == after['solution']))
    c.write(c.HERE/'verification.json', dict(cases=checked, states=sum(v['states'] for v in checked),
        first_five_states_identical=True, first_penalty_difference_at_extra_outer=5, curvature_checks=True, native_pilots=pilots))
    print(json.dumps(dict(cases=len(checked), states=sum(v['states'] for v in checked), native_pilots=pilots)))


if __name__ == '__main__':
    main()
