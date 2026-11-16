"""Re-evaluate all saved inner inputs, accepted iterates and final gradients."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import numpy as np

BASE=Path(__file__).resolve().parent


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def worker():
    import helpers as h
    case=os.environ['UAV_R2_CASE'];method=os.environ['UAV_INNER_METHOD']
    folder=BASE/'inner'/f'{case}-{method}';before={p.name:sha(p) for p in folder.iterdir()}
    result=json.loads((folder/'result.json').read_text());source=h.ROOT/result['source']
    assert sha(source)==result['source_sha256']
    state=json.loads(source.read_text());f=h.stage4.Frozen(state)
    trace=[json.loads(line) for line in (folder/'trace.jsonl').read_text().splitlines()]
    assert len(trace)==result['accepted']+1
    np.testing.assert_array_equal(trace[0]['y'],state['y'])
    errors=[]
    for row in trace:
        value,gradient=f.eval(np.array(row['y']))
        np.testing.assert_allclose(value,row['value'],atol=1e-10,rtol=1e-12)
        np.testing.assert_allclose(max(abs(gradient)),row['gradient_inf'],atol=1e-10,rtol=1e-9)
        errors.append(abs(float(value)-row['value']))
    np.testing.assert_array_equal(trace[-1]['y'],result['y'])
    value,gradient=f.eval(np.array(result['y']))
    np.testing.assert_allclose(gradient,result['gradient'],atol=1e-10,rtol=1e-9)
    np.testing.assert_allclose(trace[0]['value'],result['initial_value'],atol=1e-12)
    np.testing.assert_allclose(trace[0]['gradient_inf'],result['initial_gradient_inf'],atol=1e-12)
    np.testing.assert_allclose(result['al_decrease'],result['initial_value']-value,atol=1e-12)
    # Reconstruct the shared initial matrix and the two initial TR steps.
    initial=np.array(state['y']);H,_=h.decomposition.hessian_of_al(f,initial,1e-7)
    _,g=f.eval(initial);g=g.copy()
    with np.load(folder/'first-step.npz') as data:
        np.testing.assert_allclose(H,data['H'],atol=1e-9,rtol=1e-9)
        np.testing.assert_allclose(g,data['g'],atol=1e-10,rtol=1e-9)
        w,V=np.linalg.eigh(H);p,_=h.stage4.old.newton.tr_step(w,V,g,1.)
        np.testing.assert_allclose(p,data['old_step'],atol=1e-10,rtol=1e-9)
        from inner_cg import cg_step
        p,_,_,_=cg_step(lambda v:H@v,g,1.)
        np.testing.assert_allclose(p,data['cg_step'],atol=1e-10,rtol=1e-9)
    f.close();assert before=={p.name:sha(p) for p in folder.iterdir()}
    out=BASE/'inner-reverification'/f'{case}-{method}.json'
    assert not out.exists()
    out.write_text(json.dumps(dict(case=case,method=method,points_recomputed=len(trace),
        max_value_error=max(errors),final_gradient_reproduced=True,source_and_outputs_unchanged=True),indent=2)+'\n')


def main():
    import driver
    with driver.guard.protocol_lock():
        (BASE/'inner-reverification').mkdir(exist_ok=False)
        for case in ['tau2-seed2000001','tau6-seed6000002']:
            for method in ['dense-cg']:
                env=dict(os.environ,UAV_R2_CASE=case,UAV_INNER_METHOD=method,
                    OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
                subprocess.run([sys.executable,str(Path(__file__).resolve())],env=env,check=True)
        print(json.dumps(dict(solves_rechecked=2,source_and_trace_unchanged=True)))


if __name__=='__main__':worker() if 'UAV_INNER_METHOD' in os.environ else main()
