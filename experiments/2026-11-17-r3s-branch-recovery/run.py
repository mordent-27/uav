import csv
import gzip
import hashlib
import json
from pathlib import Path
import sys

BASE=Path(__file__).resolve().parent;ROOT=BASE.parents[1]
PRIOR=ROOT/'experiments/2026-11-17-r3s-final-branches'
E2E=ROOT/'experiments/2026-11-17-r3s-gradient-e2e'
COHORT=ROOT/'experiments/2026-11-16-r3s-cohort'
CONTROL='tau7-seed7000005'
sys.path.insert(0,str(PRIOR))
from diagnostics import branch_bounds


def read(p):return json.loads(p.read_text())
def write(p,v):p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')


def recoveries(flags):
    return [i for i in range(1,len(flags)) if flags[i-1] and not flags[i]]


def successes():
    summary=read(COHORT/'summary.json')
    selected=[r for r in summary['cases'] if r['route']=='G']
    assert len(selected)==268
    return selected


def source_paths():
    paths=[COHORT/'summary.json',PRIOR/'diagnostics.py',ROOT/'scripts/diagnose_solution.py',ROOT/'scripts/repair_initialization.py']
    for r in successes():
        base=ROOT/'experiments'/r['origin'];case=r['case'];folder=ROOT/r['G']['folder']
        paths.extend([base/'inputs'/case/'input.json',folder/'stages/stage13/initial.json',folder/'result.json',base/'runs'/case/'selected.json'])
    paths.extend([E2E/'fast/inputs'/CONTROL/'input.json',E2E/'fast/runs'/CONTROL/'selected.json'])
    for folder in sorted((E2E/'fast/cases/G'/CONTROL/'stages').glob('stage*')):
        paths.extend([folder/'initial.json',folder/'outer.jsonl.gz'])
    return list(dict.fromkeys(paths))


def branch(template,state):
    return dict(instance=template['instance'],phys=template['phys'],
                modes=[r['winner'] for r in state['selection']['modes']],
                task_stamp=[r['stamp'] for r in state['selection']['tasks']])


def measure(case,label,data):
    bounds=branch_bounds(data)
    assignment=dict(modes=data['modes'],task_stamp=data['task_stamp'])
    return dict(case=case,point=label,branch_sha256=hashlib.sha256(json.dumps(assignment,sort_keys=True).encode()).hexdigest(),
                charging_segments=sum(m>=0 for m in data['modes']),
                max_bound_km=max((r['flight_lower_bound_km'] for r in bounds),default=0),
                range_km=data['phys']['v_d']*(data['phys']['e_max']-data['phys']['e_min'])/data['phys']['zeta'],
                infeasible_branch_proven=any(r['infeasible_branch_proven'] for r in bounds),bounds=bounds,
                **assignment)


def main():
    sources={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in source_paths()}
    if '--freeze' in sys.argv:
        assert not (BASE/'source-index.json').exists();write(BASE/'source-index.json',sources)
        print(json.dumps(dict(sources=len(sources),existing_G_successes=268)));return
    assert sources==read(BASE/'source-index.json') and not (BASE/'summary.json').exists()
    template=read(E2E/'fast/inputs'/CONTROL/'input.json')
    control=[dict(measure(CONTROL,'original',template),stage=0,kind='original',outer=0)]
    for folder in sorted((E2E/'fast/cases/G'/CONTROL/'stages').glob('stage*')):
        initial=read(folder/'initial.json');stage=initial['stage']
        control.append(dict(measure(CONTROL,folder.name+'-entry',branch(template,initial)),stage=stage,kind='entry',outer=0))
        with gzip.open(folder/'outer.jsonl.gz','rt') as stream:
            for line in stream:
                state=json.loads(line)
                control.append(dict(measure(CONTROL,folder.name+'-outer'+str(state['outer']),branch(template,state)),
                    stage=stage,kind='outer',outer=state['outer'],common_pass=state['common_pass']))
    returned=read(E2E/'fast/runs'/CONTROL/'selected.json')
    control.append(dict(measure(CONTROL,'returned',returned),stage=13,kind='returned',outer=0))
    rows=[];details=[]
    for r in successes():
        base=ROOT/'experiments'/r['origin'];case=r['case'];folder=ROOT/r['G']['folder']
        template=read(base/'inputs'/case/'input.json');entry=read(folder/'stages/stage13/initial.json');end=read(folder/'result.json')
        assert end['stage']==13
        returned=read(base/'runs'/case/'selected.json')
        points=[measure(case,'stage13-entry',branch(template,entry)),measure(case,'G-final',branch(template,end)),measure(case,'returned',returned)]
        details.extend(dict(p,origin=r['origin']) for p in points)
        same=points[1]['modes']==points[2]['modes'] and points[1]['task_stamp']==points[2]['task_stamp']
        rows.append(dict(case=case,tau=int(case.split('-')[0][3:]),origin=r['origin'],
                    entry_impossible=points[0]['infeasible_branch_proven'],final_impossible=points[1]['infeasible_branch_proven'],
                    returned_impossible=points[2]['infeasible_branch_proven'],entry_max_bound_km=points[0]['max_bound_km'],
                    final_max_bound_km=points[1]['max_bound_km'],restore_same_branch=same,
                    entry_to_final_branch_changed=points[0]['branch_sha256']!=points[1]['branch_sha256']))
    with (BASE/'cohort.csv').open('w') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]),lineterminator='\n');writer.writeheader();writer.writerows(rows)
    with (BASE/'control.csv').open('w') as stream:
        fields=['case','point','stage','kind','outer','charging_segments','infeasible_branch_proven','max_bound_km','branch_sha256']
        writer=csv.DictWriter(stream,fieldnames=fields,extrasaction='ignore',lineterminator='\n');writer.writeheader();writer.writerows(control)
    result=dict(control_points=control,control_recovery_indices=recoveries([p['infeasible_branch_proven'] for p in control]),
                cohort=rows,cohort_points=details,entry_false_stops=sum(r['entry_impossible'] for r in rows),
                final_impossible=sum(r['final_impossible'] for r in rows),returned_impossible=sum(r['returned_impossible'] for r in rows),
                new_solves=0)
    write(BASE/'summary.json',result)
    print(json.dumps(dict(control_points=len(control),control_recoveries=[control[i]['point'] for i in result['control_recovery_indices']],
          entry_false_stops=result['entry_false_stops'],final_impossible=result['final_impossible'],returned_impossible=result['returned_impossible'],
          restore_branch_changed=sum(not r['restore_same_branch'] for r in rows))))


if __name__=='__main__':main()
