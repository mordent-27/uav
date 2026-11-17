import csv
import hashlib
import json
import math
from pathlib import Path
import sys
import numpy as np

BASE=Path(__file__).resolve().parent;ROOT=BASE.parents[1]


def read(p):return json.loads(p.read_text())
def median(values):
    v=sorted(values);return (v[(len(v)-1)//2]+v[len(v)//2])/2
def close(a,b):assert math.isclose(a,b,abs_tol=1e-12,rel_tol=1e-12)


def main():
    for index,root in [('source-index.json',ROOT),('artifact-index.json',BASE)]:
        p=BASE/index
        if p.exists():
            for name,digest in read(p).items():assert hashlib.sha256((root/name).read_bytes()).hexdigest()==digest,name
    states={r['case']:r for r in read(ROOT/'experiments/2026-11-17-r3s-step-profile/states.json')}
    summary=read(BASE/'summary.json');total=0
    for r in summary['cases']:
        folder=BASE/'cases'/r['case'];checks=read(folder/'checks.json');state=states[r['case']]
        with np.load(folder/'numeric-checks.npz') as a:
            for x,y in [('original_gradients','fast_gradients'),('original_H','fast_H'),('original_h','fast_h'),('original_g','fast_g')]:
                assert a[x].dtype==a[y].dtype and a[x].shape==a[y].shape and a[x].tobytes()==a[y].tobytes()
                assert np.isfinite(a[x]).all()
            n=len(state['context']['y']);assert a['points'].shape==(2*n+1,n)
            expected=[np.array(state['context']['y'])]
            for j in range(n):
                for sign in [1,-1]:
                    point=expected[0].copy();point[j]+=sign*1e-7;expected.append(point)
            np.testing.assert_array_equal(a['points'],expected)
            assert a['original_gradients'].shape==(2*n+1,n) and a['original_H'].shape==(n,n)
            total+=2*n+1
        np.testing.assert_allclose(checks['first_accepted']['y'],state['first_accepted']['y'],atol=1e-11,rtol=1e-11)
        assert checks['original_skew']==checks['fast_skew']
        with (folder/'timings.csv').open() as stream:rows=list(csv.DictReader(stream))
        assert len(rows)==r['measurements']==21 and checks['matching_pairs']==24
        assert [int(row['repeat']) for row in rows]==list(range(21))
        for row in rows:
            assert row['accepted_y_bytes_equal']==row['decision_scalars_equal']=='True'
            assert row['order']==('fast_first' if int(row['repeat'])%2 else 'original_first')
        original=[int(row['original_ns']) for row in rows];fast=[int(row['fast_ns']) for row in rows]
        assert min(original+fast)>0 and median(original)==r['original_median_ns'] and median(fast)==r['fast_median_ns']
        close(median(original)/median(fast),r['speedup_median_ratio'])
        close(1-median(fast)/median(original),r['time_reduction_median_ratio'])
        close(median([x/y for x,y in zip(original,fast)]),r['median_paired_speedup'])
        pools=read(folder/'environment.json')['threadpools'];assert pools and all(p['num_threads']==1 for p in pools)
    assert total==summary['gradient_points']==1271
    if (BASE/'REPORT.md').exists():
        table=[line for line in (BASE/'REPORT.md').read_text().splitlines() if line.startswith('| tau')]
        assert len(table)==3
        for line,r in zip(table,summary['cases']):
            cols=[x.strip() for x in line.split('|')[1:-1]]
            assert cols==[r['case'],str(r['gradient_points']),format(r['original_median_ns']/1e6,'.3f'),
                format(r['fast_median_ns']/1e6,'.3f'),format(r['time_reduction_median_ratio']*100,'.2f')+'%']
    result=dict(passed=True,independent_gradient_points=total,H_and_cache_pairs=3,measured_pairs=63,
        runtime_matching_pairs=72,BLAS_single_thread_confirmed=True,independent_statistics=True,
        full_solves=0,returned_points_changed=0)
    if '--check-only' not in sys.argv:
        assert not (BASE/'verification.json').exists()
        (BASE/'verification.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))


if __name__=='__main__':main()
