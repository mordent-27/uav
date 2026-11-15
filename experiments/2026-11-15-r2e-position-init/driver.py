"""Four case jobs; baseline, initialization and repaired solve stay sequential per case."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import sys
from time import monotonic

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
CASES=[f'tau{tau}-seed3' for tau in [1,3,5,7]]


def execute(case,kind,script):
    env=dict(os.environ,UAV_R2_CASE=case,UAV_R2E_KIND=kind,
        OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
    start=monotonic()
    with (HERE/'logs'/f'{case}-{kind}-{script}.log').open('w') as log:
        answer=subprocess.run([sys.executable,str(HERE/(script+'.py'))],env=env,stdout=log,stderr=subprocess.STDOUT)
    row=dict(kind=kind,script=script,seconds=monotonic()-start,returncode=answer.returncode)
    assert answer.returncode==0,row
    return row


def job(case):
    start=monotonic();steps=[]
    try:
        if case in ['tau1-seed3','tau3-seed3']:
            steps.append(execute(case,'original','phase'))
        steps.append(execute(case,'repaired','initialize'))
        initialization=json.loads((HERE/'initializations'/case/'result.json').read_text())
        if initialization['accepted']:
            steps.append(execute(case,'repaired','phase'))
        row=dict(case=case,steps=steps,seconds=monotonic()-start,error=None,
            initialization_accepted=initialization['accepted'])
    except Exception as error:
        row=dict(case=case,steps=steps,seconds=monotonic()-start,error=repr(error))
    (HERE/'jobs'/f'{case}.json').write_text(json.dumps(row,indent=2)+'\n')
    print(json.dumps(row),flush=True)
    return row


if __name__=='__main__':
    (HERE/'logs').mkdir(exist_ok=False);(HERE/'jobs').mkdir(exist_ok=False)
    start=monotonic()
    with ThreadPoolExecutor(4) as pool:
        jobs=list(pool.map(job,CASES))
    (HERE/'execution.json').write_text(json.dumps(dict(workers=4,blas_threads=1,
        affinity_cpus=len(os.sched_getaffinity(0)),seconds=monotonic()-start,jobs=jobs),indent=2)+'\n')
    if any(row['error'] for row in jobs):raise SystemExit(1)
