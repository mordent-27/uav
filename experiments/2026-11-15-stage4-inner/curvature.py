"""Step-size-sensitive curvature and scalar-change diagnostics, without solves."""
import json
import numpy as np
import support as s


def hessian(frozen, step):
    y = frozen.anchor
    raw = np.empty((len(y), len(y)))
    for j in range(len(y)):
        a, b = y.copy(), y.copy()
        a[j] += step
        b[j] -= step
        raw[:, j] = (frozen.eval(a)[1]-frozen.eval(b)[1])/(2*step)
    return (raw+raw.T)/2, float(np.max(abs(raw-raw.T)))


def main():
    assert not (s.HERE/'curvature.json').exists()
    states = json.loads((s.HERE/'inputs.json').read_text())
    spectra, matrices, direction_checks = [], {}, []
    for name, state in states.items():
        frozen = s.Frozen(state)
        value, gradient = frozen.eval(frozen.anchor)
        chosen = None
        for step in [1e-6, 1e-7, 1e-8]:
            H, skew = hessian(frozen, step)
            eigen = np.linalg.eigvalsh(H)
            matrices[name+'_'+str(step)] = H
            row = dict(problem=name, step=step, gradient_inf=float(max(abs(gradient))),
                min_eigenvalue=float(eigen[0]), max_eigenvalue=float(eigen[-1]),
                max_asymmetry=skew, eigenvalues=eigen.tolist(),
                condition_estimate=float(eigen[-1]/eigen[0]) if eigen[0] > 0 else None)
            spectra.append(row)
            print(json.dumps({k: row[k] for k in ['problem', 'step', 'min_eigenvalue', 'max_eigenvalue', 'max_asymmetry']}), flush=True)
            if step == 1e-7:
                chosen = H
        if name == 'stalled':
            eigen, vectors = np.linalg.eigh(chosen)
            regularized = eigen[0] <= 0
            p = -vectors@((vectors.T@gradient)/np.maximum(eigen, 1e-8))
            directions = [('negative-gradient', -gradient/np.linalg.norm(gradient), [1e-4, 1e-6, 1e-8, 1e-10, 1e-12]),
                ('newton' if not regularized else 'regularized-newton', p/np.linalg.norm(p),
                 [float(np.linalg.norm(p))*a for a in [1., .1, .01, .001, 1e-4, 1e-6, 1e-8]])]
            nodes, weights = np.polynomial.legendre.leggauss(16)
            for direction_name, direction, distances in directions:
                samples = []
                for distance in distances:
                    point = frozen.anchor+distance*direction
                    ordinary, _ = frozen.eval(point)
                    stable, _ = frozen.eval(point, stable=True)
                    derivatives = [frozen.eval(frozen.anchor+distance*(node+1)/2*direction)[1]@direction for node in nodes]
                    integrated = float(distance/2*np.dot(weights, derivatives))
                    first = float(distance*(gradient@direction))
                    second = first+float(distance**2*(direction@chosen@direction)/2)
                    samples.append(dict(distance=distance, ordinary_change=ordinary-value,
                        stable_change=stable, gradient_line_integral=integrated,
                        first_prediction=first, second_prediction=second))
                direction_checks.append(dict(direction=direction_name, vector=direction.tolist(),
                    newton_step_norm=float(np.linalg.norm(p)), samples=samples))
        frozen.close()
    s.write(s.HERE/'curvature.json', spectra)
    s.write(s.HERE/'direction-checks.json', direction_checks)
    np.savez_compressed(s.HERE/'hessians.npz', **matrices)


if __name__ == '__main__':
    main()
