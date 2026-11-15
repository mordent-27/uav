"""Five independent policy jobs; each phase uses only one BLAS/OpenMP thread."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import sys
from time import monotonic

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
JOBS = [('tau5-seed1', 'regression')] + [(f'tau{tau}-seed3', 'diagnostic_holdout') for tau in [1, 3, 5, 7]]


def accepted(folder):
    result = folder/'restored/result.json'
    return result.exists() and json.loads(result.read_text())['accepted']


def phase(case, name):
    folder = HERE/'cases'/name/case
    assert not folder.exists(), 'refuse to overwrite a phase'
    env = dict(os.environ, UAV_R2_CASE=case, UAV_R2D_PHASE=name,
        OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1')
    start = monotonic()
    with (HERE/'logs'/f'{case}-{name}.log').open('w') as log:
        result = subprocess.run([sys.executable, str(HERE/'phase.py')], env=env,
            stdout=log, stderr=subprocess.STDOUT)
    info = dict(phase=name, path=str(folder.relative_to(ROOT)), returncode=result.returncode,
        wall_seconds=monotonic()-start)
    assert result.returncode == 0, info
    assert json.loads((folder/'steps.json').read_text()) == dict(run='ok', restore='ok', verify='ok')
    return info


def job(item):
    case, group = item
    start = monotonic()
    attempts = []
    try:
        if group == 'diagnostic_holdout':
            attempts.append(phase(case, 'G'))
            gfolder = ROOT/attempts[-1]['path']
        else:
            gfolder = HERE.parent/'2026-11-15-r2b-coarse/cases/G'/case
        if accepted(gfolder):
            selected = dict(phase='G', path=str(gfolder.relative_to(ROOT)))
        else:
            attempts.append(phase(case, 'direct'))
            folder = ROOT/attempts[-1]['path']
            selected = dict(phase='direct', path=str(folder.relative_to(ROOT))) if accepted(folder) else None
        row = dict(case=case, group=group, attempts=attempts, selected=selected,
            accepted=selected is not None, seconds=monotonic()-start, error=None)
    except Exception as error:
        row = dict(case=case, group=group, attempts=attempts, selected=None,
            accepted=False, seconds=monotonic()-start, error=repr(error))
    (HERE/'jobs'/f'{case}.json').write_text(json.dumps(row, indent=2)+'\n')
    print(json.dumps(row), flush=True)
    return row


if __name__ == '__main__':
    (HERE/'logs').mkdir(exist_ok=False)
    (HERE/'jobs').mkdir(exist_ok=False)
    start = monotonic()
    with ThreadPoolExecutor(5) as pool:
        results = list(pool.map(job, JOBS))
    (HERE/'execution.json').write_text(json.dumps(dict(workers=5, blas_threads=1,
        affinity_cpus=len(os.sched_getaffinity(0)), seconds=monotonic()-start, jobs=results), indent=2)+'\n')
    if any(row['error'] for row in results):
        raise SystemExit(1)
