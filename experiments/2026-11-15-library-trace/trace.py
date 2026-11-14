"""Paired inner-solver comparisons and full-precision homotopy traces for Figure 1."""
import ctypes as ct
import gzip
import json
from pathlib import Path
import sys
from time import monotonic

import numpy as np
import scipy
from scipy.optimize import minimize

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE.parent / '2026-11-14-reproduction'))
sys.path.insert(0, str(ROOT / 'scripts'))
from independent_al import Model
import diagnose_solution as diag

LIBRARIES = {'normalized': '/tmp/uav-library-trace-speed.so', 'original': '/tmp/uav-library-trace-original.so'}
BACKENDS = ['rust', 'scipy-lbfgs', 'scipy-bfgs']


def write(path, data):
    path.write_text(json.dumps(data, indent=2, allow_nan=False) + '\n')


def decode(model, y, template):
    n, ns = model.stamps, model.stamps - 1
    nr = 2 * (n - 2)
    x = y * model.scale
    return dict(r=[template['instance']['r0']] + x[:nr].reshape(-1, 2).tolist() + [template['instance']['rf']],
        e=[template['phys']['e_max']] + x[nr:nr+ns].tolist(),
        s=x[nr+ns:nr+2*ns].tolist(), c=x[nr+2*ns:].tolist())


def softmin(z, p):
    z = np.asarray(z)
    low = float(min(z))
    phi = low * float(sum((low / z)**p))**(-1 / p)
    derivative = (phi / z)**(p + 1)
    return dict(z=z.tolist(), phi=phi, dphi_dz=derivative.tolist(),
        derivative_share=(derivative / sum(derivative)).tolist(), winner=int(np.argmin(z)) - 1)


def psi(y, delta=.001):
    y = np.asarray(y)
    return np.where(y <= -delta, 0., np.where(y <= delta, (y + delta)**2 / (4 * delta), y))


def describe(model, y, template, eps, p):
    tr = decode(model, y, template)
    r, s, c = np.array(tr['r']), np.array(tr['s']), np.array(tr['c'])
    regions, phys = template['instance']['regions'], template['phys']
    modes = []
    for k in range(len(s)):
        z = [np.hypot(c[k], eps)]
        distance = np.linalg.norm(r[k+1] - r[k])
        for region in regions:
            violation = psi([np.linalg.norm(r[k] - region['o']) - region['rho'],
                             np.linalg.norm(r[k+1] - region['o']) - region['rho'],
                             distance - phys['v_c'] * s[k]])
            z.append(np.sqrt((c[k] - s[k])**2 + violation @ violation + eps**2))
        modes.append(dict(segment=k, s=s[k], c=c[k], c_over_s=float(c[k]/s[k]) if s[k] != 0 else None,
                          **softmin(z, p)))
    tasks = []
    for i, task in enumerate(template['instance']['tasks']):
        z = np.sqrt(np.sum((r - task)**2, axis=1) + eps**2)
        item = softmin(z, p)
        item['stamp'] = item.pop('winner') + 1
        tasks.append(dict(task=i, **item))
    data = dict(instance=template['instance'], phys=phys, solution=tr,
                modes=[item['winner'] for item in modes])
    audit = dict(original_residuals=diag.residuals(data))
    try:
        energy = diag.replay(data)
        audit.update(pure_mode_min_energy=min(energy), pure_mode_final_energy=energy[-1])
    except ValueError as error:
        audit['pure_mode_replay_error'] = str(error)
    return dict(modes=modes, tasks=tasks, charging_segments=sum(item['winner'] >= 0 for item in modes), audit=audit)


def kkt(model, y, lam, mu):
    model.eval(y, lam, mu, 0.)
    return dict(stat=float(max(abs(model.grad))), feas=float(max(max(abs(model.h)), max(model.g), 0.)),
                comp=float(max(abs(np.minimum(mu, -model.g)))), dual=float(max(0., -min(mu))))


def original_multipliers(model, y, template, mu):
    tr = decode(model, y, template)
    delta = np.diff(np.array(tr['r']), axis=0)
    denominator = np.sqrt(np.sum(delta**2, axis=1) + .001**2) + np.sqrt((36*np.array(tr['s']))**2 + .001**2)
    mapped = mu.copy()
    mapped[:model.stamps - 1] /= denominator
    return mapped


def inner(model, y, lam, mu, rho, backend, deadline):
    y = np.ascontiguousarray(y.copy())
    start = monotonic()
    initial_value, initial_gradient = model.eval(y, lam, mu, rho)
    interrupted = False
    last = y.copy()
    count = 0
    def fg(point):
        nonlocal count
        if monotonic() > deadline:
            raise TimeoutError()
        count += 1
        return model.eval(np.ascontiguousarray(point), lam, mu, rho)
    def callback(point):
        nonlocal last
        last = point.copy()
    if backend == 'rust':
        result = np.empty(5)
        model.lib.uav_rust_inner(model.ctx, model.ptr(y), model.ptr(lam), model.ptr(mu), rho, 2000, model.ptr(result))
        status = ['gradient', 'max_iter', 'stalled', 'line_search'][int(result[4])]
        iterations, evaluations = int(result[2]), int(result[3])
        success = int(result[4]) == 0
    else:
        options = dict(gtol=1e-6, maxiter=2000)
        if backend == 'scipy-lbfgs':
            options.update(ftol=1e-14, maxcor=20, maxls=65, maxfun=100000)
        try:
            result = minimize(fg, y, jac=True, callback=callback,
                              method='L-BFGS-B' if backend == 'scipy-lbfgs' else 'BFGS', options=options)
            y = np.ascontiguousarray(result.x)
            status, iterations, evaluations, success = str(result.message), int(result.nit), int(result.nfev), bool(result.success)
        except TimeoutError:
            y, status, iterations, evaluations, success = last, 'timeout; last accepted inner iterate', None, count, False
            interrupted = True
    value, gradient = model.eval(y, lam, mu, rho)
    return dict(y=y, value=value, gradient_inf=float(max(abs(gradient))), initial_value=initial_value,
        initial_gradient_inf=float(max(abs(initial_gradient))), status=status, iterations=iterations,
        evaluations=evaluations, solver_success=success, gradient_pass=bool(max(abs(gradient)) <= 1e-6),
        seconds=monotonic() - start, interrupted=interrupted)


def state(y, lam, mu, rho, eps, p, stage):
    return dict(y=y.tolist(), lam=lam.tolist(), mu=mu.tolist(), rho=rho, eps=eps, p=p, stage=stage)


def trace(backend):
    folder = HERE / 'runs' / backend
    folder.mkdir(parents=True, exist_ok=False)
    model = Model(0, 0, LIBRARIES['normalized'])
    original = Model(0, 0, LIBRARIES['original'])
    template = model.solution(model.y)
    y = model.y.copy()
    lam, mu, rho = np.zeros(model.me), np.zeros(model.mi), 1e4
    initial = state(y, lam, mu, rho, .2, 2., 1)
    write(folder / 'initial.json', initial)
    start = monotonic()
    stop, stages, last_stage = 'outer_limit', [], 0
    outer_total = 0
    with gzip.open(folder / 'outer.jsonl.gz', 'wt') as log:
        for st in range(13):
            eps, p = max(.0005, .2*.6**st), min(12., 2.*1.2**st)
            model.stage(eps, p)
            original.stage(eps, p)
            last_stage = st + 1
            entry = state(y, lam, mu, rho, eps, p, st+1)
            entry['selection'] = describe(model, y, template, eps, p)
            write(folder / f'stage{st+1:02d}-start.json', entry)
            for outer in range(30 if st == 12 else 10):
                if monotonic() - start >= 120:
                    stop = 'timeout'
                    break
                result = inner(model, y, lam, mu, rho, backend, start + 120)
                point = result.pop('y')
                if result['interrupted']:
                    write(folder / 'interrupted-inner.json', dict(y=point.tolist(), **result))
                    stop = 'timeout'
                    break
                y = point
                model.eval(y, lam, mu, 0.)
                lam += rho * model.h
                mu = np.maximum(0., mu + rho * model.g)
                normalized = kkt(model, y, lam, mu)
                canonical = kkt(original, y, lam, original_multipliers(model, y, template, mu))
                outer_total += 1
                row = dict(**state(y, lam, mu, rho, eps, p, st+1), outer=outer+1,
                    normalized_kkt=normalized, original_kkt=canonical, inner=result,
                    objective=float(model.objective[0]), selection=describe(model, y, template, eps, p),
                    elapsed=monotonic() - start)
                log.write(json.dumps(row, allow_nan=False) + '\n')
                log.flush()
                if max(normalized.values()) <= 1e-6:
                    break
            final = state(y, lam, mu, rho, eps, p, st+1)
            final.update(normalized_kkt=kkt(model, y, lam, mu),
                original_kkt=kkt(original, y, lam, original_multipliers(model, y, template, mu)),
                objective=float(model.objective[0]), selection=describe(model, y, template, eps, p))
            write(folder / f'stage{st+1:02d}-end.json', final)
            stages.append(dict(stage=st+1, objective=final['objective'], original_kkt=final['original_kkt'],
                charging_segments=final['selection']['charging_segments'],
                segment29=final['selection']['modes'][29], task_stamps=[r['stamp'] for r in final['selection']['tasks']]))
            print(json.dumps(dict(backend=backend, stage=st+1, objective=final['objective'],
                original_kkt=final['original_kkt'], segment29_winner=final['selection']['modes'][29]['winner'],
                elapsed=monotonic()-start)), flush=True)
            if stop == 'timeout':
                break
    final['backend'] = backend
    final.update(stop=stop, outer_total=outer_total, seconds=monotonic()-start, stages=stages,
        kkt_converged=bool(stop != 'timeout' and last_stage == 13 and max(final['original_kkt'].values()) <= 1e-6))
    write(folder / 'result.json', final)
    doc = model.solution(y)
    doc['experiment'] = dict(backend=backend, paper_matlab=False, y_full_precision=y.tolist(),
        lam=lam.tolist(), mu=mu.tolist(), stop=stop, final_stage=last_stage,
        final_original_kkt=final['original_kkt'], selection=final['selection'])
    doc['metrics']['converged'] = final['kkt_converged']
    doc['metrics']['seconds'] = final['seconds']
    write(folder / 'solution.json', doc)
    model.close()
    original.close()


def probes():
    results = []
    for stage in [1, 7, 13]:
        source = HERE / 'runs/rust' / f'stage{stage:02d}-start.json'
        if not source.exists():
            results.append(dict(stage=stage, missing=True))
            continue
        entry = json.loads(source.read_text())
        for representation in ['normalized', 'original']:
            model = Model(0, 0, LIBRARIES[representation])
            template = model.solution(model.y)
            model.stage(entry['eps'], entry['p'])
            y, lam, mu = (np.array(entry[key]) for key in ['y', 'lam', 'mu'])
            if representation == 'original':
                mu = original_multipliers(model, y, template, mu)
            initial = dict(**state(y, lam, mu, entry['rho'], entry['eps'], entry['p'], stage), representation=representation)
            folder = HERE / 'probes' / f'{representation}-stage{stage:02d}'
            folder.mkdir(parents=True, exist_ok=False)
            write(folder / 'input.json', initial)
            for backend in BACKENDS:
                result = inner(model, y, lam, mu, entry['rho'], backend, monotonic()+15)
                result['y'] = result['y'].tolist()
                result.update(stage=stage, representation=representation, backend=backend)
                write(folder / f'{backend}.json', result)
                results.append({key: value for key, value in result.items() if key != 'y'})
                print(json.dumps({key: value for key, value in result.items() if key != 'y'}), flush=True)
            model.close()
    write(HERE / 'probe-summary.json', results)


if __name__ == '__main__':
    if sys.argv[1:] == ['--probes']:
        probes()
    else:
        assert not sys.argv[1:]
        for backend in BACKENDS:
            trace(backend)
        probes()
        write(HERE / 'versions.json', dict(numpy=np.__version__, scipy=scipy.__version__, libraries=LIBRARIES))
