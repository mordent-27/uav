"""Separate curvature of the constraints from the PHR active-set contribution."""
import json
import importlib.util
import numpy as np
import support as s

spec = importlib.util.spec_from_file_location('stage4_curvature', s.HERE/'curvature.py')
curvature = importlib.util.module_from_spec(spec)
spec.loader.exec_module(curvature)
direct_hessian = curvature.hessian


def hessian_of_al(frozen, y, step=1e-7, counters=None):
    m = frozen.m
    m.eval(y, frozen.lam, frozen.mu, frozen.rho)
    h, g = m.h.copy(), m.g.copy()
    le = frozen.lam+frozen.rho*h
    shifted = frozen.mu+frozen.rho*g
    active = shifted > 0
    mi = np.maximum(0., shifted)
    jac = m.jacobian(y)
    raw = np.empty((len(y), len(y)))
    for j in range(len(y)):
        a, b = y.copy(), y.copy()
        a[j] += step
        b[j] -= step
        raw[:, j] = (m.eval(a, le, mi, 0.)[1]-m.eval(b, le, mi, 0.)[1])/(2*step)
    if counters is not None:
        counters['gradient_calls'] += 1+2*len(y)
        counters['jacobian_calls'] += 1
    J = jac[:m.me]
    G = jac[m.me:][active]
    H = (raw+raw.T)/2+frozen.rho*(J.T@J+G.T@G)
    return H, float(np.max(abs(raw-raw.T)))


def main():
    assert not (s.HERE/'decomposition.json').exists()
    summaries, matrices = [], {}
    for name, state in json.loads((s.HERE/'inputs.json').read_text()).items():
        frozen = s.Frozen(state)
        frozen.eval(frozen.anchor)
        shifted = frozen.mu+frozen.rho*frozen.m.g
        jac = frozen.m.jacobian(frozen.anchor)[frozen.m.me:]
        sensitivities = frozen.rho*np.max(abs(jac), axis=1)
        distances = np.divide(abs(shifted), sensitivities, out=np.full(len(shifted), np.inf), where=sensitivities > 0)
        margins = [dict(constraint=int(j), shifted=float(shifted[j]), active=bool(shifted[j] > 0),
            coordinate_distance_estimate=float(distances[j])) for j in np.argsort(distances)[:12]]
        estimates = []
        for step in [1e-9, 1e-10, 1e-11, 1e-12]:
            H, skew = direct_hessian(frozen, step)
            eigen = np.linalg.eigvalsh(H)
            matrices[name+'_direct_'+str(step)] = H
            estimates.append(dict(kind='direct', step=step, min_eigenvalue=float(eigen[0]),
                max_eigenvalue=float(eigen[-1]), max_asymmetry=skew))
        for step in [1e-6, 1e-7, 1e-8]:
            H, skew = hessian_of_al(frozen, frozen.anchor, step)
            eigen = np.linalg.eigvalsh(H)
            matrices[name+'_decomposed_'+str(step)] = H
            estimates.append(dict(kind='decomposed', step=step, min_eigenvalue=float(eigen[0]),
                max_eigenvalue=float(eigen[-1]), max_asymmetry=skew,
                condition_estimate=float(eigen[-1]/eigen[0]) if eigen[0] > 0 else None))
        summary = dict(problem=name, closest_switches=margins,
            exact_switch_rows=[int(j) for j in np.flatnonzero(shifted == 0)], estimates=estimates)
        summaries.append(summary)
        print(json.dumps(summary), flush=True)
        frozen.close()
    np.savez_compressed(s.HERE/'decomposed-hessians.npz', **matrices)
    s.write(s.HERE/'decomposition.json', summaries)


if __name__ == '__main__':
    main()
