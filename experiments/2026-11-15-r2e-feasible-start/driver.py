"""One additional initial-point comparison; initialization and final solve are sequential."""
import json
import os
from pathlib import Path
import subprocess
import sys
from time import monotonic

HERE=Path(__file__).resolve().parent
if __name__=='__main__':
    (HERE/'logs').mkdir(exist_ok=False)
    env=dict(os.environ,UAV_R2_CASE='tau7-seed3',UAV_R2E_KIND='repaired',
        OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
    start=monotonic();steps=[]
    for script in ['initialize','phase']:
        step_start=monotonic()
        with (HERE/'logs'/(script+'.log')).open('w') as log:
            answer=subprocess.run([sys.executable,str(HERE/(script+'.py'))],env=env,stdout=log,stderr=subprocess.STDOUT)
        steps.append(dict(script=script,returncode=answer.returncode,seconds=monotonic()-step_start))
        if answer.returncode!=0:break
        if script=='initialize' and not json.loads((HERE/'initializations/tau7-seed3/result.json').read_text())['accepted']:break
    (HERE/'execution.json').write_text(json.dumps(dict(workers=1,blas_threads=1,seconds=monotonic()-start,steps=steps),indent=2)+'\n')
    if any(row['returncode']!=0 for row in steps):raise SystemExit(1)
