import csv
from datetime import datetime,timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys
from time import monotonic
import numpy as np
from scipy.stats import wasserstein_distance,ks_2samp
from metrics import distribution,missing_median_bounds,objective_from_point

BASE=Path(__file__).resolve().parent;ROOT=BASE.parents[1]
COHORT=ROOT/'experiments/2026-11-16-r3s-cohort'


def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')


def collect():
    summary=read(COHORT/'summary.json');targets=read(COHORT/'targets.json')
    assert summary['finished']==summary['terminal']==summary['planned']==900 and summary['pending']==0
    assert summary['final_distribution_complete']
    by_case={r['case']:r for r in summary['cases']};assert len(by_case)==900 and set(by_case)==set(targets['cases'])
    sources={};rows=[]
    def track(path):sources[str(path.relative_to(ROOT))]=sha(path)
    for path in [COHORT/'summary.json',COHORT/'targets.json',COHORT/'protocol.json',COHORT/'REPORT.md',
        ROOT/'experiments/2026-11-16-r3a-cohort/protocol.json',ROOT/'data/paper_fig3.csv',
        ROOT/'scripts/extract_paper_figures.py',ROOT/'experiments/2026-11-14-paper-figures/REPORT.md',ROOT.parent/'2609.40201v1.pdf']:
        # The PDF is external to the nested Git root.
        sources[str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else '../'+path.name]=sha(path)
    for root in [ROOT/'experiments/2026-11-16-r3a-cohort',COHORT]:
        for path in sorted((root/'batches').glob('*/artifact-index.json')):track(path)
    for target in targets['rows']:
        case=target['case'];r=by_case[case];assert r['state']=='finished' and r['error'] is None
        origin=ROOT/'experiments'/r['origin'];raw_path=origin/'runs'/case/'result.json';track(raw_path)
        raw=read(raw_path);assert raw['case']==case and raw['error'] is None;out=raw['outcome'];available=out['physical_point_available']
        for key in ['selected_hours','physical_point_available','selected_same_final_branch_kkt','selected']:
            assert out[key]==r[key],(case,key)
        assert raw['route']==r['route']
        selected=origin/'runs'/case/'selected.json';hours=None
        if available:
            track(selected);assert sha(selected)==out['selected_sha256'];point=read(selected)
            assert len(point['instance']['tasks'])==target['tau']
            hours=objective_from_point(point,out['selected_hours'])
            assert point['metrics']['viol']<=1e-6
        else:
            assert out['selected_hours'] is None and out['selected'] is None and not selected.exists()
        rows.append(dict(case=case,tau=target['tau'],seed=target['seed'],run=target['run'],origin=r['origin'],
            route=r['route'],selected=r['selected'],physical_point_available=available,
            fixed_branch_kkt=out['selected_same_final_branch_kkt'],final_common_kkt=r['final_common_kkt'],
            final_both_scales_kkt=r['final_both_scales_kkt'],objective_h=hours,
            selected_source=None if not available else str(selected.relative_to(ROOT))))
    assert sum(r['physical_point_available'] for r in rows)==894
    assert sum(r['fixed_branch_kkt'] for r in rows)==830
    for tau in range(1,10):assert sum(r['tau']==tau for r in rows)==100
    return rows,sources


def verify_sources():
    for name,digest in read(BASE/'source-index.json').items():assert sha(ROOT/name)==digest,name


def main():
    if '--freeze' in sys.argv:
        assert not (BASE/'source-index.json').exists();rows,sources=collect();write(BASE/'source-index.json',sources)
        print(json.dumps(dict(frozen_sources=len(sources),cases=len(rows),available=sum(r['physical_point_available'] for r in rows))));return
    start=monotonic();verify_sources();rows,sources=collect();assert sources==read(BASE/'source-index.json')
    assert not (BASE/'summary.json').exists()
    with (ROOT/'data/paper_fig3.csv').open() as stream:paper=list(csv.DictReader(stream))
    paper_groups={(method,tau):[float(r['value']) for r in paper if r['quantity']=='objective_h' and r['method']==method and int(r['tau'])==tau]
        for method in ['NLP','SCIP','Juniper'] for tau in range(1,10)}
    for method in ['NLP','SCIP','Juniper']:
        for tau in range(1,10):assert len(paper_groups[method,tau])==(99 if method=='Juniper' and tau==6 else 100)
    groups=[];flat=[]
    for tau in range(1,10):
        cases=[r for r in rows if r['tau']==tau];available=[r for r in cases if r['physical_point_available']]
        vals=[r['objective_h'] for r in available];cert=[r['objective_h'] for r in available if r['fixed_branch_kkt']]
        own=distribution(vals);reference=distribution(paper_groups['NLP',tau]);lo,hi=missing_median_bounds(vals,100)
        group=dict(tau=tau,total=100,returned=len(vals),missing=100-len(vals),certified=len(cert),
            selected=own,certified_objective=distribution(cert),paper={m:distribution(paper_groups[m,tau]) for m in ['NLP','SCIP','Juniper']},
            median_ratio=own['median']/reference['median'],median_difference_h=own['median']-reference['median'],
            median_difference_min=60*(own['median']-reference['median']),
            missing_median_lower_h=lo,missing_median_upper_h=hi,
            missing_median_ratio_lower=lo/reference['median'],missing_median_ratio_upper=hi/reference['median'],
            wasserstein_h=float(wasserstein_distance(vals,paper_groups['NLP',tau])),
            ecdf_max_difference_conditional=float(ks_2samp(vals,paper_groups['NLP',tau]).statistic),
            by_origin={origin:distribution([r['objective_h'] for r in available if r['origin']==origin]) for origin in sorted({r['origin'] for r in rows})},
            by_route={route:distribution([r['objective_h'] for r in available if r['route']==route]) for route in ['G','fallback']},
            by_selected={selection:distribution([r['objective_h'] for r in available if r['selected']==selection]) for selection in ['restoration','certificate','original','constructed']})
        groups.append(group)
        flat.append(dict(tau=tau,total=100,returned=len(vals),missing=100-len(vals),certified=len(cert),
            paper_median_h=reference['median'],selected_q25_h=own['q25'],selected_median_h=own['median'],selected_q75_h=own['q75'],
            median_ratio=group['median_ratio'],median_difference_min=group['median_difference_min'],
            certified_median_h=group['certified_objective']['median'],missing_median_lower_h=lo,missing_median_upper_h=hi,
            wasserstein_h=group['wasserstein_h'],ecdf_max_difference_conditional=group['ecdf_max_difference_conditional']))
    for name,data in [('cases.csv',rows),('by-tau.csv',flat)]:
        with (BASE/name).open('w',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(data[0]),lineterminator='\n');writer.writeheader();writer.writerows(data)
    result=dict(date='2026-11-17',cases=900,returned=894,missing=6,certified=830,
        origins={origin:sum(r['origin']==origin for r in rows) for origin in sorted({r['origin'] for r in rows})},
        paper_objective_counts={m:sum(len(paper_groups[m,t]) for t in range(1,10)) for m in ['NLP','SCIP','Juniper']},
        quantile_method='linear',missing_rows_preserved=True,paired_with_paper=False,optimizer_launched=False,groups=groups)
    write(BASE/'summary.json',result)
    lines=['# R3/R3sと論文図3 NLPの目的値分布','',
        '| tau | 返却/100 | 固定分岐KKT | 論文中央値 h | 手元中央値 h | 比 | 差 分 | 手元Q25–Q75 h |',
        '|---:|---:|---:|---:|---:|---:|---:|---|']
    for r in flat:lines.append(f"| {r['tau']} | {r['returned']} | {r['certified']} | {r['paper_median_h']:.6f} | {r['selected_median_h']:.6f} | {r['median_ratio']:.3f} | {r['median_difference_min']:.2f} | {r['selected_q25_h']:.3f}–{r['selected_q75_h']:.3f} |")
    lines+=['','比は対応のない集団の中央値の比。手元は実行可能返却点、論文はNLPの全描画点。','欠測6件はcases.csvに残し、中央値範囲と分母100のECDFも別に示す。','']
    (BASE/'comparison.md').write_text('\n'.join(lines))
    write(BASE/'execution.json',dict(command=[sys.executable,*sys.argv],head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        recorded_utc=datetime.now(timezone.utc).isoformat(),seconds=monotonic()-start,python=sys.version,
        packages={m:importlib.metadata.version(m) for m in ['numpy','scipy','matplotlib']},optimizer_launched=False))
    verify_sources();print(json.dumps(flat))


if __name__=='__main__':main()
