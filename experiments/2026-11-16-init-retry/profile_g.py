"""Fixed-point component microbenchmarks; no Newton or AL iteration."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from time import perf_counter

BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[1]
CONTEXTS=[(case,stage) for case in ['tau2-seed2000001','tau6-seed6000002'] for stage in [1,13]]


def worker():
    import numpy as np
    import helpers as h
    case=os.environ['UAV_R2_CASE'];stage=int(os.environ['UAV_PROFILE_STAGE'])
    source=ROOT/'experiments/2026-11-16-r3a-cohort/cases/G'/case/'stages'/f'stage{stage:02d}'/'initial.json'
    raw=source.read_bytes();state=json.loads(raw);f=h.stage4.Frozen(state);y=np.array(state['y'])
    measured=f.m.metrics(y,np.array(state['lam']),np.array(state['mu']))
    for key in ['common_kkt','paper_units_kkt']:
        np.testing.assert_allclose(list(measured[key].values()),list(state[key].values()),atol=1e-9,rtol=1e-8)
    def one():
        t=perf_counter();_,g=f.eval(y);g=g.copy();scalar=perf_counter()-t
        times=dict(eval=0.,jacobian=0.);original_eval,original_jac=f.m.eval,f.m.jacobian
        def ev(*args):
            t=perf_counter();v=original_eval(*args);times['eval']+=perf_counter()-t;return v
        def jac(*args):
            t=perf_counter();v=original_jac(*args);times['jacobian']+=perf_counter()-t;return v
        f.m.eval,f.m.jacobian=ev,jac
        counts=dict(gradient_calls=0,jacobian_calls=0)
        try:
            t=perf_counter();H,skew=h.decomposition.hessian_of_al(f,y,1e-7,counts);total=perf_counter()-t
        finally:f.m.eval,f.m.jacobian=original_eval,original_jac
        t=perf_counter();w,V=np.linalg.eigh(H);eigen=perf_counter()-t
        t=perf_counter();step,_=h.stage4.old.newton.tr_step(w,V,g,1.);trust=perf_counter()-t
        t=perf_counter();value,gradient=f.eval(y+step);trial=perf_counter()-t
        assert np.isfinite(value) and np.isfinite(gradient).all()
        return H,dict(scalar_seconds=scalar,hessian_seconds=total,hessian_eval_seconds=times['eval'],
            hessian_constraint_jacobian_seconds=times['jacobian'],hessian_other_seconds=total-times['eval']-times['jacobian'],
            eigen_seconds=eigen,trust_step_seconds=trust,trial_seconds=trial,counters=counts,max_asymmetry=skew)
    reference,_=one();rows=[]
    for _ in range(5):
        H,r=one();np.testing.assert_allclose(H,reference,atol=1e-9,rtol=1e-9);rows.append(r)
    f.close();assert source.read_bytes()==raw
    medians={key:float(np.median([r[key] for r in rows])) for key in rows[0] if key not in ['counters','max_asymmetry']}
    result=dict(case=case,stage=stage,variables=len(y),source=str(source.relative_to(ROOT)),
        source_sha256=hashlib.sha256(raw).hexdigest(),source_unchanged=True,kkt_reproduced=True,
        warmup=1,repetitions=5,blas_threads=1,rows=rows,medians=medians,optimizer_launched=False)
    out=BASE/'profile'/f'{case}-stage{stage:02d}.json';assert not out.exists()
    out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(case=case,stage=stage,variables=len(y),medians=medians)))


def main():
    import driver
    with driver.guard.protocol_lock():
        (BASE/'profile').mkdir(exist_ok=False)
        for case,stage in CONTEXTS:
            env=dict(os.environ,UAV_R2_CASE=case,UAV_PROFILE_STAGE=str(stage),OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
            with (BASE/'profile'/f'{case}-{stage}.log').open('x') as log:
                subprocess.run([sys.executable,str(Path(__file__).resolve())],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,check=True)


if __name__=='__main__':worker() if 'UAV_PROFILE_STAGE' in os.environ else main()
