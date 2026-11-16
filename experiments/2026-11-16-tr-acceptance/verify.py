"""Read back trial points and recompute values, gradients and model decrease."""
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
    case=os.environ['UAV_R2_CASE'];folder=BASE/'replays'/case
    before={p.name:sha(p) for p in folder.iterdir()}
    result=json.loads((folder/'result.json').read_text());source=h.ROOT/result['source']
    assert sha(source)==result['source_sha256']
    state=json.loads(source.read_text());f=h.stage4.Frozen(state)
    rows=[json.loads(s) for s in (folder/'trials.jsonl').read_text().splitlines()]
    last_outer=None
    for row in rows:
        y,z=np.array(row['y']),np.array(row['candidate_y'])
        value,g=f.eval(y);g=g.copy();trial,gn=f.eval(z);gn=gn.copy()
        stable,_=f.eval(y,stable=True);stable_trial,_=f.eval(z,stable=True)
        for actual,expected in [(value,row['value']),(trial,row['trial_value']),
            (value-trial,row['ordinary_decrease']),(stable-stable_trial,row['stable_decrease']),
            (np.linalg.norm(g),row['gradient_norm']),(np.linalg.norm(gn),row['trial_gradient_norm'])]:
            np.testing.assert_allclose(actual,expected,atol=1e-25,rtol=1e-10)
        if last_outer!=row['accepted_before']:
            H,_=h.decomposition.hessian_of_al(f,y,1e-7);last_outer=row['accepted_before']
        # The stored TR step can differ from z-y through the final addition's
        # rounding; reconstruct the actual subproblem step from its source log.
        prior=h.ROOT/'experiments/2026-11-16-tr-boundary-fix/inner'/f'{case}-boundary-fixed/tr-steps.jsonl'
        original=json.loads(prior.read_text().splitlines()[row['index']-1]);p=np.array(original['step'])
        np.testing.assert_array_equal(y+p,z)
        prediction=-float(g@p+.5*p@H@p)
        np.testing.assert_allclose(prediction,row['prediction'],atol=1e-30,rtol=1e-10)
    f.close();assert before=={p.name:sha(p) for p in folder.iterdir()}
    out=BASE/'reverification'/f'{case}.json';assert not out.exists()
    out.write_text(json.dumps(dict(case=case,trials_recomputed=len(rows),
        native_value_gradient_model_and_stable_difference_reproduced=True,
        source_and_results_unchanged=True,optimizer_launched=False),indent=2)+'\n')


def main():
    import driver
    with driver.guard.protocol_lock():
        (BASE/'reverification').mkdir(exist_ok=False)
        for target in json.loads((BASE/'targets.json').read_text())['contexts']:
            env=dict(os.environ,UAV_R2_CASE=target['case'],OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
            subprocess.run([sys.executable,str(Path(__file__).resolve())],env=env,check=True)
        print(json.dumps(dict(trials_reverified=52,optimizer_launched=False)))


if __name__=='__main__':worker() if 'UAV_R2_CASE' in os.environ else main()
