import csv
import hashlib
import json
import math
from pathlib import Path
import sys
from diagnostics import decode,rows,branch_bounds

BASE=Path(__file__).resolve().parent;ROOT=BASE.parents[1]
E2E=ROOT/'experiments/2026-11-17-r3s-gradient-e2e'
CASES=['tau8-seed8000006','tau8-seed8000062']


def read(p):return json.loads(p.read_text())
def write(p,v):p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')


def sources():
    paths=[E2E/'artifact-index.json',ROOT/'src/model.rs',ROOT/'src/battery.rs',ROOT/'scripts/diagnose_solution.py',
           ROOT/'experiments/2026-11-15-library-trace/trace.py',ROOT/'experiments/2026-11-15-fidelity/run.py']
    for case in CASES:
        paths.extend([E2E/'fast/inputs'/case/'input.json',E2E/'fast/inputs'/case/'original-state.json',E2E/'fast/runs'/case/'selected.json'])
        paths.extend(sorted((E2E/'fast/cases/G'/case/'stages').glob('stage*/result.json')))
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def main():
    index=sources()
    if '--freeze' in sys.argv:
        assert not (BASE/'source-index.json').exists();write(BASE/'source-index.json',index);print(len(index));return
    assert index==read(BASE/'source-index.json') and not (BASE/'summary.json').exists()
    detailed=[];flat=[];constraints=[]
    for case in CASES:
        template=read(E2E/'fast/inputs'/case/'input.json');scale=read(E2E/'fast/inputs'/case/'original-state.json')['scale']
        initial_modes=template['modes'];states=[('original',template,None)]
        for p in sorted((E2E/'fast/cases/G'/case/'stages').glob('stage*/result.json')):
            state=read(p);selection=state['selection'];data=dict(instance=template['instance'],phys=template['phys'],
                solution=decode(state['y'],scale,template),modes=[r['winner'] for r in selection['modes']],
                task_stamp=[r['stamp'] for r in selection['tasks']])
            states.append((p.parent.name,data,state))
        states.append(('returned',read(E2E/'fast/runs'/case/'selected.json'),None))
        for label,data,state in states:
            bounds=branch_bounds(data);bad=[r for r in bounds if r['infeasible_branch_proven']]
            info=dict(case=case,point=label,charging_segments=sum(m>=0 for m in data['modes']),
                task_stamp=data['task_stamp'],task_order=sorted(range(len(data['task_stamp'])),key=lambda i:data['task_stamp'][i]),
                modes=data['modes'],lost_charge_segments=[i for i,(a,b) in enumerate(zip(initial_modes,data['modes'])) if a>=0 and b<0],
                bounds=bounds,infeasible_branch_proven=bool(bad),objective_h=sum(data['solution']['s']))
            if state:
                eq,ineq=rows(data,state['eps'],state['p'],state['mu'])
                feasibility=max([abs(r['value']) for r in eq]+[max(0.,r['value']) for r in ineq])
                comp=max(r['complementarity'] for r in ineq)
                assert math.isclose(feasibility,state['common_kkt']['feas'],abs_tol=2e-8,rel_tol=2e-8),(case,label,'feas',feasibility,state['common_kkt']['feas'])
                assert math.isclose(comp,state['common_kkt']['comp'],abs_tol=2e-8,rel_tol=2e-8),(case,label,'comp',comp,state['common_kkt']['comp'])
                info.update(common_feas=feasibility,common_comp=comp,top_equalities=sorted(eq,key=lambda r:abs(r['value']),reverse=True)[:5],
                    top_inequalities=sorted(ineq,key=lambda r:r['value'],reverse=True)[:5],
                    top_complementarity=sorted(ineq,key=lambda r:r['complementarity'],reverse=True)[:5],
                    replay=state['selection']['audit'],lost_charge_derivative_share=[dict(segment=i,
                       winner_share=max(state['selection']['modes'][i]['derivative_share']),
                       best_alternative_share=sorted(state['selection']['modes'][i]['derivative_share'],reverse=True)[1]) for i in info['lost_charge_segments']])
                if label=='stage13':
                    for kind,group in [('equality',eq),('inequality',ineq)]:
                        constraints.extend(dict(case=case,row_type=kind,**r) for r in group)
            detailed.append(info);flat.append(dict(case=case,point=label,charging_segments=info['charging_segments'],
                lost_charge_count=len(info['lost_charge_segments']),infeasible_branch_proven=bool(bad),
                max_flight_bound_km=max((r['flight_lower_bound_km'] for r in bounds),default=0),
                objective_h=info['objective_h'],common_feas=info.get('common_feas'),common_comp=info.get('common_comp')))
    with (BASE/'points.csv').open('w') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(flat[0]),lineterminator='\n');writer.writeheader();writer.writerows(flat)
    with (BASE/'final-constraints.csv').open('w') as stream:
        keys=list(dict.fromkeys(k for r in constraints for k in r));writer=csv.DictWriter(stream,fieldnames=keys,lineterminator='\n');writer.writeheader();writer.writerows(constraints)
    write(BASE/'summary.json',dict(points=detailed,new_solves=0,stationarity_recomputed=False))
    print(json.dumps([r for r in flat if r['point'] in ['original','stage13','returned']]))


if __name__=='__main__':main()
