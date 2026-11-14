"""Spectrum of the AL Hessian at the minimiser of the very first subproblem (eps=.2, p=2, rho=10, lam=0)."""
import sys
import numpy as np
from scipy.optimize import minimize
import newton_al as na

np.set_printoptions(linewidth=200, formatter={'float': '{:.2e}'.format})
lib, tau, seed = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
m = na.Model(tau, seed, lib)
m.stage(.2, 2.)
lam, mu, rho = np.zeros(m.me), np.zeros(m.mi), 10.
fg = lambda q: m.eval(q, lam, mu, rho)
r = minimize(fg, m.y.copy(), jac=True, method='BFGS', options=dict(gtol=1e-9, maxiter=20000))
print(f'n {m.n}; dense BFGS: {r.nit} iterations, {r.nfev} evaluations, |grad| {np.abs(r.jac).max():.1e}')
y = r.x
w, V = np.linalg.eigh(na.fd_hessian(lambda q: fg(q)[1], y))
print('eigenvalues', w)
print(f'condition number {w[-1]/w[0]:.1e}')
ns = m.stamps - 1
names = [f'r{k//2+1}{"xy"[k%2]}' for k in range(2 * (m.stamps - 2))] + [f'e{k+1}' for k in range(ns)] \
    + [f's{k}' for k in range(ns)] + [f'c{k}' for k in range(ns)]
for i in (0, 1, 2, -2, -1):
    idx = np.argsort(-np.abs(V[:, i]))[:5]
    print(f'{w[i]:10.2e}', ' '.join(f'{names[j]}:{V[j, i]:+.2f}' for j in idx))
J = m.jacobian(y)
x = y * m.scale
c = x[-ns:]
print('charging durations c [s]', c * 3600)
print('mode-equality gradient norms (scaled variables)', np.linalg.norm(J[m.me - ns:m.me], axis=1))
print('predicted rho*|dh_mode|^2', rho * np.linalg.norm(J[m.me - ns:m.me], axis=1)**2)
print('speed-inequality gradient norms', np.linalg.norm(J[m.me:m.me + ns], axis=1))
