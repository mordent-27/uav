"""Fixed assignment (modes, task stamps) NLP, with or without one carrier per disk as position variables.

Not the paper's algorithm: a local Ipopt solve of the exact original constraints on a frozen branch.
    python solve.py            # the six targets fixed in PLAN.md (never overwrites)
"""
import copy
import json
import math
from pathlib import Path
import sys
from time import monotonic

import casadi as ca
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
sys.path.insert(0, str(ROOT/'experiments/2026-11-14-restoration'))
import diagnose_solution as diag
import carrier_certificate as carrier
from fixed_branch import charge_expr, ENERGY_BUFFER  # same battery expression as the restoration NLP

TARGETS = ['tau4-seed4000012', 'tau6-seed6000032', 'tau9-seed9000076',
           'tau9-seed9000001', 'tau8-seed8000015', 'tau7-seed7000053']
TOL = 1e-9  # km
OPTIONS = {'print_time': False, 'ipopt': {'print_level': 0, 'sb': 'yes', 'hessian_approximation': 'exact',
    'tol': 1e-10, 'dual_inf_tol': 1e-8, 'constr_viol_tol': 1e-11, 'compl_inf_tol': 1e-9,
    'acceptable_iter': 0, 'max_iter': 1500, 'max_wall_time': 300., 'nlp_scaling_method': 'none',
    'bound_relax_factor': 0., 'mu_strategy': 'adaptive'}}


def dist_le(a, b, bound):
    """Smooth form of |a-b| <= bound (same as fixed_branch.py)."""
    d2 = ca.sumsqr(a-b)
    return (d2-bound**2)/(ca.sqrt(d2+1e-6)+ca.sqrt(bound**2+1e-6))


def initial_carriers(d, regions_used):
    """Time-linear interpolation between contact anchors (positions in the disk by convexity)."""
    r, s, modes = d['solution']['r'], d['solution']['s'], d['modes']
    t = np.r_[0., np.cumsum(s)]
    out = {}
    for j in regions_used:
        anchors = {}
        for k, m in enumerate(modes):
            if m == j:
                anchors[k], anchors[k+1] = r[k], r[k+1]
        ks = sorted(anchors)
        out[j] = np.array([np.interp(t[k], t[ks], [anchors[a][i] for a in ks]) for k in range(len(r))
                           for i in (0, 1)]).reshape(-1, 2)
    return out


class Branch:
    def __init__(self, d, with_carrier):
        self.data = copy.deepcopy(d); self.p = p = d['phys']; self.with_carrier = with_carrier
        self.n = n = len(d['solution']['r']); self.ns = ns = n-1
        self.modes = modes = list(d['modes']); regions = d['instance']['regions']
        r = np.array(d['solution']['r'], float)
        anchors = {0: d['instance']['r0'], n-1: d['instance']['rf']}
        for point, k in zip(d['instance']['tasks'], d['task_stamp']):
            assert k not in anchors or np.linalg.norm(np.array(anchors[k])-point) < 1e-14
            anchors[k] = point
        for k, point in anchors.items():
            r[k] = point
        self.base_positions = r
        self.free = [k for k in range(n) if k not in anchors]
        self.used = sorted({m for m in modes if m >= 0}) if with_carrier else []
        self.contacts = {j: sorted({k0 for k, m in enumerate(modes) if m == j for k0 in (k, k+1)}) for j in self.used}
        self.qfree = [(j, k) for j in self.used for k in range(n) if k not in self.contacts[j]]
        self.nr, self.nq = 2*len(self.free), 2*len(self.qfree)
        self.range = p['v_d']/p['zeta']
        self.v = v = ca.SX.sym('y', self.nr+2*ns+self.nq)
        pos = [ca.DM(x) for x in r]
        for i, k in enumerate(self.free):
            pos[k] = v[2*i:2*i+2]
        q = {j: list(pos) for j in self.used}  # contact stamps: carrier = UAV (substituted)
        off = self.nr+2*ns
        for i, (j, k) in enumerate(self.qfree):
            q[j][k] = v[off+2*i:off+2*i+2]
        self.pos, self.q = pos, q
        energy = [ca.SX(p['e_max'])]+[v[self.nr+k]/self.range for k in range(ns)]
        dur = [v[self.nr+ns+k]/p['v_d'] for k in range(ns)]
        lower = []
        for k, m in enumerate(modes):
            speed = p['v_c'] if m >= 0 else p['v_d']
            lower.append(max(p['s_min'], math.dist(r[k], r[k+1])/speed+1e-12))
        self.lb = np.r_[np.full(self.nr, -np.inf), np.full(ns, (p['e_min']+ENERGY_BUFFER)*self.range),
                        np.full(ns, p['s_min']*p['v_d']), np.full(self.nq, -np.inf)]
        self.ub = np.r_[np.full(self.nr, np.inf), np.full(ns, p['e_max']*self.range),
                        np.full(ns, p['s_max']*p['v_d']), np.full(self.nq, np.inf)]
        eq, ineq = [], []
        for k, m in enumerate(modes):
            before, after = energy[k:k+2]; s = dur[k]
            eq.append(self.range*(after-(charge_expr(p, before, s) if m >= 0 else before-p['zeta']*s)))
            ineq.append(dist_le(pos[k+1], pos[k], (p['v_c'] if m >= 0 else p['v_d'])*s))
        for j, k in sorted({(m, k0) for k, m in enumerate(modes) if m >= 0 for k0 in (k, k+1)}):
            reg = regions[j]
            if k in self.free:
                ineq.append((ca.sumsqr(pos[k]-ca.DM(reg['o']))-reg['rho']**2)/(2*reg['rho']))
            else:
                assert math.dist(r[k], reg['o']) <= reg['rho']+1e-10, (j, k)
        for j in self.used:
            reg = regions[j]
            for k in range(ns):
                if modes[k] != j:  # inside a mode-j segment the carrier is the UAV (constraint above)
                    ineq.append(dist_le(q[j][k+1], q[j][k], p['v_c']*dur[k]))
            for k in range(n):
                if k not in self.contacts[j]:
                    ineq.append((ca.sumsqr(q[j][k]-ca.DM(reg['o']))-reg['rho']**2)/(2*reg['rho']))
        self.me, self.mi = len(eq), len(ineq)
        self.constraints = ca.vertcat(*eq, *ineq); self.objective = sum(dur)
        self.evaluate = ca.Function('values', [v], [self.objective, self.constraints,
                                    ca.gradient(self.objective, v), ca.jacobian(self.constraints, v)])
        tr = d['solution']
        e0 = np.clip(np.array(tr['e'][1:]), p['e_min']+ENERGY_BUFFER, p['e_max'])
        s0 = np.maximum(np.array(tr['s']), np.array(lower))
        q0 = initial_carriers(d, self.used)
        self.x0 = np.r_[r[self.free].ravel(), e0*self.range, s0*p['v_d'],
                        np.array([q0[j][k] for j, k in self.qfree]).ravel() if self.qfree else []]

    def kkt(self, x, lam, lam_x):
        f, con, grad, jac = self.evaluate(x)
        con = np.array(con).ravel(); grad = np.array(grad).ravel()+np.array(jac).T@lam+lam_x
        h, g = con[:self.me], con[self.me:]
        lo, up = np.isfinite(self.lb), np.isfinite(self.ub)
        lmu, umu = np.maximum(-lam_x, 0.), np.maximum(lam_x, 0.)
        comp = [0.]+np.abs(np.minimum(lam[self.me:], -g)).tolist()
        comp += np.abs(np.minimum(lmu[lo], x[lo]-self.lb[lo])).tolist()
        comp += np.abs(np.minimum(umu[up], self.ub[up]-x[up])).tolist()
        return dict(stat=float(max(abs(grad))),
                    feas=float(max([0.]+abs(h).tolist()+g.tolist()+(self.lb-x).tolist()+(x-self.ub).tolist())),
                    comp=float(max(comp)),
                    dual=float(max([0.]+(-lam[self.me:]).tolist()+lmu[~lo].tolist()+umu[~up].tolist())))

    def solve(self):
        solver = ca.nlpsol('branch', 'ipopt', dict(x=self.v, f=self.objective, g=self.constraints), OPTIONS)
        start = monotonic()
        sol = solver(x0=self.x0, lbx=self.lb, ubx=self.ub,
                     lbg=np.r_[np.zeros(self.me), np.full(self.mi, -np.inf)], ubg=np.zeros(self.me+self.mi))
        seconds = monotonic()-start
        x = np.array(sol['x']).ravel(); lam = np.array(sol['lam_g']).ravel(); lam_x = np.array(sol['lam_x']).ravel()
        stats = solver.stats()
        p = self.p; n = self.n
        r = self.base_positions.copy()
        for i, k in enumerate(self.free):
            r[k] = x[2*i:2*i+2]
        s = x[self.nr+self.ns:self.nr+2*self.ns]/p['v_d']
        q = {j: np.array([r[k] for k in range(n)]) for j in self.used}
        off = self.nr+2*self.ns
        for i, (j, k) in enumerate(self.qfree):
            q[j][k] = x[off+2*i:off+2*i+2]
        before = s.copy()
        for k, m in enumerate(self.modes):  # roundoff in time bounds only
            need = [p['s_min'], math.dist(r[k], r[k+1])/(p['v_c'] if m >= 0 else p['v_d'])]
            need += [math.dist(q[j][k], q[j][k+1])/p['v_c'] for j in self.used]
            s[k] = max(s[k], *need)
        assert max(s) <= p['s_max']+1e-11
        d = copy.deepcopy(self.data)
        tr = d['solution'] = dict(r=r.tolist(), s=s.tolist(), c=[float(t) if m >= 0 else 0. for t, m in zip(s, self.modes)])
        tr['e'] = diag.replay(d)
        check = diag.residuals(d)
        assert check['viol'] < 1e-10, check
        assert min(tr['e']) >= p['e_min'] and max(tr['e']) <= p['e_max']
        own = dict(speed_excess_km=0., region_excess_km=0., contact_error_km=0.)
        regions = d['instance']['regions']
        for j in self.used:
            for k in range(n-1):
                own['speed_excess_km'] = max(own['speed_excess_km'], math.dist(q[j][k], q[j][k+1])-p['v_c']*s[k])
            for k in range(n):
                own['region_excess_km'] = max(own['region_excess_km'], math.dist(q[j][k], regions[j]['o'])-regions[j]['rho'])
            for k in self.contacts[j]:
                own['contact_error_km'] = max(own['contact_error_km'], math.dist(q[j][k], r[k]))
        cert = carrier.certify(d)
        unreachable = [f['excess_km'] for c in cert['carriers'] for f in c['failures'] if f['kind'] == 'unreachable']
        region_fail = [f['excess_km'] for c in cert['carriers'] for f in c['failures'] if f['kind'] == 'outside_region']
        d['metrics'] = dict(objective=float(sum(s)), init_objective=float(sum(d['init']['s'])), converged=False,
                            seconds=seconds, stamps=n, **check)
        d['diagnostic'] = dict(method='exact fixed modes/task stamps NLP'+(' with carrier position variables' if self.with_carrier else ''),
                               paper_algorithm=False, global_optimality=False, energy_buffer=ENERGY_BUFFER,
                               max_roundoff_time_correction_hours=float(max(abs(s-before))))
        d['stages'] = []
        result = dict(with_carrier=self.with_carrier, objective_hours=float(sum(s)), solver_status=stats['return_status'],
                      solver_success=bool(stats['success']), iterations=stats['iter_count'], seconds=seconds,
                      variables=int(self.v.numel()), equalities=self.me, inequalities=self.mi,
                      kkt=self.kkt(x, lam, lam_x), original=check, min_energy=min(tr['e']),
                      carrier_own=own if self.with_carrier else None,
                      certify_unreachable_max_km=max(unreachable, default=0.), certify_pairs_failing=len(unreachable),
                      certify_region_excess_max_km=max(region_fail, default=0.),
                      max_roundoff_time_correction_hours=float(max(abs(s-before))))
        if self.with_carrier:
            d['carrier_positions'] = {str(j): q[j].tolist() for j in self.used}
        return d, result, dict(x=x.tolist(), lam=lam.tolist(), lam_x=lam_x.tolist(), options=OPTIONS)


def main():
    index = {p['case']: p for p in json.loads((ROOT/'experiments/2026-11-18-r3s-carrier/source-index.json').read_text())['points']}
    import hashlib
    rows = []
    for case in TARGETS:
        out = HERE/'runs'/case
        assert not out.exists(), f'do not overwrite {out}'
        out.mkdir(parents=True)
        src = ROOT/index[case]['path']
        assert hashlib.sha256(src.read_bytes()).hexdigest() == index[case]['sha256']
        d = json.loads(src.read_text())
        row = dict(case=case, returned_hours=d['metrics']['objective'] if 'objective' in d['metrics'] else sum(d['solution']['s']),
                   returned_sum_s_hours=float(sum(d['solution']['s'])))
        for name, flag in (('base', False), ('carrier', True)):
            sol, res, raw = Branch(d, flag).solve()
            (out/f'{name}.json').write_text(json.dumps(sol, indent=1, allow_nan=False)+'\n')
            (out/f'{name}-solver.json').write_text(json.dumps(raw, allow_nan=False)+'\n')
            row[name] = res
            print(case, name, json.dumps(dict(T=res['objective_hours'], status=res['solver_status'], it=res['iterations'],
                  kkt=res['kkt'], late=res['certify_unreachable_max_km'], own=res['carrier_own'])), flush=True)
        rows.append(row)
    (HERE/'results.json').write_text(json.dumps(rows, indent=1, allow_nan=False)+'\n')


if __name__ == '__main__':
    main()
