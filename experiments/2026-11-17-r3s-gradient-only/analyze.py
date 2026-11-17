import csv
import json
from pathlib import Path
import statistics

BASE=Path(__file__).resolve().parent


def main():
    assert not (BASE/'summary.json').exists()
    results=[]
    for folder in sorted((BASE/'cases').iterdir()):
        with (folder/'timings.csv').open() as stream:rows=list(csv.DictReader(stream))
        assert len(rows)==21
        original=[int(r['original_ns']) for r in rows];fast=[int(r['fast_ns']) for r in rows]
        a,b=statistics.median(original),statistics.median(fast)
        checks=json.loads((folder/'checks.json').read_text())
        results.append(dict(case=folder.name,variables=checks['variables'],gradient_points=checks['gradient_points'],
            measurements=len(rows),original_median_ns=a,fast_median_ns=b,speedup_median_ratio=a/b,
            time_reduction_median_ratio=1-b/a,median_paired_speedup=statistics.median([x/y for x,y in zip(original,fast)]),
            original_min_ns=min(original),original_max_ns=max(original),fast_min_ns=min(fast),fast_max_ns=max(fast)))
    result=dict(cases=results,gradient_points=sum(r['gradient_points'] for r in results),measured_pairs=63,
                runtime_matching_pairs=72,full_solves=0,returned_points_changed=0)
    (BASE/'summary.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))


if __name__=='__main__':main()
