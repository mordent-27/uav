"""Print the trajectory, constraint residuals and multipliers of a saved state (npz)."""
import sys
import numpy as np
import newton_al as na

np.set_printoptions(linewidth=220, precision=4)
state, lib, tau, seed, stage = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5])
if state.endswith('.json'):  # summary written by newton_al.py
    import json
    doc = json.load(open(state))
    z = {k: np.array(doc[k]) for k in ('y', 'lam', 'mu')} | {'rho': doc['rho']}
else:
    z = np.load(state)
m = na.Model(tau, seed, lib)
m.stage(max(.0005, .2 * .6**stage), min(12., 2. * 1.2**stage))
y, lam, mu = z['y'], z['lam'], z['mu']
print('kkt', na.kkt(m, y, lam, mu), 'rho', float(z['rho']))
ns, nr = m.stamps - 1, 2 * (m.stamps - 2)
x = y * m.scale
sol = m.solution(y)
inst = sol['instance']
r = np.vstack([inst['r0'], x[:nr].reshape(-1, 2), inst['rf']])
e = np.r_[1.0, x[nr:nr + ns]]
s, c = x[nr + ns:nr + 2 * ns], x[nr + 2 * ns:]
tau_n = m.me - 2 * ns
g = m.g.reshape(6, ns)
J = np.linalg.norm(m.jacobian(y), axis=1)
print('tasks', inst['tasks'], 'objective', s.sum(), 'modes', sol.get('modes'))
print(' k      x       y       e      s[s]    c[s]   speed  in-region(a,b)   h_dyn     h_mode   lam_mode  |dh_mode|  g_speed')
for k in range(ns):
    d = np.linalg.norm(r[k + 1] - r[k])
    reg = [''.join(str(j + 1) for j, q in enumerate(inst['regions']) if np.linalg.norm(r[i] - q['o']) <= q['rho'] + 1e-6) or '-'
           for i in (k, k + 1)]
    print(f'{k:>2} {r[k][0]:7.3f} {r[k][1]:7.3f} {e[k]:7.4f} {s[k]*3600:7.1f} {c[k]*3600:7.2f} {d/s[k]:7.2f}   {reg[0]:>3},{reg[1]:<3}'
          f'      {m.h[k]:9.1e} {m.h[ns+tau_n+k]:9.1e} {lam[ns+tau_n+k]:9.1e} {J[ns+tau_n+k]:9.1e} {g[0][k]:9.1e}')
print(f'{ns:>2} {r[-1][0]:7.3f} {r[-1][1]:7.3f} {e[-1]:7.4f}')
print('h_task', m.h[ns:ns + tau_n], 'lam_task', lam[ns:ns + tau_n], '|dh_task|', J[ns:ns + tau_n])
print('max g: speed %.1e elo %.1e ehi %.1e slo %.1e shi %.1e c>=0 %.1e' % tuple(g.max(axis=1)))
