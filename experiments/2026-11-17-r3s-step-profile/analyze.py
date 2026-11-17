import csv
import json
from pathlib import Path
import statistics

BASE=Path(__file__).resolve().parent
PARTS=['initial_eval_ns','hessian_setup_ns','jacobian_ns','curvature_fd_ns','hessian_assembly_ns','eigh_ns','search_ns','other_ns']


def describe(values):
    return dict(n=len(values),min=min(values),median=statistics.median(values),max=max(values),total=sum(values))


def main():
    assert not (BASE/'summary.json').exists()
    results=[]
    for state in json.loads((BASE/'states.json').read_text()):
        with (BASE/'cases'/state['case']/'timings.csv').open() as stream:rows=list(csv.DictReader(stream))
        assert len(rows)==21
        sums={k:sum(int(r[k]) for r in rows) for k in PARTS}
        total=sum(int(r['total_ns']) for r in rows)
        assert sum(sums.values())==total
        parts={k:dict(timing_ns=describe([int(r[k]) for r in rows]),share=sums[k]/total) for k in PARTS}
        result=dict(case=state['case'],variables=int(rows[0]['variables']),measurements=len(rows),
                    original_ns=describe([int(r['baseline_ns']) for r in rows]),
                    profiled_ns=describe([int(r['total_ns']) for r in rows]),parts=parts,
                    hessian_share=sum(parts[k]['share'] for k in ['hessian_setup_ns','jacobian_ns','curvature_fd_ns','hessian_assembly_ns']),
                    trials=sorted({int(r['trials']) for r in rows}))
        result['profiled_to_original_median_ratio']=result['profiled_ns']['median']/result['original_ns']['median']
        results.append(result)
    (BASE/'summary.json').write_text(json.dumps(dict(cases=results,measured_pairs=63,warmup_pairs=9,
          single_process=True,full_solves=0,returned_points_changed=0),indent=2)+'\n')
    for r in results:
        print(json.dumps(dict(case=r['case'],original_ms=r['original_ns']['median']/1e6,
             profiled_ms=r['profiled_ns']['median']/1e6,profiled_to_original=r['profiled_to_original_median_ratio'],
             phase_percent={k:100*v['share'] for k,v in r['parts'].items()})))


if __name__=='__main__':main()
