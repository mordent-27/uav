"""One prescribed pass over single charging choices; not Algorithm 1."""
import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
from time import monotonic

import casadi as ca
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MODEL = HERE.parent / '2026-11-14-restoration/fixed_branch.py'
SOURCE = HERE.parent / '2026-11-14-restoration/geometry.json'
spec = importlib.util.spec_from_file_location('restoration_model', MODEL)
fb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fb)


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def choices(source):
    for k, mode in enumerate(source['modes']):
        if mode >= 0:
            for replacement in [-1] + [j for j in range(len(source['instance']['regions'])) if j != mode]:
                yield k, mode, replacement


def check_structure(source, candidate, segment, replacement):
    assert candidate['phys'] == source['phys']
    assert candidate['instance'] == source['instance']
    assert candidate['task_stamp'] == source['task_stamp']
    assert len(candidate['solution']['r']) == len(source['solution']['r'])
    expected = list(source['modes'])
    expected[segment] = replacement
    assert candidate['modes'] == expected
    tr, inst = candidate['solution'], candidate['instance']
    assert tr['r'][0] == inst['r0'] and tr['r'][-1] == inst['rf']
    for task, stamp in zip(inst['tasks'], candidate['task_stamp']):
        assert tr['r'][stamp] == task
    assert all(c == (s if mode >= 0 else 0.) for c, s, mode in zip(tr['c'], tr['s'], expected))


def solve(source, k, old, new):
    name = f'segment{k:02d}-' + ('remove' if new < 0 else f'region{new}')
    case = HERE / 'cases' / name
    case.mkdir(parents=True, exist_ok=False)
    result = dict(name=name, segment=k, old_region=old, new_region=new, accepted=False)
    data = copy.deepcopy(source)
    data['modes'][k] = new
    data['solution']['c'][k] = data['solution']['s'][k] if new >= 0 else 0.
    start = monotonic()
    try:
        model = fb.FixedBranch(data, moving=True)
        options = dict(print_time=False, ipopt=dict(print_level=0, sb='yes',
            hessian_approximation='exact', tol=1e-10, dual_inf_tol=1e-8,
            constr_viol_tol=1e-11, compl_inf_tol=1e-9, acceptable_iter=0,
            max_iter=1500, max_wall_time=5., nlp_scaling_method='none',
            bound_relax_factor=0., mu_strategy='adaptive'))
        solver = ca.nlpsol('choice', 'ipopt', dict(x=model.v, f=model.objective, g=model.constraints), options)
        raw = solver(x0=model.x0, lbx=model.lb, ubx=model.ub,
            lbg=np.r_[np.zeros(model.me), np.full(model.mi, -np.inf)], ubg=np.zeros(model.me + model.mi))
        point = np.array(raw['x']).ravel()
        lam = np.array(raw['lam_g']).ravel()
        lam_x = np.array(raw['lam_x']).ravel()
        kkt = model.kkt(point, lam, lam_x)
        result.update(solver_status=solver.stats()['return_status'],
            solver_success=bool(solver.stats()['success']), iterations=solver.stats()['iter_count'], raw_kkt=kkt)
        write(case / 'solver.json', dict(point=point.tolist(), lam=lam.tolist(), lam_x=lam_x.tolist(),
            options=options, **result))
        r, s = model.decode(point)
        before = s.copy()
        for i, mode in enumerate(data['modes']):
            speed = model.p['v_c'] if mode >= 0 else model.p['v_d']
            s[i] = max(s[i], model.p['s_min'], math.dist(r[i], r[i + 1]) / speed)
        correction = float(max(abs(s - before)))
        assert correction < 1e-10, ('roundoff correction too large', correction)
        data['solution'] = dict(r=r.tolist(), s=s.tolist(),
            c=[float(t) if m >= 0 else 0. for t, m in zip(s, data['modes'])])
        tr = data['solution']
        tr['e'] = fb.diag.replay(data)
        final_point = np.r_[r[model.free].ravel(), np.array(tr['e'][1:]) * model.range, s * model.p['v_d']]
        final_kkt = model.kkt(final_point, lam, lam_x)
        residual = fb.diag.residuals(data)
        result.update(objective=float(sum(s)), min_energy=min(tr['e']), max_energy=max(tr['e']),
            original_residuals=residual, final_kkt=final_kkt, roundoff_time_correction=correction)
        assert result['solver_success'], result['solver_status']
        assert all(v <= 1e-6 for v in kkt.values()), kkt
        assert all(v <= 1e-6 for v in final_kkt.values()), final_kkt
        assert residual['viol'] < 1e-10, residual
        assert min(tr['e']) >= model.p['e_min'] and max(tr['e']) <= model.p['e_max']
        check_structure(source, data, k, new)
        fb.build_history(data)
        dense_e = data.pop('history')['e']
        assert min(dense_e) >= model.p['e_min'] and max(dense_e) <= model.p['e_max']
        data['stages'] = []
        data['metrics'] = dict(objective=float(sum(s)), init_objective=sum(data['init']['s']),
            converged=False, seconds=monotonic() - start, stamps=model.n, **residual)
        data['diagnostic'] = dict(method='single charging choice followed by exact fixed-branch NLP',
            paper_algorithm=False, global_optimality=False, branch_kkt=final_kkt,
            branch_kkt_pass=True, energy_buffer=fb.ENERGY_BUFFER, source=str(SOURCE.relative_to(ROOT)),
            source_objective=source['metrics']['objective'], segment=k, old_region=old, new_region=new)
        data.pop('restoration', None)
        write(case / 'solution.json', data)
        result['accepted'] = True
        result['improvement_seconds'] = float((source['metrics']['objective'] - sum(s)) * 3600)
        result['dense_energy_bounds'] = [min(dense_e), max(dense_e)]
    except (AssertionError, RuntimeError, ValueError) as error:
        result['reason'] = str(error)
    result['seconds'] = monotonic() - start
    write(case / 'result.json', result)
    print(json.dumps(result, allow_nan=False), flush=True)
    return result


def summarize(source, results, elapsed):
    good = [r for r in results if r['accepted']]
    best = min(good, key=lambda r: r['objective']) if good else None
    summary = dict(source_objective=source['metrics']['objective'], cases=results, candidates=len(results),
        accepted=len(good), improved=int(sum(r['improvement_seconds'] > 1e-3 for r in good)),
        best=best, wall_seconds=elapsed, paper_algorithm=False)
    write(HERE / 'summary.json', summary)
    if best:
        data = json.loads((HERE / 'cases' / best['name'] / 'solution.json').read_text())
        fb.build_history(data)
        write(HERE / 'best.json', data)
        certificate = fb.carrier.certify(data)
        if certificate['feasible']:
            certificate['independent_check'] = fb.carrier.check_constructed(data, certificate)
        write(HERE / 'best-carrier.json', certificate)
    paths = [SOURCE, MODEL, Path(__file__), HERE / 'PLAN.md']
    paths += sorted((ROOT / 'src').glob('*.rs'))
    write(HERE / 'provenance.json', dict(casadi=ca.__version__, numpy=np.__version__,
        files={str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}))
    print(json.dumps({k: v for k, v in summary.items() if k != 'cases'}), flush=True)


def main():
    source = json.loads(SOURCE.read_text())
    candidates = list(choices(source))
    assert len(candidates) == 48 and len(set(candidates)) == 48
    assert len(source['solution']['r']) == 37 and len(source['instance']['tasks']) == 7
    if sys.argv[1:] == ['--summarize']:
        # Rebuild tables from immutable case outputs; never rerun a solve.
        results = []
        for k, old, new in candidates:
            name = f'segment{k:02d}-' + ('remove' if new < 0 else f'region{new}')
            results.append(json.loads((HERE / 'cases' / name / 'result.json').read_text()))
        summarize(source, results, None)
    else:
        assert not sys.argv[1:]
        assert not (HERE / 'cases').exists(), 'refuse to overwrite an experiment'
        start = monotonic()
        results = [solve(source, *choice) for choice in candidates]
        summarize(source, results, monotonic() - start)


if __name__ == '__main__':
    main()
