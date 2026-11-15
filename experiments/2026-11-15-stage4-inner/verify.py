"""Audit frozen AL results and their gradients using constraint Jacobians."""
import gzip
import json
import numpy as np
import support as s
from decomposition import hessian_of_al


def close(a, b, tol=1e-9):
    np.testing.assert_allclose(a, b, atol=tol, rtol=tol)


def main():
    checks = []
    for folder in sorted((s.HERE/'cases').glob('*/*')):
        initial = json.loads((folder/'initial.json').read_text())
        result = json.loads((folder/'result.json').read_text())
        frozen = s.Frozen(initial)
        y = np.array(result['y'])
        value, gradient = frozen.eval(y)
        close(value, result['value'])
        close(gradient, result['gradient'])
        centered, gb = frozen.eval(y, stable=True)
        assert np.array_equal(gradient, gb)
        close(centered, result['centered_value'])
        close(centered+frozen.value0, value, 1e-11)
        h, g = frozen.m.h.copy(), frozen.m.g.copy()
        effective_lam, effective_mu = frozen.lam+frozen.rho*h, np.maximum(0., frozen.mu+frozen.rho*g)
        jac = frozen.m.jacobian(y)
        _, gf = frozen.m.eval(y, np.zeros(frozen.m.me), np.zeros(frozen.m.mi), 0.)
        independent = gf+jac[:frozen.m.me].T@effective_lam+jac[frozen.m.me:].T@effective_mu
        close(independent, gradient, 1e-8)
        assert result['gradient_pass'] == (not result['interrupted'] and max(abs(gradient)) <= 1e-8)
        for key, lam, mu in [('fixed_dual_kkt', frozen.lam, frozen.mu), ('one_update_kkt', effective_lam, effective_mu)]:
            measured = frozen.m.metrics(y, lam, mu)
            for sub in ['common_kkt', 'paper_units_kkt']:
                close(list(measured[sub].values()), list(result[key][sub].values()))
            q, le, mi = frozen.m.reference_state(y, lam, mu)
            ref = frozen.m.reference
            jr = ref.jacobian(q)
            _, gf = ref.eval(q, np.zeros(ref.me), np.zeros(ref.mi), 0.)
            direct = gf+jr[:ref.me].T@le+jr[ref.me:].T@mi
            close(max(abs(direct)), measured['common_kkt']['stat'], 1e-8)
        with gzip.open(folder/'evaluations.jsonl.gz', 'rt') as handle:
            history = [json.loads(line) for line in handle]
        assert len(history) == result['observed_evaluations']
        assert [row['evaluation'] for row in history] == list(range(1, len(history)+1))
        ordinary, gradient0 = frozen.eval(frozen.anchor)
        close(history[0]['value'], 0. if result['method'] == 'stable-bfgs' else ordinary)
        close(history[0]['gradient_inf'], max(abs(gradient0)))
        assert result['lam'] == initial['lam'] and result['mu'] == initial['mu'] and result['rho'] == initial['rho']
        doc = json.loads((folder/'solution.json').read_text())
        assert doc['init'] == s.old.fidelity.tr.decode(frozen.m, frozen.anchor, frozen.m.source)
        assert not doc['metrics']['converged']
        common_pass = max(result['one_update_kkt']['common_kkt'].values()) <= 1e-6
        checks.append(dict(problem=result['problem'], method=result['method'],
            gradient_inf=result['gradient_inf'], inner_pass=result['gradient_pass'],
            one_update_common_pass=common_pass, evaluations=len(history)))
        if result['method'] == 'newton-decomposed':
            s.write(folder/'one-update-state.json', dict(y=y.tolist(), lam=effective_lam.tolist(),
                mu=effective_mu.tolist(), rho=frozen.rho, eps=initial['eps'], p=initial['p'], stage=4,
                **result['one_update_kkt'], common_kkt_pass=common_pass,
                note='alternative output of outer 200, using duals from outer 199; not a continuation or final-stage success'))
        frozen.close()
    matrices = np.load(s.HERE/'decomposed-hessians.npz')
    decomposition = json.loads((s.HERE/'decomposition.json').read_text())
    states = json.loads((s.HERE/'inputs.json').read_text())
    for row in decomposition:
        frozen = s.Frozen(states[row['problem']])
        H, skew = hessian_of_al(frozen, frozen.anchor, 1e-7)
        close(H, matrices[row['problem']+'_decomposed_1e-07'], 1e-10)
        eigen = np.linalg.eigvalsh(H)
        target = next(v for v in row['estimates'] if v['kind'] == 'decomposed' and v['step'] == 1e-7)
        close(eigen[[0, -1]], [target['min_eigenvalue'], target['max_eigenvalue']], 1e-7)
        # A finite-step directional consistency check. Some switch surfaces can
        # lie inside this interval; this does not certify the tiny eigenvalues.
        v = np.cos(np.arange(len(frozen.anchor))+.2)
        v /= np.linalg.norm(v)
        step = 1e-10
        fd = (frozen.eval(frozen.anchor+step*v)[1]-frozen.eval(frozen.anchor-step*v)[1])/(2*step)
        error = float(np.linalg.norm(fd-H@v)/max(1., np.linalg.norm(H@v)))
        assert error < 1e-4, (row['problem'], error)
        row['independent_hessian_direction_relative_error'] = error
        frozen.close()
    assert (s.HERE/'follow-skipped.json').exists() and not (s.HERE/'follow').exists()
    s.write(s.HERE/'verification.json', dict(cases=checks, cases_checked=len(checks),
        logged_evaluations=sum(v['evaluations'] for v in checks),
        hessian_direction_errors={r['problem']: r['independent_hessian_direction_relative_error'] for r in decomposition},
        fixed_AL_inputs_and_duals=True, conditional_follow_skipped=True))
    print(json.dumps(dict(cases=len(checks), inner_pass=sum(v['inner_pass'] for v in checks),
        one_update_common_pass=sum(v['one_update_common_pass'] for v in checks),
        hessian_direction_errors={r['problem']: r['independent_hessian_direction_relative_error'] for r in decomposition})))


if __name__ == '__main__':
    main()
