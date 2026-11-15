"""Positive control: same good physical seed, final NLP versus full homotopy."""
import copy
import gzip
import importlib.util
import json
from pathlib import Path
import sys
from time import monotonic

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE = HERE.parent / '2026-11-14-resume/fixed-modes/default-fig1-fixed-modes.json'
SPEC = importlib.util.spec_from_file_location('library_trace', HERE.parent / '2026-11-15-library-trace/trace.py')
tr = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tr)


def source_path(kind):
    return SOURCE if kind == 'good' else HERE / 'default-seed.json'


def load_seed(model, kind='good'):
    source = json.loads(source_path(kind).read_text())
    template = model.solution(model.y)
    assert source['instance'] == template['instance'] and source['phys'] == template['phys']
    assert len(source['solution']['r']) == model.stamps == 37
    trajectory = source['solution']
    x = np.r_[np.array(trajectory['r'][1:-1]).ravel(), trajectory['e'][1:], trajectory['s'], trajectory['c']]
    y = np.ascontiguousarray(x / model.scale)
    decoded = tr.decode(model, y, template)
    for key in trajectory:
        np.testing.assert_allclose(decoded[key], trajectory[key], rtol=1e-15, atol=1e-15)
    if kind == 'good':
        residuals = tr.diag.residuals(source)
        assert residuals['viol'] < 1e-10
        replay = tr.diag.replay(source)
        assert min(replay) >= 0. and max(replay) <= 1.
    else:
        np.testing.assert_allclose(y, model.y, atol=1e-14, rtol=1e-15)
    assert abs(sum(trajectory['s']) - source['metrics']['objective']) < 1e-13
    return source, y


def assess(model, original, y, lam, mu, source, eps, p):
    normalized = tr.kkt(model, y, lam, mu)
    canonical = tr.kkt(original, y, lam, tr.original_multipliers(model, y, source, mu))
    selection = tr.describe(model, y, source, eps, p)
    return dict(normalized_kkt=normalized, original_kkt=canonical, selection=selection,
                objective=float(sum(tr.decode(model, y, source)['s'])))


def export(folder, model, original, y, lam, mu, source, eps, p, rows, stop, seconds, name, seed_kind='good'):
    result = dict(**tr.state(y, lam, mu, 1e4, eps, p, rows[-1]['stage'] if rows else 13),
                  **assess(model, original, y, lam, mu, source, eps, p),
                  stop=stop, outer_total=len(rows), seconds=seconds, name=name)
    result['kkt_converged'] = bool(result['stage'] == 13 and max(result['original_kkt'].values()) <= 1e-6)
    tr.write(folder / 'result.json', result)
    doc = model.solution(y)
    doc['init'] = copy.deepcopy(source['solution'])
    doc['metrics'].update(init_objective=source['metrics']['objective'], seconds=seconds,
                          converged=result['kkt_converged'])
    doc['experiment'] = dict(name=name, paper_algorithm=False, source=str(source_path(seed_kind).relative_to(ROOT)), seed_kind=seed_kind,
        y_full_precision=y.tolist(), lam=lam.tolist(), mu=mu.tolist(),
        final_original_kkt=result['original_kkt'], stop=stop, outer_total=len(rows),
        source_objective=source['metrics']['objective'])
    tr.write(folder / 'solution.json', doc)
    print(json.dumps({key: result[key] for key in ['name', 'objective', 'original_kkt', 'stop', 'outer_total', 'seconds', 'kkt_converged']}), flush=True)
    return result


def run(backend, route, seed_kind='good'):
    name = backend + ('-default' if seed_kind == 'default' else '') + '-' + route
    folder = HERE / 'runs' / name
    folder.mkdir(parents=True, exist_ok=False)
    model, original = (tr.Model(0, 0, tr.LIBRARIES[key]) for key in ['normalized', 'original'])
    source, y = load_seed(model, seed_kind)
    lam, mu = np.zeros(model.me), np.zeros(model.mi)
    schedule = [(13, .0005, 12., 150)] if route == 'direct' else [
        (stage+1, max(.0005, .2*.6**stage), min(12., 2.*1.2**stage), 30 if stage == 12 else 10) for stage in range(13)]
    tr.write(folder / 'initial.json', dict(**tr.state(y, lam, mu, 1e4, schedule[0][1], schedule[0][2], schedule[0][0]),
        source=str(source_path(seed_kind).relative_to(ROOT)), seed_kind=seed_kind, source_objective=source['metrics']['objective']))
    start, rows, stop = monotonic(), [], 'outer_limit'
    with gzip.open(folder / 'outer.jsonl.gz', 'wt') as log:
        for stage, eps, p, budget in schedule:
            model.stage(eps, p)
            original.stage(eps, p)
            tr.write(folder / f'stage{stage:02d}-start.json', dict(**tr.state(y, lam, mu, 1e4, eps, p, stage),
                **assess(model, original, y, lam, mu, source, eps, p)))
            for outer in range(budget):
                if monotonic() - start >= 120:
                    stop = 'timeout'
                    break
                inner = tr.inner(model, y, lam, mu, 1e4, backend, start+120)
                point = inner.pop('y')
                if inner['interrupted']:
                    tr.write(folder / 'interrupted-inner.json', dict(y=point.tolist(), **inner))
                    stop = 'timeout'
                    break
                y = point
                model.eval(y, lam, mu, 0.)
                lam += 1e4 * model.h
                mu = np.maximum(0., mu+1e4*model.g)
                row = dict(**tr.state(y, lam, mu, 1e4, eps, p, stage), outer=outer+1,
                           **assess(model, original, y, lam, mu, source, eps, p), inner=inner, elapsed=monotonic()-start)
                rows.append(row)
                log.write(json.dumps(row, allow_nan=False)+'\n')
                log.flush()
                if route == 'direct' and outer == 29:
                    tr.write(folder / 'checkpoint30.json', row)
                norm_pass = max(row['normalized_kkt'].values()) <= 1e-6
                canonical_pass = max(row['original_kkt'].values()) <= 1e-6
                if norm_pass and (stage != 13 or canonical_pass):
                    if stage == 13:
                        stop = 'kkt'
                    break
            tr.write(folder / f'stage{stage:02d}-end.json', dict(**tr.state(y, lam, mu, 1e4, eps, p, stage),
                **assess(model, original, y, lam, mu, source, eps, p)))
            print(json.dumps(dict(name=name, stage=stage, outer_total=len(rows), objective=float(model.objective[0]),
                elapsed=monotonic()-start)), flush=True)
            if stop in ['timeout', 'kkt']:
                break
    result = export(folder, model, original, y, lam, mu, source, eps, p, rows, stop, monotonic()-start, name, seed_kind)
    model.close()
    original.close()
    return result


def continue_newton(seed_kind='good'):
    case = 'scipy-bfgs' + ('-default' if seed_kind == 'default' else '') + '-direct'
    path = HERE / 'runs' / case / 'result.json'
    saved = json.loads(path.read_text())
    if saved['kkt_converged']:
        tr.write(HERE / ('newton-' + seed_kind + '-skipped.json'), dict(reason='direct BFGS already reached original KKT'))
        return
    sys.path.insert(0, str(HERE.parent / '2026-11-14-conditioning'))
    import newton_al as na
    name = 'newton-default' if seed_kind == 'default' else 'newton'
    folder = HERE / name
    folder.mkdir(exist_ok=False)
    model, original = (tr.Model(0, 0, tr.LIBRARIES[key]) for key in ['normalized', 'original'])
    source, _ = load_seed(model, seed_kind)
    model.stage(.0005, 12.)
    original.stage(.0005, 12.)
    y, lam, mu = (np.array(saved[key]) for key in ['y', 'lam', 'mu'])
    tr.write(folder / 'initial.json', dict(**tr.state(y, lam, mu, 1e4, .0005, 12., 13),
        parent=f'runs/{case}/result.json', seed_kind=seed_kind, parent_outer=saved['outer_total']))
    start, rows, stop = monotonic(), [], 'outer_limit'
    with gzip.open(folder / 'outer.jsonl.gz', 'wt') as log:
        for outer in range(600):
            def fg(point):
                if monotonic()-start > 300:
                    raise TimeoutError()
                return model.eval(point, lam, mu, 1e4)
            try:
                result = na.tr_newton(fg, y, gtol=1e-6, max_iter=300, hessian_step=1e-8)
            except TimeoutError:
                stop = 'timeout'
                break
            y = np.ascontiguousarray(result['y'])
            model.eval(y, lam, mu, 0.)
            lam += 1e4*model.h
            mu = np.maximum(0., mu+1e4*model.g)
            row = dict(**tr.state(y, lam, mu, 1e4, .0005, 12., 13), outer=outer+1,
                **assess(model, original, y, lam, mu, source, .0005, 12.),
                inner=dict(status=result['status'], iterations=result['iters'], evaluations=result['evals']), elapsed=monotonic()-start)
            rows.append(row)
            log.write(json.dumps(row, allow_nan=False)+'\n')
            log.flush()
            tr.write(folder / 'checkpoint.json', row)
            if outer % 25 == 0:
                print(json.dumps(dict(name=name, outer=outer+1, original_kkt=row['original_kkt'], elapsed=monotonic()-start)), flush=True)
            if max(row['original_kkt'].values()) <= 1e-6:
                stop = 'kkt'
                break
    result = export(folder, model, original, y, lam, mu, source, .0005, 12., rows, stop, monotonic()-start, name, seed_kind)
    result['parent_outer'] = saved['outer_total']
    result['total_outer'] = saved['outer_total']+len(rows)
    result['total_seconds'] = saved['seconds']+result['seconds']
    result['hessian_step'] = 1e-8
    tr.write(folder / 'result.json', result)
    model.close()
    original.close()


if __name__ == '__main__':
    assert not (HERE / 'runs').exists(), 'refuse to overwrite existing experiment'
    for backend in tr.BACKENDS:
        for route in ['direct', 'homotopy']:
            run(backend, route)
    continue_newton()
