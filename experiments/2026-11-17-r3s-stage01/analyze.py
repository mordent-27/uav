"""Diagnose saved stage-1 logs. Standard library only; no model/solver imports."""
from collections import Counter
import csv
import gzip
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[1]
COHORT = ROOT / 'experiments/2026-11-16-r3s-cohort'


def read(p):
    return json.loads(p.read_text())


def write(p, v):
    p.write_text(json.dumps(v, indent=2, allow_nan=False) + '\n')


def target(row):
    return row['origin'] == COHORT.name and row['G']['stage'] == 1 and row['G']['stop'] == 'timeout'


def blockers(kkt):
    return {k: v > 1e-6 for k, v in kkt.items()}


def hessian_counts(n, inner):
    return inner['hessian_gradient_calls'] == (1 + 2*n) * inner['jacobian_calls']


def next_penalty(rho, violation, previous, gradient, passed):
    increase = violation > 1e-6 and violation > .25*previous and gradient <= 1e-6 and not passed
    return min(1e8, 10*rho) if increase else rho


def distribution(values):
    return dict(n=len(values), min=min(values) if values else None,
                median=statistics.median(values) if values else None, max=max(values) if values else None,
                mean=statistics.mean(values) if values else None, total=sum(values))


def collect():
    sources = {}

    def load(p, zipped=False):
        data = p.read_bytes()
        sources[str(p.relative_to(ROOT))] = hashlib.sha256(data).hexdigest()
        return [json.loads(line) for line in gzip.decompress(data).splitlines()] if zipped else json.loads(data)

    summary = load(COHORT / 'summary.json')
    for p in [COHORT/'protocol.json', COHORT/'run_stall.py',
              ROOT/'experiments/2026-11-15-r2b-coarse/helpers.py',
              ROOT/'experiments/2026-11-15-decomposed-follow/newton.py',
              ROOT/'experiments/2026-11-15-stage4-inner/decomposition.py']:
        sources[str(p.relative_to(ROOT))] = hashlib.sha256(p.read_bytes()).hexdigest()
    rows, inner_rows = [], []
    for case in summary['cases']:
        folder = ROOT/case['G']['folder']/'stages/stage01'
        initial = load(folder/'initial.json'); final = load(folder/'result.json')
        outer = load(folder/'outer.jsonl.gz', zipped=True)
        n = len(final['y']); assert n == len(initial['y'])
        assert len(outer) == final['completed_outer'] <= 10
        if target(case):
            assert final['stage'] == 1 and final['stop'] == 'timeout'
        interrupted_path = folder/'interrupted-inner.json'
        interrupted = load(interrupted_path) if interrupted_path.exists() else None
        for i, row in enumerate(outer):
            assert row['outer'] == i+1
            assert hessian_counts(n, row['inner'])
            previous = math.inf if row['previous_violation'] is None else row['previous_violation']
            assert next_penalty(row['rho'], row['violation'], previous, row['inner']['gradient_inf'], row['stage_pass']) == row['rho_next']
        complete = outer[-1] if outer else initial
        # The runner keeps the last completed outer point, not the interrupted inner point.
        assert final['y'] == complete['y'] and final['lam'] == complete['lam'] and final['mu'] == complete['mu']
        discarded_step = None
        if interrupted:
            assert interrupted['inner']['status'] == 'timeout'
            assert interrupted['context']['y'] == final['y']
            assert interrupted['context']['lam'] == final['lam']
            assert interrupted['context']['mu'] == final['mu']
            assert hessian_counts(n, interrupted['inner'])
            discarded_step = max(abs(a-b) for a, b in zip(interrupted['last_accepted_y'], final['y']))
        records = [(i+1, False, x['inner']) for i, x in enumerate(outer)]
        if interrupted:
            records.append((len(outer)+1, True, interrupted['inner']))
        for index, is_interrupted, info in records:
            inner_rows.append(dict(case=case['case'], tau=int(case['case'].split('-')[0][3:]),
                                   origin=case['origin'], target=target(case), outer=index, interrupted=is_interrupted,
                                   variables=n, **{k: info[k] for k in ['status','iterations','accepted','seconds',
                                   'gradient_inf','scalar_calls','hessian_gradient_calls','jacobian_calls']}))
        rows.append(dict(case=case['case'], tau=int(case['case'].split('-')[0][3:]), origin=case['origin'],
            target=target(case), stage_stop=final['stop'], variables=n, completed_outer=len(outer),
            stage_seconds=final['seconds'], rho_initial=initial['rho'], rho_final=final['rho'],
            initial_h=initial['objective'], final_h=final['objective'],
            common_pass=final['common_pass'], **{k:final['common_kkt'][k] for k in ['stat','feas','comp','dual']},
            last_completed_inner=None if not outer else outer[-1]['inner']['status'],
            interrupted=bool(interrupted), interrupted_accepted=0 if not interrupted else interrupted['inner']['accepted'],
            interrupted_seconds=0. if not interrupted else interrupted['inner']['seconds'],
            interrupted_point_max_scaled_difference=discarded_step,
            inner_seconds=sum(x[2]['seconds'] for x in records),
            hessian_builds=sum(x[2]['jacobian_calls'] for x in records),
            hessian_gradient_calls=sum(x[2]['hessian_gradient_calls'] for x in records),
            accepted_steps=sum(x[2]['accepted'] for x in records),
            rho_increases=sum(x['rho_next']>x['rho'] for x in outer),
            inner_converged=sum(x[2]['status']=='converged' for x in records),
            inner_max_iter=sum(x[2]['status']=='max_iter' for x in records),
            inner_stuck=sum(x[2]['status']=='stuck' for x in records),
            completed_inner_high_gradient=sum(x['inner']['gradient_inf']>1e-6 for x in outer)))
    assert len(rows) == len({r['case'] for r in rows}) == 900
    assert sum(r['target'] for r in rows) == 219
    return rows, inner_rows, sources


def group(rows, inner_rows):
    ids = {r['case'] for r in rows}
    inners = [r for r in inner_rows if r['case'] in ids]
    return dict(n=len(rows), stage_stops=dict(Counter(r['stage_stop'] for r in rows)),
        variables=distribution([r['variables'] for r in rows]),
        completed_outer=distribution([r['completed_outer'] for r in rows]),
        stage_seconds=distribution([r['stage_seconds'] for r in rows]),
        final_rho=dict(Counter(str(r['rho_final']) for r in rows)),
        rho_increases=sum(r['rho_increases'] for r in rows),
        kkt_blockers={k:sum(r[k]>1e-6 for r in rows) for k in ['stat','feas','comp','dual']},
        final_kkt={k:distribution([r[k] for r in rows]) for k in ['stat','feas','comp','dual']},
        inner_status=dict(Counter(r['status'] for r in inners)),
        inner_status_by_case={name:sum(r['inner_'+name]>0 for r in rows) for name in ['converged','max_iter','stuck']},
        inner_total=len(inners), completed_inner_high_gradient=sum(r['completed_inner_high_gradient'] for r in rows),
        last_completed_inner=dict(Counter(str(r['last_completed_inner']) for r in rows)),
        interrupted_cases=sum(r['interrupted'] for r in rows),
        interrupted_with_steps=sum(r['interrupted_accepted']>0 for r in rows),
        interrupted_seconds=distribution([r['interrupted_seconds'] for r in rows if r['interrupted']]),
        interrupted_accepted_total=sum(r['interrupted_accepted'] for r in rows),
        inner_seconds=distribution([r['inner_seconds'] for r in rows]),
        hessian_builds=distribution([r['hessian_builds'] for r in rows]),
        hessian_gradient_calls=distribution([r['hessian_gradient_calls'] for r in rows]),
        accepted_steps=distribution([r['accepted_steps'] for r in rows]),
        seconds_per_hessian_build=distribution([r['inner_seconds']/r['hessian_builds'] for r in rows if r['hessian_builds']]),
        inner_accepted_per_build=distribution([r['accepted']/r['jacobian_calls'] for r in inners if r['jacobian_calls']]))


def verify_sources():
    for name, digest in read(BASE/'source-index.json').items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest() == digest, name


def main():
    if '--freeze' not in sys.argv:
        verify_sources()
    rows, inner, sources = collect()
    if '--freeze' in sys.argv:
        assert not (BASE/'source-index.json').exists()
        write(BASE/'source-index.json', sources)
        print(json.dumps(dict(sources=len(sources), cases=len(rows), inner=len(inner), target=219)))
        return
    assert sources == read(BASE/'source-index.json') and not (BASE/'summary.json').exists()
    for name, data in [('cases.csv',rows),('inner.csv',inner)]:
        with (BASE/name).open('w') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(data[0]), lineterminator='\n')
            writer.writeheader(); writer.writerows(data)
    new = [r for r in rows if r['origin']==COHORT.name]
    targets = [r for r in new if r['target']]
    result = dict(total=900, current=876, targets=group(targets,inner),
                  controls=group([r for r in new if not r['target']],inner),
                  carried=group([r for r in rows if r['origin']!=COHORT.name],inner),
                  by_tau=[dict(tau=tau, targets=group([r for r in targets if r['tau']==tau],inner),
                               controls=group([r for r in new if r['tau']==tau and not r['target']],inner)) for tau in range(1,10)],
                  new_optimization=False, kkt_recomputed=False)
    write(BASE/'summary.json',result)
    ordered=sorted(targets,key=lambda r:(r['completed_outer'],r['variables'],r['case']))
    write(BASE/'representatives.json',[ordered[i] for i in [0,len(ordered)//2,len(ordered)-1]])
    print(json.dumps(dict(targets=result['targets'], controls=result['controls'])))


if __name__ == '__main__':
    main()
