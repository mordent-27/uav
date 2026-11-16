"""Separate-process recheck: every accepted point re-evaluated natively, final Hessian hashes rebuilt, control traces identical."""
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
    case=os.environ['UAV_R2_CASE'];method=os.environ['UAV_HESSIAN_METHOD'];folder=BASE/'inner'/f'{case}-{method}'
    before={p.name:sha(p) for p in folder.iterdir()};targets,row,state,frozen,rule=w.load(case)
    result=json.loads((folder/'result.json').read_text());trace=[json.loads(s) for s in (folder/'trace.jsonl').read_text().splitlines()]
    assert len(trace)==result['accepted']+1;np.testing.assert_array_equal(trace[0]['y'],state['y'])
    for r in trace:
        value,g=frozen.eval(np.array(r['y']));assert value==r['value'] and float(abs(g).max())==r['gradient_inf'],(case,method)
    y=np.array(result['y']);np.testing.assert_array_equal(trace[-1]['y'],y)
    old,_=h.decomposition.hessian_of_al(frozen,y,targets['hessian_step'])
    new,_=w.onesided.hessian_onesided(h.decomposition.hessian_of_al,frozen,y,targets['hessian_step'],None,rule,dict(builds=0,triggered=0,max_coordinates=0))
    assert w.digest(old)==result['final_old_hessian_sha256'] and w.digest(new)==result['final_onesided_hessian_sha256']
    stable,_=frozen.eval(y,stable=True);assert stable==result['stable_al_change']
    frozen.close();assert before=={p.name:sha(p) for p in folder.iterdir()}
    (BASE/'reverification'/f'{case}-{method}.json').write_text(json.dumps(dict(case=case,method=method,points_recomputed=len(trace),
        values_and_gradients_identical=True,final_hessians_identical=True,stable_change_identical=True,outputs_unchanged=True),indent=2)+'\n')


def main():
    import driver
    with driver.guard.protocol_lock():
        targets=driver.guard.read(BASE/'targets.json');driver.check_inputs(targets);(BASE/'reverification').mkdir(exist_ok=False)
        for r in targets['states']:
            for method in targets['methods']:
                env=dict(os.environ,UAV_R2_CASE=r['case'],UAV_HESSIAN_METHOD=method,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1')
                subprocess.run([sys.executable,str(Path(__file__).resolve()),'--one'],env=env,check=True)
        controls={}
        for r in targets['states']:
            # accepted points must match; the wall-clock 'seconds' field of each row is excluded
            a,b=[[{k:v for k,v in json.loads(s).items() if k!='seconds'} for s in (BASE/'inner'/f"{r['case']}-{m}"/'trace.jsonl').read_text().splitlines()]
                for m in targets['methods']]
            controls[r['case']]=dict(role=r['role'],traces_identical=a==b,rows=len(a))
        assert all(v['traces_identical'] for v in controls.values() if v['role']=='control')
        driver.check_inputs(targets);(BASE/'reverification'/'controls.json').write_text(json.dumps(controls,indent=2)+'\n')
        print(json.dumps(dict(solves_rechecked=len(targets['states'])*len(targets['methods']),controls=controls,inputs_unchanged=True)))


if __name__=='__main__':one() if '--one' in sys.argv else main()
