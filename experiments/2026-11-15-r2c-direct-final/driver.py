"""Six independent one-thread processes; never exceed the user limit of 8 cores."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import sys
from time import monotonic

HERE = Path(__file__).resolve().parent
CASES = ['tau1-seed2', 'tau5-seed0', 'tau7-seed0', 'tau7-seed1', 'tau1-seed0', 'fig1']


def run(case):
    assert not (HERE/'cases'/case).exists(), 'refuse to overwrite'
    env = dict(os.environ, UAV_R2_CASE=case, OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1')
    env.pop('UAV_R2_OUT', None)
    start = monotonic()
    with (HERE/'logs'/(case+'.log')).open('w') as log:
        result = subprocess.run([sys.executable, str(HERE/'case.py')], env=env, stdout=log, stderr=subprocess.STDOUT)
    row = dict(case=case, returncode=result.returncode, seconds=monotonic()-start)
    print(json.dumps(row), flush=True)
    return row


if __name__ == '__main__':
    (HERE/'logs').mkdir(exist_ok=False)
    start = monotonic()
    with ThreadPoolExecutor(6) as pool:
        results = list(pool.map(run, CASES))
    (HERE/'execution.json').write_text(json.dumps(dict(workers=6, blas_threads=1,
        affinity_cpus=len(os.sched_getaffinity(0)), seconds=monotonic()-start, cases=results), indent=2)+'\n')
