"""Re-evaluate saved states, dual updates and the prescribed factorial controls."""
import gzip
import json

import numpy as np
import run as experiment

HERE, c = experiment.HERE, experiment.c


def rows(folder):
    with gzip.open(folder/'outer.jsonl.gz', 'rt') as handle:
        return [json.loads(line) for line in handle]


def close(a, b, tol=1e-9):
    np.testing.assert_allclose(a, b, atol=tol, rtol=tol)


def main():
    source = json.loads(experiment.SOURCE.read_text())
    folders = sorted((HERE/'cases').glob('*'))
    folders += sorted((HERE/'follow').glob('stage*'))
    checks, parent, initial_constraints = [], None, None
    for folder in folders:
        initial = json.loads((folder/'initial.json').read_text())
        result = json.loads((folder/'result.json').read_text())
        if folder.parent.name == 'cases':
            assert initial['y'] == source['y']
            for key in ['lam', 'mu']:
                expected = [0.]*len(source[key]) if initial['dual_reset'] else source[key]
                assert initial[key] == expected
            assert initial['rho'] == (1e4 if initial['rho_reset'] else source['rho'])
        else:
            if parent is None:
                parent = json.loads((HERE/'cases/dual-reset_rho-reset_gated/result.json').read_text())
            assert parent['target_kkt_pass'] and initial['y'] == parent['y']
            assert initial['stage'] == parent['stage']+1 and initial['rho'] == 1e4
            assert not any(initial['lam']) and not any(initial['mu']) and initial['gate']
            parent = result
        m = c.fidelity.Variant('R')
        m.stage(initial['eps'], initial['p'])
        m.eval(np.array(initial['y']), np.zeros(m.me), np.zeros(m.mi), 0.)
        if folder.parent.name == 'cases':
            constraints = np.r_[m.h, m.g]
            if initial_constraints is None:
                initial_constraints = constraints.copy()
            assert np.array_equal(constraints, initial_constraints)
        previous, expected_rho, previous_v = initial, initial['rho'], None
        saved = rows(folder)
        for row in saved:
            assert row['rho'] == expected_rho
            y, lam, mu = (np.array(row[key]) for key in ['y', 'lam', 'mu'])
            old_lam, old_mu = np.array(previous['lam']), np.array(previous['mu'])
            value, gradient = m.eval(y, old_lam, old_mu, row['rho'])
            close(value, row['inner']['value'])
            close(max(abs(gradient)), row['inner']['gradient_inf'])
            close(lam, old_lam+row['rho']*m.h)
            close(mu, np.maximum(0., old_mu+row['rho']*m.g))
            measured = m.metrics(y, lam, mu)
            for key in ['common_kkt', 'paper_units_kkt']:
                close(list(measured[key].values()), list(row[key].values()))
            violation = max(measured['common_kkt']['feas'], measured['common_kkt']['comp'])
            close(violation, row['violation'])
            passed = max(measured['common_kkt'].values()) <= 1e-6
            assert row['previous_violation'] == previous_v
            # Reconstruct the decision directly, without calling run.penalty.
            allowed = violation > 1e-6 and (not initial['gate'] or max(abs(gradient)) <= 1e-6)
            increased = allowed and not passed and previous_v is not None and violation > .25*previous_v
            expected_rho = min(1e8, 10*row['rho']) if increased else row['rho']
            assert expected_rho == row['rho_next']
            assert row['gate'] == initial['gate']
            previous_v, previous = violation, row
        assert result['additional_outer'] == len(saved)
        assert all(result[key] == previous[key] for key in ['y', 'lam', 'mu'])
        assert result['rho'] == expected_rho
        y, lam, mu = (np.array(result[key]) for key in ['y', 'lam', 'mu'])
        q, le, mi = m.reference_state(y, lam, mu)
        ref = m.reference
        jac = ref.jacobian(q)
        _, gf = ref.eval(q, np.zeros(ref.me), np.zeros(ref.mi), 0.)
        grad = gf+jac[:ref.me].T@le+jac[ref.me:].T@mi
        close(max(abs(grad)), result['common_kkt']['stat'], 1e-8)
        close(max(abs(grad/ref.scale)), result['paper_units_kkt']['stat'], 1e-8)
        assert result['target_kkt_pass'] == (max(result['common_kkt'].values()) <= 1e-6)
        assert result['final_kkt_pass'] == (result['stage'] == 13 and result['target_kkt_pass'])
        doc = json.loads((folder/'solution.json').read_text())
        assert doc['init'] == c.fidelity.tr.decode(m, np.array(initial['y']), m.source)
        assert doc['metrics']['converged'] == result['final_kkt_pass']
        checks.append(dict(name=folder.name, states=len(saved), passed=result['target_kkt_pass'],
            independent_stationarity=float(max(abs(grad))), stop=result['stop']))
        m.close()
    # The measured second outer iteration is the first gate-dependent decision.
    plain = rows(HERE/'cases/dual-carry_rho-carry_plain')
    gated = rows(HERE/'cases/dual-carry_rho-carry_gated')
    for a, b in zip(plain[:2], gated[:2]):
        assert all(a[k] == b[k] for k in ['y', 'lam', 'mu', 'rho'])
    assert plain[1]['rho_next'] == 1e7 and gated[1]['rho_next'] == 1e6
    prior = rows(experiment.PRIOR/'follow-guarded')
    comparisons = []
    for a, b in zip(plain, prior):
        # Record numerical reproducibility rather than assume bitwise equality
        # across independent solves at a poorly conditioned starting point.
        comparisons.append(float(np.max(np.abs(np.array(a['y'])-np.array(b['y'])))))
    same_baseline = len(plain) == len(prior) and all(
        all(a[k] == b[k] for k in ['y', 'lam', 'mu', 'rho', 'rho_next'])
        for a, b in zip(plain, prior))
    assert same_baseline
    summary = dict(cases=checks, states=sum(v['states'] for v in checks),
        all_eight_initial_primals_and_constraints_identical=True,
        first_two_gate_control_states_identical=True,
        old_baseline_all_200_states_identical=same_baseline,
        old_baseline_first_y_max_difference=comparisons[0],
        old_baseline_last_y_max_difference=comparisons[-1],
        old_baseline_rho_sequence_identical=[r['rho'] for r in plain] == [r['rho'] for r in prior])
    experiment.write(HERE/'verification.json', summary)
    print(json.dumps(summary))


if __name__ == '__main__':
    main()
