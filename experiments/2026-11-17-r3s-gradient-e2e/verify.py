import csv
import hashlib
import json
from pathlib import Path
import sys

BASE=Path(__file__).resolve().parent;ROOT=BASE.parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from repair_initialization import audit


def read(p):return json.loads(p.read_text())


def main():
    for index,root in [('source-index.json',ROOT),('artifact-index.json',BASE)]:
        path=BASE/index
        if path.exists():
            for name,digest in read(path).items():assert hashlib.sha256((root/name).read_bytes()).hexdigest()==digest,name
    summary=read(BASE/'summary.json');targets=read(BASE/'targets.json')
    assert len(summary['rows'])==8 and summary['software_errors']==0
    assert {r['case'] for r in summary['rows']}==set(targets['cases'])
    points=0
    for r in summary['rows']:
        base=BASE/r['mode'];case=r['case'];raw=read(base/'runs'/case/'result.json')
        assert raw['error'] is None and not raw['g_reused'] and not raw['fallback_cache_used']
        outcome=raw['outcome'];g=read(base/'cases/G'/case/'result.json')
        verification=read(base/'cases/G'/case/'verification.json')
        assert verification['original_jacobian_stationarity_verified']
        common=g['stage']==13 and max(g['common_kkt'].values())<=1e-6
        both=common and max(g['paper_units_kkt'].values())<=1e-6
        assert common==g['final_common_pass']==r['G_common']
        assert both==g['final_both_scales_pass']==r['G_physical']
        assert r['G_stage']==g['stage'] and r['G_stop']==g['stop']
        assert r['route']==raw['route'] and r['certificate']==outcome['selected_same_final_branch_kkt']
        if outcome['physical_point_available']:
            path=base/'runs'/case/'selected.json';data=read(path)
            assert hashlib.sha256(path.read_bytes()).hexdigest()==outcome['selected_sha256']
            assert audit(data)['accepted'] and r['physical_audit']
            assert abs(sum(data['solution']['s'])-r['returned_h'])<1e-12;points+=1
    with (BASE/'cases.csv').open() as stream:csv_rows=list(csv.DictReader(stream))
    assert len(csv_rows)==8
    for r in csv_rows:
        saved=next(x for x in summary['rows'] if x['case']==r['case'] and x['mode']==r['mode'])
        assert float(r['returned_h'])==saved['returned_h']
    result=dict(passed=True,new_full_runs=8,software_errors=0,physical_returned=points,
        G_verifiers_passed=8,source_hashes_verified=True,new_KKT_recalculation_by_this_verifier=False)
    if '--check-only' not in sys.argv:
        assert not (BASE/'verification.json').exists()
        (BASE/'verification.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))


if __name__=='__main__':main()
