"""At most eight numerical children; cached routes are certificate readbacks only."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import importlib.metadata
import json
import os
import sys
from time import monotonic
import solve


def main():
    base=solve.CODE
    assert not (base/'execution.json').exists(),'refuse to overwrite execution'
    catalog=json.loads((base/'catalog.json').read_text())
    start=monotonic()
    execution=dict(started_utc=datetime.now(timezone.utc).isoformat(),command=[sys.executable,*sys.argv],
        cwd=os.getcwd(),python=sys.version,workers=8,blas_threads=1,
        affinity=sorted(os.sched_getaffinity(0)),
        packages={key:importlib.metadata.version(key) for key in ['numpy','scipy','casadi']},
        environment={key:os.environ.get(key) for key in ['PYTHONPATH','OPENBLAS_NUM_THREADS',
            'OMP_NUM_THREADS','MKL_NUM_THREADS','PYTHONDONTWRITEBYTECODE']})
    solve.write(base/'execution.json',execution)
    results=[]
    # Launch all eight new G solves first. Each worker launches one child at a time.
    names=catalog['new_G_cases']+[name for name in catalog['cases'] if name not in catalog['new_G_cases']]
    with ThreadPoolExecutor(max_workers=8) as pool:
        jobs={pool.submit(solve.solve_case,name,catalog['cases'][name]):name for name in names}
        for future in as_completed(jobs):
            result=future.result();results.append(result)
            print(json.dumps(dict(case=result['case'],route=result.get('route'),error=result['error'],
                seconds=result['seconds'])),flush=True)
    execution.update(seconds=monotonic()-start,finished_utc=datetime.now(timezone.utc).isoformat(),
        completed=len(results),errors=sum(r['error'] is not None for r in results),
        cached_computation_excluded_from_walltime=True)
    solve.write(base/'execution.json',execution)
    return int(execution['errors']>0)


if __name__=='__main__':sys.exit(main())
