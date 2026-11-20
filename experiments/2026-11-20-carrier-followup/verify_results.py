"""Recheck stored points, input immutability, deterministic repetitions and summaries."""
import hashlib
import json
from pathlib import Path
import statistics
from verify_point import check

BASE=Path(__file__).resolve().parent;ROOT=BASE.parents[1]


def read(path):return json.loads(path.read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    for filename in ('source-index.json','reduced-start-index.json'):
        for rel,digest in read(BASE/filename).items():assert sha(ROOT/rel)==digest,rel
    for rel,digest in read(BASE/'code-index.json').items():assert sha(BASE/rel)==digest,rel
    source={r['case']:ROOT/r['path'] for r in read(ROOT/'experiments/2026-11-18-r3s-carrier/source-index.json')['points']}
    original=read(BASE/'results.json');comparison=read(BASE/'comparison.json');extra=read(BASE/'reduced-start-results.json')
    assert original[:72]==comparison and len(original)==76 and len(extra)==4
    all_rows=original+extra;checks=[]
    for row in all_rows:
        p=ROOT/row['solution_path'];assert sha(p)==row['point_sha256'];d=read(p)
        audit=check(d,read(source[row['case']]))
        assert audit==row['independent'] and audit['accepted']==row['accepted'],p
        assert abs(sum(d['solution']['s'])-row['objective_hours'])<1e-12
        assert row['seconds']>0 and row['total_call_seconds']>=row['seconds']
        raw=read(p.with_name(p.stem+'-solver.json'))
        assert len(raw['x'])==row['variables'] and raw['options']==read(BASE/'environment.json')['options']
        checks.append(dict(point=str(p.relative_to(ROOT)),phase=row['phase'],accepted=audit['accepted'],max_time_correction_seconds=3600*row['max_roundoff_time_correction_hours']))
    cases=[]
    for case in dict.fromkeys(r['case'] for r in comparison):
        item=dict(case=case)
        for method in ('R','q'):
            rows=[r for r in comparison if r['case']==case and r['method']==method and not r['warmup']]
            assert len(rows)==5
            trajectories=[read(ROOT/r['solution_path']) for r in rows]
            signature=lambda d:json.dumps({k:d[k] for k in ('solution','modes','task_stamp','carrier_positions')},sort_keys=True)
            assert len({signature(d) for d in trajectories})==1
            assert len({(r['iterations'],r['solver_status']) for r in rows})==1
            item[method]=dict(accepted=rows[0]['accepted'],solver_success=rows[0]['solver_success'],
                objective_hours=rows[0]['objective_hours'],iterations=rows[0]['iterations'],variables=rows[0]['variables'],
                inequalities=rows[0]['inequalities'],time_median_ms=1000*statistics.median(r['seconds'] for r in rows),
                time_min_ms=1000*min(r['seconds'] for r in rows),time_max_ms=1000*max(r['seconds'] for r in rows),
                total_median_ms=1000*statistics.median(r['total_call_seconds'] for r in rows),
                raw_kkt=rows[0]['kkt'],max_time_correction_seconds=3600*rows[0]['max_roundoff_time_correction_hours'])
        item['same_quality']=bool(item['R']['accepted'] and item['q']['accepted'] and item['R']['solver_success'] and item['q']['solver_success'] and abs(item['R']['objective_hours']-item['q']['objective_hours'])<=1e-6)
        item['q_over_R_solver_time_ratio']=item['q']['time_median_ms']/item['R']['time_median_ms']
        cases.append(item)
    for row in read(BASE/'construction.json'):
        d=read(BASE/'construction'/f"{row['case']}.json");ref=read(source[row['case']]);audit=check(d,ref)
        assert audit==row['independent'] and audit['accepted']
        assert d['solution']['r']==ref['solution']['r']
        assert all(s==d['phys']['s_max'] for m,s in zip(d['modes'],d['solution']['s']) if m>=0)
    assert sum(c['same_quality'] for c in cases)==3
    result=dict(passed=True,new_solves=len(all_rows),comparison_measured=60,comparison_warmup=12,extra_feasible_starts=8,
        deterministic_constructions=2,original_start_R_feasible=sum(c['R']['accepted'] for c in cases),
        original_start_q_feasible=sum(c['q']['accepted'] for c in cases),original_start_R_success=sum(c['R']['solver_success'] for c in cases),
        original_start_q_success=sum(c['q']['solver_success'] for c in cases),same_quality_pairs=3,cases=cases,
        tau9_reduced_start_both_accepted=all(r['accepted'] for r in extra),prior_outputs_changed=False)
    (BASE/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
    (BASE/'verification.json').write_text(json.dumps(dict(passed=True,points_checked=len(checks),checks=checks),indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='cases'}))
    for c in cases:print(c['case'],json.dumps(c))


if __name__=='__main__':main()
