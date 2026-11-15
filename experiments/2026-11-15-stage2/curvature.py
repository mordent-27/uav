"""Frozen AL reconstruction and finite-difference curvature; no minimization."""
import json
import numpy as np
import common as c


def hessian(fg, y, step):
    raw = np.empty((len(y), len(y)))
    for j in range(len(y)):
        a, b = y.copy(), y.copy()
        a[j] += step
        b[j] -= step
        raw[:, j] = (fg(a)[1]-fg(b)[1])/(2*step)
    return (raw+raw.T)/2, float(np.max(abs(raw-raw.T)))


def main():
    assert not (c.HERE/'curvature.json').exists(), 'refuse to overwrite a diagnostic'
    before, after = c.source()
    m = c.model()
    y = np.array(after['y'])
    old_lam, old_mu = np.array(before['lam']), np.array(before['mu'])
    lam, mu, rho = np.array(after['lam']), np.array(after['mu']), after['rho']
    value, gradient = m.eval(y, old_lam, old_mu, rho)
    np.testing.assert_allclose(value, after['inner']['value'], atol=1e-12, rtol=1e-12)
    np.testing.assert_allclose(max(abs(gradient)), after['inner']['gradient_inf'], atol=1e-12, rtol=1e-8)
    np.testing.assert_allclose(lam, old_lam+rho*m.h, atol=1e-12, rtol=1e-12)
    np.testing.assert_allclose(mu, np.maximum(0., old_mu+rho*m.g), atol=1e-12, rtol=1e-12)
    _, lagrangian_gradient = m.eval(y, lam, mu, 0.)
    np.testing.assert_allclose(gradient, lagrangian_gradient, atol=1e-11, rtol=1e-7)
    q = np.ascontiguousarray(y*m.ratio)
    jac = m.jacobian(y)
    _, gf = m.eval(y, np.zeros(m.me), np.zeros(m.mi), 0.)
    independent = gf+jac[:m.me].T@lam+jac[m.me:].T@mu
    np.testing.assert_allclose(independent, gradient, atol=1e-10, rtol=1e-6)
    _, next_gradient = m.eval(y, lam, mu, rho)
    audit = dict(solved_al_value=value, solved_al_gradient_inf=float(max(abs(gradient))),
        updated_lagrangian_gradient_inf=float(max(abs(lagrangian_gradient))),
        next_al_gradient_inf=float(max(abs(next_gradient))),
        multiplier_update_verified=True, gradient_identity_verified=True,
        point=c.state(y, lam, mu, rho), previous_lam=old_lam.tolist(), previous_mu=old_mu.tolist())
    c.write(c.HERE/'reconstruction.json', audit)
    spectra, matrices = [], {}
    for target, a, b in [('solved', old_lam, old_mu), ('next', lam, mu)]:
        fg = lambda point: m.eval(np.ascontiguousarray(point), a, b, rho)
        f0, g0 = fg(y)
        for step in [1e-5, 1e-6, 1e-7, 1e-8]:
            H, skew = hessian(fg, y, step)
            eigen, vectors = np.linalg.eigh(H)
            v = vectors[:, 0]
            samples = []
            for distance in [1e-4, 1e-3, 1e-2, 1e-1]:
                plus, _ = fg(y+distance*v)
                minus, _ = fg(y-distance*v)
                samples.append(dict(distance=distance, plus_delta=plus-f0, minus_delta=minus-f0,
                    centered_delta=(plus+minus)/2-f0,
                    negative_centered_change=bool((plus+minus)/2-f0 < -1e-10*max(1., abs(f0)))))
            spectra.append(dict(target=target, step=step, value=f0, gradient_inf=float(max(abs(g0))),
                minimum_eigenvalue=float(eigen[0]), maximum_eigenvalue=float(eigen[-1]),
                raw_max_asymmetry=skew, eigenvalues=eigen.tolist(), direction=v.tolist(), samples=samples))
            matrices[target+'_'+str(step)] = H
    np.savez_compressed(c.HERE/'hessians.npz', **matrices)
    c.write(c.HERE/'curvature.json', spectra)
    for row in spectra:
        print(json.dumps({key: row[key] for key in ['target', 'step', 'minimum_eigenvalue', 'maximum_eigenvalue', 'raw_max_asymmetry']}))
    m.close()


if __name__ == '__main__':
    main()
