"""Independent manual statistics and saved-state checks; no model calls or solver."""
import csv
import gzip
import hashlib
import json
import math
from pathlib import Path
import sys
import numpy as np

BASE=Path(__file__).resolve().parent;ROOT=BASE.parents[1]


def read(p):return json.loads(p.read_text())
def close(a,b):assert math.isclose(a,b,abs_tol=1e-12,rel_tol=1e-12),(a,b)
def median(v):
    v=sorted(v);n=len(v);return (v[(n-1)//2]+v[n//2])/2


def main():
    for index,root in [('source-index.json',ROOT),('artifact-index.json',BASE)]:
        p=BASE/index
        if p.exists():
            for name,digest in read(p).items():assert hashlib.sha256((root/name).read_bytes()).hexdigest()==digest,name
    summary=read(BASE/'summary.json');states=read(BASE/'states.json')
    assert len(states)==len(summary['cases'])==3
    measured=0
    for state,result in zip(states,summary['cases']):
        assert state['case']==result['case']
        with gzip.open(ROOT/state['source'],'rt') as stream:raw=[json.loads(line) for line in stream]
        assert state['context']==raw[0] and state['input']==raw[1] and state['first_accepted']==raw[2]
        case_dir=BASE/'cases'/state['case'];preflight=read(case_dir/'preflight.json')
        assert all(preflight[k] for k in ['H_bitwise_equal','skew_equal','all_saved_steps_replayed',
                                         'all_profiled_steps_match_original','input_y_unchanged'])
        a,b=preflight['first_step'],state['first_accepted']
        np.testing.assert_allclose(a['y'],b['y'],atol=1e-11,rtol=1e-11)
        for k in ['value','gradient_inf','delta','ratio','prediction','eigen_min','eigen_max']:
            np.testing.assert_allclose(a[k],b[k],atol=1e-10,rtol=1e-10)
        assert a['gradient_fallback']==b['gradient_fallback']
        with np.load(case_dir/'matrices.npz') as matrix:
            n=len(state['context']['y']);assert matrix['H'].shape==(n,n)
            assert np.isfinite(matrix['H']).all();np.testing.assert_allclose(matrix['H'],matrix['H'].T,atol=1e-10,rtol=1e-12)
            np.testing.assert_array_equal(matrix['y'],state['context']['y'])
        env=read(case_dir/'environment.json');assert env['threadpools']
        assert all(p['num_threads']==1 for p in env['threadpools'])
        with (case_dir/'timings.csv').open() as stream:rows=list(csv.DictReader(stream))
        assert len(rows)==preflight['repeats']==21 and preflight['warmup']==3
        assert [int(r['repeat']) for r in rows]==list(range(21))
        parts=[k for k in rows[0] if k.endswith('_ns') and k not in ['total_ns','baseline_ns']]
        for r in rows:
            assert all(int(r[k])>=0 for k in parts)
            assert sum(int(r[k]) for k in parts)==int(r['total_ns'])
            assert r['order']==('profile_first' if int(r['repeat'])%2 else 'original_first')
        total=sum(int(r['total_ns']) for r in rows)
        for field,key in [('total_ns','profiled_ns'),('baseline_ns','original_ns')]:
            vals=[int(r[field]) for r in rows];assert result[key]['n']==len(vals)
            assert sum(vals)==result[key]['total'] and median(vals)==result[key]['median']
            assert min(vals)==result[key]['min'] and max(vals)==result[key]['max']
        for k in parts:
            vals=[int(r[k]) for r in rows];saved=result['parts'][k]
            assert sum(vals)==saved['timing_ns']['total'] and median(vals)==saved['timing_ns']['median']
            close(sum(vals)/total,saved['share'])
        close(sum(p['share'] for p in result['parts'].values()),1)
        close(result['profiled_ns']['median']/result['original_ns']['median'],result['profiled_to_original_median_ratio'])
        measured+=len(rows)
    assert measured==summary['measured_pairs']==63
    table=[line for line in (BASE/'REPORT.md').read_text().splitlines() if line.startswith('| tau')]
    assert len(table)==3
    for line,result in zip(table,summary['cases']):
        cells=[cell.strip() for cell in line.split('|')[1:-1]]
        assert cells[:2]==[result['case'],str(result['variables'])]
        assert cells[2]==format(result['original_ns']['median']/1e6,'.3f')
        assert cells[3]==format(result['profiled_ns']['median']/1e6,'.3f')
        assert cells[4:]==[format(100*result['parts'][k]['share'],'.2f')+'%' for k in
                          ['curvature_fd_ns','jacobian_ns','eigh_ns','search_ns']]
    verification=dict(passed=True,cases=3,measured_pairs=63,warmup_pairs=9,
        runtime_asserted_matching_pairs=72,independent_saved_state_checks=3,
        independent_time_accounting=True,independent_order_statistics=True,
        BLAS_single_thread_confirmed=True,full_solves=0,returned_points_changed=0)
    if '--check-only' not in sys.argv:
        assert not (BASE/'verification.json').exists()
        (BASE/'verification.json').write_text(json.dumps(verification,indent=2)+'\n')
    print(json.dumps(verification))


if __name__=='__main__':main()
