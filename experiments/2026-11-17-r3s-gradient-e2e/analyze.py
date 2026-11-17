import csv
import gzip
import hashlib
import json
from pathlib import Path
import sys

BASE=Path(__file__).resolve().parent;ROOT=BASE.parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from repair_initialization import audit


def read(p):return json.loads(p.read_text())
def write(p,v):p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')


def snapshot():
    rows=[]
    for case in read(BASE/'targets.json')['cases']:
        for mode in ['original','fast']:
            base=BASE/mode;folder=base/'cases/G'/case;result=base/'runs'/case/'result.json'
            g=read(folder/'result.json') if (folder/'result.json').exists() else None
            raw=read(result) if result.exists() else None
            rows.append(dict(case=case,mode=mode,finished=raw is not None,error=None if raw is None else raw['error'],
                G_stage=None if g is None else g['stage'],G_stop=None if g is None else g['stop'],
                G_seconds=None if g is None else g['elapsed'],
                G_common=None if g is None else g['final_common_pass'],G_physical=None if g is None else g['final_both_scales_pass'],
                route=None if raw is None else raw.get('route'),
                returned_h=None if raw is None or raw['error'] else raw['outcome']['selected_hours']))
    return rows


def main():
    rows=snapshot()
    if '--status' in sys.argv:
        print(json.dumps(rows));return
    assert not (BASE/'summary.json').exists() and all(r['finished'] for r in rows)
    for name,digest in read(BASE/'source-index.json').items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
    for row in rows:
        base=BASE/row['mode'];case=row['case'];raw=read(base/'runs'/case/'result.json')
        if raw['error']:
            row.update(physical_audit=False,certificate=False,selected=None,seconds=raw['seconds']);continue
        assert not raw['g_reused'] and not raw['fallback_cache_used']
        outcome=raw['outcome']
        row.update(physical_audit=False,certificate=outcome['selected_same_final_branch_kkt'],selected=outcome['selected'],
                   final_common=outcome['final_common_kkt'],final_physical=outcome['final_both_scales_kkt'],
                   restoration=outcome['last_restoration_solver_accepted'],seconds=raw['seconds'])
        if outcome['physical_point_available']:
            p=base/'runs'/case/'selected.json';data=read(p)
            assert hashlib.sha256(p.read_bytes()).hexdigest()==outcome['selected_sha256']
            check=audit(data);assert check['accepted'];row['physical_audit']=True
            assert abs(sum(data['solution']['s'])-row['returned_h'])<1e-12
            row['returned_original_residual']=check['original_residuals']['viol']
    comparisons=[]
    for case in read(BASE/'targets.json')['cases']:
        old,new=[next(r for r in rows if r['case']==case and r['mode']==m) for m in ['original','fast']]
        a,b=[BASE/m for m in ['original','fast']]
        inputs=[read(p/'inputs'/case/'input.json') for p in [a,b]]
        assert all(inputs[0][k]==inputs[1][k] for k in ['instance','phys','solution','modes','task_stamp'])
        original_input=read(ROOT/'experiments/2026-11-16-r3s-cohort/inputs'/case/'input.json')
        assert inputs[0]['solution']==original_input['solution']
        common=0;identical=True;differences=[]
        for stage in range(1,14):
            logs=[p/'cases/G'/case/'stages'/f'stage{stage:02d}'/'outer.jsonl.gz' for p in [a,b]]
            if not all(p.exists() for p in logs):continue
            data=[]
            for p in logs:
                with gzip.open(p,'rt') as stream:data.append([json.loads(line) for line in stream])
            for index,(x,y) in enumerate(zip(*data),1):
                common+=1
                keys=['y','lam','mu','rho','rho_next','objective','common_kkt','paper_units_kkt']
                equal=all(x[k]==y[k] for k in keys)
                if not equal:identical=False;differences.append(dict(stage=stage,outer=index))
        trajectory_same=None
        paths=[p/'runs'/case/'selected.json' for p in [a,b]]
        if all(p.exists() for p in paths):
            points=[read(p) for p in paths]
            trajectory_same=all(points[0][k]==points[1][k] for k in ['solution','modes','task_stamp'])
        comparisons.append(dict(case=case,G_stage_original=old['G_stage'],G_stage_fast=new['G_stage'],
            original_route=old['route'],fast_route=new['route'],original_h=old['returned_h'],fast_h=new['returned_h'],
            delta_seconds=None if old['returned_h'] is None or new['returned_h'] is None else 3600*(new['returned_h']-old['returned_h']),
            G_speedup=old['G_seconds']/new['G_seconds'],common_outer_points=common,
            common_outer_states_equal=identical,first_differences=differences[:3],returned_trajectory_equal=trajectory_same))
    with (BASE/'cases.csv').open('w') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(dict.fromkeys(k for r in rows for k in r)),lineterminator='\n')
        writer.writeheader();writer.writerows(rows)
    write(BASE/'summary.json',dict(rows=rows,comparisons=comparisons,wall_seconds=read(BASE/'completion.json')['wall_seconds'],
         new_full_runs=8,software_errors=sum(r['error'] is not None for r in rows),paper_reproduction=False))
    print(json.dumps(comparisons))


if __name__=='__main__':main()
