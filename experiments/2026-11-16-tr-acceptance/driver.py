from datetime import datetime,timezone
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from time import monotonic

BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[1]
spec=importlib.util.spec_from_file_location('dense_cg_guard',BASE.parent/'2026-11-16-r3a-cohort/driver.py')
guard=importlib.util.module_from_spec(spec);spec.loader.exec_module(guard)


def main():
    with guard.protocol_lock():
        targets=guard.read(BASE/'targets.json')
        for r in targets['contexts']:
            assert guard.sha(ROOT/r['source'])==r['sha256']
            for name,digest in r['recorded_trials'].items():assert guard.sha(ROOT/name)==digest
        (BASE/'replays').mkdir(exist_ok=False)
        assert 'Ran 34 tests' in (BASE/'python-tests.log').read_text() and (BASE/'python-tests.log').read_text().strip().endswith('OK')
        start=monotonic();runs=[]
        execution=dict(started_utc=datetime.now(timezone.utc).isoformat(),command=[sys.executable,*sys.argv],
            head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
            workers=1,blas_threads=1,python=sys.version,replay_only=True,optimizer_launched=False,outer_solver_launched=False,
            environment={k:os.environ.get(k) for k in ['PYTHONPATH','OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS']})
        guard.write(BASE/'execution.json',execution)
        for row in targets['contexts']:
            case=row['case'];env=dict(os.environ,UAV_R2_CASE=case,
                OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1')
            with (BASE/'replays'/f'{case}.log').open('x') as log:
                run=subprocess.run([sys.executable,str(BASE/'worker.py')],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
            runs.append(dict(case=case,returncode=run.returncode))
        execution.update(finished_utc=datetime.now(timezone.utc).isoformat(),seconds=monotonic()-start,runs=runs)
        guard.write(BASE/'execution.json',execution);print(json.dumps(execution),flush=True)
        assert all(r['returncode']==0 for r in runs)


if __name__=='__main__':main()
