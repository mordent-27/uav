"""Separate-process recheck of the 12 solves: accepted points, Decimal decreases, final Decimal gradients, stop thresholds, A0 vs earlier run."""
from decimal import localcontext
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import numpy as np

BASE=Path(__file__).resolve().parent


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def strip(rows):return [{k:v for k,v in r.items() if k!='seconds'} for r in rows]


def one():
    import helpers as h
    import worker as w
    import loop
    case=os.environ['UAV_R2_CASE'];arm=os.environ['UAV_ARM'];folder=BASE/'inner'/f'{case}-{arm}';before={p.name:sha(p) for p in folder.iterdir()}
    targets,row,state,frozen,metadata,exact,decimal_gradient=w.setup(case)
    result=json.loads((folder/'result.json').read_text());trace=[json.loads(s) for s in (folder/'trace.jsonl').read_text().splitlines()]
    assert len(trace)==result['accepted']+1;np.testing.assert_array_equal(trace[0]['y'],state['y'])
    for r in trace:
        v,g=frozen.eval(np.array(r['y']));assert v==r['value'] and float(abs(g).max())==r['gradient_inf']
    if arm[0]=='B':
        for prev,r in zip(trace,trace[1:]):
            with localcontext() as c:
                c.prec=targets['digits'];assert float(exact(np.array(prev['y']))-exact(np.array(r['y'])))==r['decimal_decrease']
    y=np.array(result['y'])
    if result['status']=='converged_floor':
        H=h.decomposition.hessian_of_al(frozen,y,targets['hessian_step'])[0]
        assert loop.floor_threshold(H,y,targets['tolerance'],targets['floor_factor'])==result['stop']['threshold'] and result['gradient_inf']<=result['stop']['threshold']
    g100=decimal_gradient(y,targets['reference_digits'],targets['reference_step']);diff=abs(float(abs(g100).max())-result['decimal_gradient_inf'])
    assert diff<=targets['gradient_agreement_inf']
    frozen.close();assert before=={p.name:sha(p) for p in folder.iterdir()}
    (BASE/'reverification'/f'{case}-{arm}.json').write_text(json.dumps(dict(case=case,arm=arm,points_recomputed=len(trace),
        decimal_decreases_identical=arm[0]=='B',decimal_gradient_inf_100=float(abs(g100).max()),difference_from_80=diff,outputs_unchanged=True),indent=2)+'\n')


def main():
    import driver
    with driver.guard.protocol_lock():
        targets=driver.guard.read(BASE/'targets.json');driver.check_inputs(targets);(BASE/'reverification').mkdir(exist_ok=False)
        for r in targets['states']:
            for arm in targets['arms']:
                env=dict(os.environ,UAV_R2_CASE=r['case'],UAV_ARM=arm,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1')
                subprocess.run([sys.executable,str(Path(__file__).resolve()),'--one'],env=env,check=True)
        previous={}
        for r in targets['states']:
            old=BASE.parents[1]/targets['previous_a0']['case_dir']/f"{r['case']}-{targets['previous_a0']['method']}"/'trace.jsonl'
            if old.exists():
                a=strip([json.loads(s) for s in old.read_text().splitlines()]);b=strip([json.loads(s) for s in (BASE/'inner'/f"{r['case']}-A0"/'trace.jsonl').read_text().splitlines()])
                previous[r['case']]=dict(identical_to_switch_onesided_old=a==b,rows=len(b));assert a==b,r['case']
        driver.check_inputs(targets);(BASE/'reverification'/'previous-a0.json').write_text(json.dumps(previous,indent=2)+'\n')
        print(json.dumps(dict(solves_rechecked=len(targets['states'])*len(targets['arms']),previous_a0=previous,inputs_unchanged=True)))


if __name__=='__main__':one() if '--one' in sys.argv else main()
