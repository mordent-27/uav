"""Independent raw-log readback, without importing the analyzer or solver."""
import csv
from collections import Counter
import gzip
import hashlib
import json
import math
from pathlib import Path
import sys

BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[1]


def load(p):return json.loads(p.read_text())


def median(values):
    v=sorted(values); n=len(v)
    return None if not n else (v[(n-1)//2]+v[n//2])/2


def close(a,b):
    assert a is None and b is None or a is not None and b is not None and math.isclose(a,b,abs_tol=1e-7,rel_tol=1e-12),(a,b)


def main():
    for index,root in [('source-index.json',ROOT),('representative-source-index.json',ROOT),('artifact-index.json',BASE)]:
        p=BASE/index
        if p.exists():
            for name,digest in load(p).items():
                assert hashlib.sha256((root/name).read_bytes()).hexdigest()==digest,name
    source=load(ROOT/'experiments/2026-11-16-r3s-cohort/summary.json')
    by_id={r['case']:r for r in source['cases']}
    with (BASE/'cases.csv').open() as stream:rows=list(csv.DictReader(stream))
    with (BASE/'inner.csv').open() as stream:inners=list(csv.DictReader(stream))
    assert len(rows)==len({r['case'] for r in rows})==900 and set(by_id)=={r['case'] for r in rows}
    recomputed=[];raw_inners=[]
    for r in rows:
        old=by_id[r['case']];folder=ROOT/old['G']['folder']/'stages/stage01'
        final=load(folder/'result.json');initial=load(folder/'initial.json')
        with gzip.open(folder/'outer.jsonl.gz','rt') as stream:outer=[json.loads(line) for line in stream]
        is_target=old['origin']=='2026-11-16-r3s-cohort' and old['G']['stage']==1 and old['G']['stop']=='timeout'
        assert r['target']==str(is_target)
        assert r['stage_stop']==final['stop']
        assert int(r['completed_outer'])==len(outer)==final['completed_outer']
        complete=outer[-1] if outer else initial
        assert final['y']==complete['y'] and final['lam']==complete['lam'] and final['mu']==complete['mu']
        for x in outer:
            i=x['inner'];n=len(final['y'])
            assert i['hessian_gradient_calls']==(2*n+1)*i['jacobian_calls']
            previous=math.inf if x['previous_violation'] is None else x['previous_violation']
            gate=x['violation']>1e-6 and x['violation']>.25*previous and i['gradient_inf']<=1e-6 and not x['stage_pass']
            assert x['rho_next']==(min(1e8,x['rho']*10) if gate else x['rho'])
        info=[dict(x['inner'],interrupted=False) for x in outer]
        ip=folder/'interrupted-inner.json'
        if ip.exists():
            interrupted=load(ip)
            assert interrupted['context']['y']==final['y']
            assert interrupted['context']['lam']==final['lam']
            assert interrupted['context']['mu']==final['mu']
            info.append(dict(interrupted['inner'],interrupted=True))
        saved=[x for x in inners if x['case']==r['case']]
        assert len(saved)==len(info)
        for saved_row,raw in zip(saved,info):
            assert saved_row['status']==raw['status'] and saved_row['interrupted']==str(raw['interrupted'])
            for key in ['accepted','iterations','scalar_calls','hessian_gradient_calls','jacobian_calls']:
                assert int(saved_row[key])==raw[key]
            close(float(saved_row['seconds']),raw['seconds'])
            close(float(saved_row['gradient_inf']),raw['gradient_inf'])
        close(float(r['inner_seconds']),sum(x['seconds'] for x in info))
        assert int(r['hessian_builds'])==sum(x['jacobian_calls'] for x in info)
        assert int(r['hessian_gradient_calls'])==sum(x['hessian_gradient_calls'] for x in info)
        raw_inners.extend(dict(x,case=r['case'],target=is_target,origin=old['origin']) for x in info)
        recomputed.append(dict(case=r['case'],target=is_target,origin=old['origin'],tau=int(r['tau']),
                              stop=final['stop'],seconds=final['seconds'],completed=len(outer),rho=final['rho'],kkt=final['common_kkt']))
    summary=load(BASE/'summary.json')
    def check(cases,stats):
        assert len(cases)==stats['n'];ids={r['case'] for r in cases}
        assert dict(Counter(r['stop'] for r in cases))==stats['stage_stops']
        ii=[x for x in raw_inners if x['case'] in ids]
        assert dict(Counter(x['status'] for x in ii))==stats['inner_status']
        assert len(ii)==stats['inner_total']
        assert sum(x['interrupted'] for x in ii)==stats['interrupted_cases']
        assert sum(x['accepted'] for x in ii if x['interrupted'])==stats['interrupted_accepted_total']
        close(sum(x['seconds'] for x in ii if x['interrupted']),stats['interrupted_seconds']['total'])
        close(median([x['completed'] for x in cases]),stats['completed_outer']['median'])
        close(sum(x['seconds'] for x in cases),stats['stage_seconds']['total'])
        for k in ['stat','feas','comp','dual']:
            assert sum(x['kkt'][k]>1e-6 for x in cases)==stats['kkt_blockers'][k]
            close(median([x['kkt'][k] for x in cases]),stats['final_kkt'][k]['median'])
    new=[r for r in recomputed if r['origin']=='2026-11-16-r3s-cohort']
    assert len(new)==876
    check([r for r in new if r['target']],summary['targets'])
    check([r for r in new if not r['target']],summary['controls'])
    check([r for r in recomputed if r['origin']!='2026-11-16-r3s-cohort'],summary['carried'])
    for g in summary['by_tau']:
        check([r for r in new if r['tau']==g['tau'] and r['target']],g['targets'])
        check([r for r in new if r['tau']==g['tau'] and not r['target']],g['controls'])
    table=[line for line in (BASE/'REPORT.md').read_text().splitlines() if any(line.startswith('| '+str(tau)+' |') for tau in range(1,10))]
    assert len(table)==9
    for line,g in zip(table,summary['by_tau']):
        cells=[cell.strip() for cell in line.split('|')[1:-1]];t,c=g['targets'],g['controls']
        assert [int(x) for x in cells[:5]]==[g['tau'],t['n']+c['n'],t['n'],c['stage_stops'].get('kkt',0),c['stage_stops'].get('outer_limit',0)]
        assert cells[-1]==('—' if not c['n'] else format(c['stage_seconds']['median'],'.2f'))
    with (BASE/'representative-traces.csv').open() as stream:traces=list(csv.DictReader(stream))
    assert len(traces)==6
    for row in traces:
        with gzip.open(ROOT/row['source_copy'],'rt') as stream:trace=[json.loads(line) for line in stream]
        initial=trace[1];accepted=trace[2:];endpoint=accepted[-1] if accepted else initial
        assert len(accepted)==int(row['accepted'])
        close(endpoint['value'],float(row['last_AL']));close(initial['value'],float(row['initial_AL']))
        close(endpoint['gradient_inf'],float(row['last_gradient_inf']))
        close(initial['gradient_inf'],float(row['initial_gradient_inf']))
        assert int(row['gradient_fallback_steps'])==sum(p['gradient_fallback'] for p in accepted)
        assert int(row['negative_eigen_steps'])==sum(p['eigen_min']<0 for p in accepted)
        folder=ROOT/by_id[row['case']]['G']['folder']/'stages/stage01'
        if row['interrupted']=='True':
            assert endpoint['y']==load(folder/'interrupted-inner.json')['last_accepted_y']
        else:
            with gzip.open(folder/'outer.jsonl.gz','rt') as stream:out=[json.loads(line) for line in stream]
            assert endpoint['y']==out[int(row['outer'])-1]['y']
    result=dict(passed=True,cases=900,current=876,targets=219,controls=657,raw_inner_records=len(raw_inners),
                independent_raw_readback=True,penalty_rule_verified=True,interrupted_point_not_adopted_verified=True,
                hessian_counter_verified=True,representative_traces_verified=6,new_optimization=False,kkt_recomputed=False)
    if '--check-only' not in sys.argv:
        assert not (BASE/'verification.json').exists()
        (BASE/'verification.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))


if __name__=='__main__':main()
