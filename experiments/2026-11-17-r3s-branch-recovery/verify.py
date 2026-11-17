import csv
import gzip
import hashlib
import json
import math
from pathlib import Path
import sys

BASE=Path(__file__).resolve().parent;ROOT=BASE.parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from repair_initialization import audit


def read(p):return json.loads(p.read_text())
def close(a,b):assert math.isclose(a,b,abs_tol=2e-8,rel_tol=2e-8),(a,b)


def check_bound(point,instance,phys):
    modes,stamps=point['modes'],point['task_stamp'];covered=[];flags=[]
    for r in point['bounds']:
        start,end=r['start_segment'],r['end_segment'];covered.extend(range(start,end+1))
        assert all(modes[k]<0 for k in range(start,end+1))
        assert start==0 or modes[start-1]>=0
        assert end==len(modes)-1 or modes[end+1]>=0
        ids=[i for _,i in sorted((stamp,i) for i,stamp in enumerate(stamps) if start<=stamp<=end+1)]
        assert ids==r['task_ids']
        def region(i):
            q=instance['regions'][i];return (q['o'],q['rho'])
        left=(instance['r0'],0) if start==0 else region(modes[start-1])
        right=(instance['rf'],0) if end==len(modes)-1 else region(modes[end+1])
        nodes=[left]+[(instance['tasks'][i],0) for i in ids]+[right]
        assert len(nodes)==len(r['nodes'])
        for (center,radius),node in zip(nodes,r['nodes']):assert center==node['center'] and radius==node['radius']
        lower=math.fsum(max(0.,math.sqrt(sum((a-b)**2 for a,b in zip(u[0],v[0])))-u[1]-v[1]) for u,v in zip(nodes,nodes[1:]))
        capacity=phys['v_d']/phys['zeta']*(phys['e_max']-phys['e_min'])
        close(lower,r['flight_lower_bound_km']);close(capacity,r['full_battery_range_km'])
        flags.append(lower>capacity+1e-6)
    assert covered==[i for i,m in enumerate(modes) if m<0]
    assert any(flags)==point['infeasible_branch_proven']


def main():
    for index,root in [('source-index.json',ROOT),('counterexample-source-index.json',ROOT),('artifact-index.json',BASE)]:
        path=BASE/index
        if path.exists():
            for name,digest in read(path).items():assert hashlib.sha256((root/name).read_bytes()).hexdigest()==digest,name
    summary=read(BASE/'summary.json');cohort=read(ROOT/'experiments/2026-11-16-r3s-cohort/summary.json')
    successes={r['case']:r for r in cohort['cases'] if r['route']=='G'};assert len(successes)==268
    assert set(successes)=={r['case'] for r in summary['cohort']}
    bad=[];checked=0
    for r in summary['cohort']:
        prior=successes[r['case']];base=ROOT/'experiments'/prior['origin'];folder=ROOT/prior['G']['folder']
        template=read(base/'inputs'/r['case']/'input.json');returned=read(base/'runs'/r['case']/'selected.json')
        assert audit(returned)['accepted']
        entry=read(folder/'stages/stage13/initial.json');end=read(folder/'result.json')
        for label,state,data in [('stage13-entry',entry,template),('G-final',end,template),('returned',None,returned)]:
            p=next(p for p in summary['cohort_points'] if p['case']==r['case'] and p['point']==label)
            if state:
                assert p['modes']==[x['winner'] for x in state['selection']['modes']]
                assert p['task_stamp']==[x['stamp'] for x in state['selection']['tasks']]
            else:assert p['modes']==returned['modes'] and p['task_stamp']==returned['task_stamp']
            check_bound(p,data['instance'],data['phys']);checked+=1
            assert r[{'stage13-entry':'entry_impossible','G-final':'final_impossible','returned':'returned_impossible'}[label]]==p['infeasible_branch_proven']
        if r['entry_impossible']:bad.append(r['case'])
    control=summary['control_points'];template=read(ROOT/'experiments/2026-11-17-r3s-gradient-e2e/fast/inputs/tau7-seed7000005/input.json')
    returned=read(ROOT/'experiments/2026-11-17-r3s-gradient-e2e/fast/runs/tau7-seed7000005/selected.json')
    assert audit(returned)['accepted']
    for p in control:
        data=returned if p['kind']=='returned' else template
        check_bound(p,data['instance'],data['phys']);checked+=1
    transitions=[i for i in range(1,len(control)) if control[i-1]['infeasible_branch_proven'] and not control[i]['infeasible_branch_proven']]
    assert transitions==summary['control_recovery_indices']
    extra=read(BASE/'counterexamples.json');assert set(bad)=={r['case'] for r in extra}
    for r in extra:
        prior=successes[r['case']];base=ROOT/'experiments'/prior['origin'];folder=ROOT/prior['G']['folder'];template=read(base/'inputs'/r['case']/'input.json')
        with gzip.open(folder/'stages/stage13/outer.jsonl.gz','rt') as stream:outer=[json.loads(line) for line in stream]
        assert len(r['points'])==len(outer)+1
        for p in r['points']:
            check_bound(p,template['instance'],template['phys']);checked+=1
            if p['outer']:
                state=outer[p['outer']-1];assert p['rho']==state['rho']
                assert p['modes']==[x['winner'] for x in state['selection']['modes']]
                assert p['task_stamp']==[x['stamp'] for x in state['selection']['tasks']]
        transitions=[i for i in range(1,len(r['points'])) if r['points'][i-1]['infeasible_branch_proven'] and not r['points'][i]['infeasible_branch_proven']]
        assert transitions==r['recovery_indices']
    assert len(bad)==summary['entry_false_stops']==2
    assert not summary['final_impossible'] and not summary['returned_impossible']
    with (BASE/'cohort.csv').open() as stream:csv_rows=list(csv.DictReader(stream))
    assert len(csv_rows)==268 and sum(r['entry_impossible']=='True' for r in csv_rows)==2
    result=dict(passed=True,existing_G_returns=268,physical_return_audits=269,independent_branch_points=checked,
         stage13_entry_false_stops=2,coarse_control_recoveries=2,final_bound_violations=0,new_solves=0)
    if '--check-only' not in sys.argv:
        assert not (BASE/'verification.json').exists()
        (BASE/'verification.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))


if __name__=='__main__':main()
