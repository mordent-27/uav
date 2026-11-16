"""Separate-process recheck: every outer row's multiplier update, assess metrics and rho rule; final assess; inner-log hashes."""
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import numpy as np

BASE=Path(__file__).resolve().parent


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def one():
    import helpers as h
    import worker as w
    case=os.environ['UAV_R2_CASE'];arm=os.environ['UAV_ARM'];folder=BASE/'stages'/f'{case}-{arm}'
    targets=json.loads((BASE/'targets.json').read_text());row=next(r for r in targets['states'] if r['case']==case)
    initial=json.loads((h.ROOT/row['initial']).read_text());final=json.loads((folder/'result.json').read_text())
    rows=[json.loads(s) for s in gzip.open(folder/'outer.jsonl.gz','rt').read().splitlines()];assert len(rows)==final['completed_outer']
    lam,mu=np.zeros(len(initial['lam'])),np.zeros(len(initial['mu']));previous=np.inf;rho=1e4;tol=targets['stage_tolerance']
    for r in rows:
        assert r['rho']==rho;y=np.array(r['y']);f=w.frozen_for(h.state(y,lam,mu,rho,13));f.eval(y)
        lam=lam+rho*f.m.h;mu=np.maximum(0.,mu+rho*f.m.g)
        np.testing.assert_array_equal(lam,r['lam']);np.testing.assert_array_equal(mu,r['mu'])
        metrics=h.assess(f,y,lam,mu);f.close()
        assert metrics['common_kkt']==r['common_kkt'] and metrics['paper_units_kkt']==r['paper_units_kkt']
        common=max(metrics['common_kkt'].values())<=tol;physical=max(metrics['paper_units_kkt'].values())<=1e-6;passed=common and physical
        violation=max(metrics['common_kkt']['feas'],metrics['common_kkt']['comp'])
        increase=violation>tol and violation>.25*previous and r['inner']['gradient_inf']<=1e-6 and not passed
        assert r['rho_next']==(min(1e8,10*rho) if increase else rho) and r['stage_pass']==passed
        previous,rho=violation,r['rho_next']
    y=np.array(final['y']);np.testing.assert_array_equal(lam,final['lam']);np.testing.assert_array_equal(mu,final['mu']);assert final['rho']==rho
    f=w.frozen_for(h.state(y,lam,mu,rho,13));metrics=h.assess(f,y,lam,mu);f.close()
    assert metrics['common_kkt']==final['common_kkt'] and metrics['paper_units_kkt']==final['paper_units_kkt']
    logs=sorted((BASE/'inner-logs'/f'{case}-{arm}').glob('*.jsonl.gz'))
    (BASE/'reverification'/f'{case}-{arm}.json').write_text(json.dumps(dict(case=case,arm=arm,outer_rows_recomputed=len(rows),
        multiplier_updates_identical=True,metrics_identical=True,rho_rule_identical=True,final_assess_identical=True,
        inner_logs={p.name:sha(p) for p in logs}),indent=2)+'\n')


def main():
    import driver
    with driver.guard.protocol_lock():
        targets=driver.guard.read(BASE/'targets.json');driver.check_inputs(targets);(BASE/'reverification').mkdir(exist_ok=False)
        before={str(p.relative_to(BASE)):sha(p) for p in (BASE/'stages').rglob('*') if p.is_file()}
        for r in targets['states']:
            for arm in targets['arms']:
                env=dict(os.environ,UAV_R2_CASE=r['case'],UAV_ARM=arm,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1')
                subprocess.run([sys.executable,str(Path(__file__).resolve()),'--one'],env=env,check=True)
        assert before=={str(p.relative_to(BASE)):sha(p) for p in (BASE/'stages').rglob('*') if p.is_file()}
        manifest={}
        for p in sorted((BASE/'reverification').glob('tau*.json')):
            d=json.loads(p.read_text());manifest[f"{d['case']}-{d['arm']}"]=d['inner_logs']
        (BASE/'local-inner-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
        driver.check_inputs(targets);print(json.dumps(dict(stages_rechecked=len(targets['states'])*len(targets['arms']),outputs_unchanged=True)))


if __name__=='__main__':one() if '--one' in sys.argv else main()
