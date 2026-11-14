"""Eigenvalues of the AL Hessian at a saved state, with the variables that carry the extreme ones."""
import sys
import numpy as np
import newton_al as na

np.set_printoptions(linewidth=220, precision=2)
state, lib, tau, seed, stage = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5])
z = np.load(state)
m = na.Model(tau, seed, lib)
m.stage(max(.0005, .2 * .6**stage), min(12., 2. * 1.2**stage))
y, lam, mu, rho = z['y'], z['lam'], z['mu'], float(sys.argv[6]) if len(sys.argv) > 6 else float(z['rho'])
ns = m.stamps - 1
names = [f'r{k//2+1}{"xy"[k%2]}' for k in range(2 * (m.stamps - 2))] + [f'e{k+1}' for k in range(ns)] \
    + [f's{k}' for k in range(ns)] + [f'c{k}' for k in range(ns)]
H = na.fd_hessian(lambda q: m.eval(q, lam, mu, rho)[1], y)
w, V = np.linalg.eigh(H)
print(f'rho {rho:.0e}: n {m.n}, eigenvalues min {w[0]:.2e} max {w[-1]:.2e} cond {w[-1]/abs(w[0]):.1e}')
print('all', w)
for i in list(range(4)) + [-3, -2, -1]:
    v = V[:, i]
    idx = np.argsort(-np.abs(v))[:5]
    print(f'{w[i]:10.2e}', ' '.join(f'{names[j]}:{v[j]:+.2f}' for j in idx))
