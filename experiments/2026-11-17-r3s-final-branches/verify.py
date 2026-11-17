import csv
import hashlib
import json
import math
from pathlib import Path
import sys

BASE=Path(__file__).resolve().parent;ROOT=BASE.parents[1]


def read(p):return json.loads(p.read_text())
def close(a,b):assert math.isclose(a,b,abs_tol=2e-8,rel_tol=2e-8),(a,b)


def main():
    for index,root in [('source-index.json',ROOT),('artifact-index.json',BASE)]:
        path=BASE/index
        if path.exists():
            for name,digest in read(path).items():assert hashlib.sha256((root/name).read_bytes()).hexdigest()==digest,name
    summary=read(BASE/'summary.json');assert len(summary['points'])==30
    final=[]
    for r in summary['points']:
        template=read(ROOT/'experiments/2026-11-17-r3s-gradient-e2e/fast/inputs'/r['case']/'input.json')
        if r['point']=='returned':
            returned=read(ROOT/'experiments/2026-11-17-r3s-gradient-e2e/fast/runs'/r['case']/'selected.json')
            assert all(math.dist(a,b)<=1e-9 for a,b in zip(template['instance']['tasks'],returned['instance']['tasks']))
            template=returned
        inst,ph=template['instance'],template['phys'];modes=r['modes'];covered=[]
        for run in r['bounds']:
            start,end=run['start_segment'],run['end_segment'];covered.extend(range(start,end+1))
            assert all(modes[k]<0 for k in range(start,end+1))
            assert start==0 or modes[start-1]>=0
            assert end==len(modes)-1 or modes[end+1]>=0
            ids=[i for _,i in sorted((stamp,i) for i,stamp in enumerate(r['task_stamp']) if start<=stamp<=end+1)]
            assert ids==run['task_ids']
            def region(index):
                q=inst['regions'][index];return (q['o'],q['rho'])
            left=(inst['r0'],0) if start==0 else region(modes[start-1])
            right=(inst['rf'],0) if end==len(modes)-1 else region(modes[end+1])
            nodes=[left]+[(inst['tasks'][i],0) for i in ids]+[right]
            assert len(nodes)==len(run['nodes'])
            for (center,radius),saved in zip(nodes,run['nodes']):assert center==saved['center'] and radius==saved['radius']
            lower=math.fsum(max(0.,math.sqrt(sum((u-v)**2 for u,v in zip(a[0],b[0])))-a[1]-b[1]) for a,b in zip(nodes,nodes[1:]))
            capacity=ph['v_d']/ph['zeta']*(ph['e_max']-ph['e_min'])
            close(lower,run['flight_lower_bound_km']);close(capacity,run['full_battery_range_km'])
            assert run['infeasible_branch_proven']==(lower>capacity+1e-6)
        assert covered==[k for k,m in enumerate(modes) if m<0]
        assert r['infeasible_branch_proven']==any(run['infeasible_branch_proven'] for run in r['bounds'])
        if r['point'].startswith('stage'):
            saved=read(ROOT/'experiments/2026-11-17-r3s-gradient-e2e/fast/cases/G'/r['case']/'stages'/r['point']/'result.json')
            close(r['common_feas'],saved['common_kkt']['feas']);close(r['common_comp'],saved['common_kkt']['comp'])
            assert min(saved['mu'])>=0 and saved['common_kkt']['dual']==0
        if r['point']=='stage13':final.append(r)
    assert len(final)==2 and all(r['infeasible_branch_proven'] for r in final)
    native=read(BASE/'native-model-check.json')
    assert len(native['results'])==2 and all(r['passed'] for r in native['results'])
    assert sum(r['equalities']+r['inequalities'] for r in native['results'])==672
    assert all(r['returned_audit']['accepted'] for r in read(BASE/'energy-detail.json'))
    with (BASE/'points.csv').open() as stream:rows=list(csv.DictReader(stream))
    assert len(rows)==30
    with (BASE/'final-constraints.csv').open() as stream:constraints=list(csv.DictReader(stream))
    assert len(constraints)==672
    for r in final:
        group=[x for x in constraints if x['case']==r['case']]
        feasibility=max(abs(float(x['value'])) if x['row_type']=='equality' else max(0.,float(x['value'])) for x in group)
        close(feasibility,r['common_feas'])
        close(max(float(x['complementarity']) for x in group if x['row_type']=='inequality'),r['common_comp'])
    result=dict(passed=True,points=30,constraint_rows=672,saved_KKT_feas_comp_checks=26,
                independent_branch_bounds=True,final_infeasible_branches=2,returned_physical_points=2,
                new_solves=0,stationarity_recomputed=False)
    if '--check-only' not in sys.argv:
        assert not (BASE/'verification.json').exists()
        (BASE/'verification.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))


if __name__=='__main__':main()
