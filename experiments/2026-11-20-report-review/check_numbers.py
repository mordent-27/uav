"""Read-only audit of numbers used in report.tex; no optimization and no legacy writes."""
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys
import numpy as np

BASE=Path(__file__).resolve().parent;ROOT=BASE.parents[1]


def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    for name,digest in read(BASE/'source-index.json').items():assert sha(ROOT/name)==digest,name
    for name,digest in read(BASE/'numeric-input-index.json').items():assert sha(ROOT/name)==digest,name
    carrier=ROOT/'experiments/2026-11-18-r3s-carrier';index=read(carrier/'source-index.json')
    with (carrier/'cases.csv').open() as stream:saved={r['case']:r for r in csv.DictReader(stream)}
    by_tau={t:dict(points=0,revisit=0,late=0) for t in range(1,10)};gaps=[];dash=0
    for item in index['points']:
        path=ROOT/item['path'];assert sha(path)==item['sha256'];data=read(path)
        r=np.array(data['solution']['r']);s=np.array(data['solution']['s']);m=data['modes'];vc=data['phys']['v_c']
        time=np.r_[0.,np.cumsum(s)];worst=0.;revisit=False
        for j in range(len(data['instance']['regions'])):
            seg=[k for k,mode in enumerate(m) if mode==j]
            # Consecutive charging segments form one visit, not a departure and revisit.
            revisit|=any(b>a+1 for a,b in zip(seg,seg[1:]))
            for a,b in zip(seg,seg[1:]):worst=max(worst,float(np.linalg.norm(r[b]-r[a+1])-vc*(time[b]-time[a+1])))
        late=worst>1e-9;row=saved[item['case']];assert late==(row['status']=='carrier_late')
        assert abs(worst-float(row['max_excess_km']))<1e-9
        tau=int(item['case'][3:item['case'].index('-')]);by_tau[tau]['points']+=1;by_tau[tau]['revisit']+=int(revisit);by_tau[tau]['late']+=int(late)
        assert len(r)==5*tau+2
        if late:
            gaps.append(worst);a,b=json.loads(row['worst_pair']);j=int(row['worst_region']);reg=data['instance']['regions'][j]
            inside=all(math.dist(q,reg['o'])<=reg['rho']+1e-6 for q in data['solution']['r'][a:b+1])
            task=any(a<stamp<b for stamp in data['task_stamp']);dash+=int(inside and not task)
    assert sum(x['points'] for x in by_tau.values())==894
    assert sum(x['late'] for x in by_tau.values())==590 and sum(x['revisit'] for x in by_tau.values())==755 and dash==354
    nlp=ROOT/'experiments/2026-11-18-carrier-nlp';source=nlp/'verify.py'
    # Load only its independent check definitions; its legacy main would overwrite verification.json.
    prefix=source.read_text().split('\nrows = ')[0];namespace=dict(__file__=str(source),__name__='review_independent_check')
    exec(compile(prefix,str(source),'exec'),namespace);check=namespace['check'];acceptance=[]
    for item in read(nlp/'results.json'):
        for mode in ['base','carrier']:
            data=read(nlp/'runs'/item['case']/(mode+'.json'));c=check(data)
            ok=(c['energy_gap']<1e-12 and c['min_energy']>=data['phys']['e_min'] and c['tasks']<1e-12 and c['endpoints']<1e-12
                and c['uav_speed']<=1e-10 and c['s_bounds']<=1e-11 and c['contact_disk']<=1e-10 and c['c_exact']==0.)
            if mode=='carrier':ok=ok and max(c['carrier_speed'],c['carrier_disk'],c['carrier_contact'])<=1e-9 and c['carrier_late_km']<=1e-9
            assert bool(ok)==item[mode]['accepted']
            assert abs(sum(data['solution']['s'])-item[mode]['objective_hours'])<1e-12
            acceptance.append(dict(case=item['case'],mode=mode,accepted=bool(ok)))
    assert sum(r['accepted'] for r in acceptance if r['mode']=='carrier')==4
    summary=read(nlp/'summary.json')['cases'];paired=[r for r in summary if r['base_accepted'] and r['carrier_accepted']]
    assert len(paired)==3
    with (ROOT/'data/paper_fig3.csv').open() as stream:paper=list(csv.DictReader(stream))
    select=lambda quantity,method,tau=None:[float(r['value']) for r in paper if r['quantity']==quantity and r['method']==method and (tau is None or int(r['tau'])==tau)]
    violations=select('violation','NLP');assert len(violations)==900 and sum(v>1e-3 for v in violations)==5
    ratios=[statistics.median(select('objective_h','NLP',t))/statistics.median(select('objective_h','SCIP',t)) for t in range(1,10)]
    assert all(statistics.median(select('time_min','NLP',t))<1 for t in range(1,10))
    cap_counts={t:sum(v>599 for v in select('time_min','SCIP',t)) for t in range(1,10)}
    assert cap_counts[1]==24 and all(cap_counts[t]==100 for t in range(5,10))
    sys.path.insert(0,str(ROOT/'experiments/2026-11-17-r3s-final-branches'))
    from diagnostics import rows
    example=read(ROOT/'experiments/2026-11-14-critical/duration-example.json')
    eq,ineq=rows(example,.2,2.,[0.]*(6*len(example['solution']['s'])))
    max_res=max(max(abs(r['value']) for r in eq),max(0.,max(r['value'] for r in ineq)))
    assert max_res<1e-12 and example['solution']['c'][1]>example['solution']['s'][1]
    result=dict(passed=True,carrier_by_tau=by_tau,carrier_points=894,late=590,revisit=755,in_disk_without_task=354,
        late_median_km=statistics.median(gaps),late_max_km=max(gaps),NLP_candidate_checks=acceptance,
        paired_NLP_cases=3,increase_seconds=[r['increase_seconds'] for r in paired],paper_NLP_violation_count_gt_1e_3=5,
        paper_NLP_max_violation=max(violations),paper_SCIP_max_violation=max(select('violation','SCIP')),
        paper_NLP_to_SCIP_median_ratios=ratios,paper_SCIP_near_10h_counts=cap_counts,
        duration_counterexample_residual=max_res,duration_counterexample_charge_seconds=example['solution']['c'][1]*3600,
        exact_visit_distance_upper_m=.0005*math.sqrt(17**(2/12)-1)*1000,new_solves=0,legacy_outputs_changed=False)
    if '--check-only' not in sys.argv:
        assert not (BASE/'number-verification.json').exists()
        (BASE/'number-verification.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ['passed','carrier_points','late','in_disk_without_task','paired_NLP_cases','duration_counterexample_residual','new_solves']}))


if __name__=='__main__':main()
