from datetime import datetime,timezone
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from time import monotonic

BASE=Path(__file__).resolve().parent;ROOT=BASE.parents[1]
spec=importlib.util.spec_from_file_location('kink_sides_guard',BASE.parent/'2026-11-16-r3a-cohort/driver.py')
guard=importlib.util.module_from_spec(spec);spec.loader.exec_module(guard)


def check_inputs(targets):
    assert guard.sha(ROOT/targets['full_precision_tasks'])==targets['full_precision_tasks_sha256']
    for name,digest in targets['reused_modules'].items():assert guard.sha(ROOT/name)==digest,name
    c=targets['side']['context']
    for key,digest in [('samples','samples_sha256'),('result','result_sha256'),('metadata_source','metadata_sha256')]:
        assert guard.sha(ROOT/c[key])==c[digest],key
    for r in targets['floors']['states']:
        assert guard.sha(ROOT/r['checkpoint'])==r['checkpoint_sha256'] and guard.sha(ROOT/r['result'])==r['result_sha256'],r['case']


def run(script,case,log,runs):
    env=dict(os.environ,UAV_R2_CASE=case,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1')
    began=monotonic()
    with log.open('x') as out:
        process=subprocess.run([sys.executable,str(BASE/script)],env=env,cwd=ROOT,stdout=out,stderr=subprocess.STDOUT)
    runs.append(dict(script=script,case=case,returncode=process.returncode,seconds=monotonic()-began))


def main():
    with guard.protocol_lock():
        targets=guard.read(BASE/'targets.json');check_inputs(targets)
        tests=(BASE/'tests.log').read_text();assert 'Ran 7 tests' in tests and tests.strip().endswith('OK')
        for name in ['side','floors','logs']:(BASE/name).mkdir(exist_ok=False)
        start=monotonic();runs=[]
        execution=dict(started_utc=datetime.now(timezone.utc).isoformat(),
            head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
            command=[sys.executable,*sys.argv],workers=1,blas_threads=1,python=sys.version,optimizer_launched=False,outer_solver_launched=False,
            environment={k:os.environ.get(k) for k in ['PYTHONPATH','OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS']})
        guard.write(BASE/'execution.json',execution)
        run('worker_side.py',targets['side']['context']['case'],BASE/'logs'/'side.log',runs)
        floor_start=monotonic();skipped=[]
        for r in targets['floors']['states']:
            if monotonic()-floor_start>=targets['floors']['seconds']:skipped.append(r['case']);continue
            run('worker_floor.py',r['case'],BASE/'logs'/f"floor-{r['case']}.log",runs)
        execution.update(finished_utc=datetime.now(timezone.utc).isoformat(),seconds=monotonic()-start,
            floor_seconds=monotonic()-floor_start,floor_skipped=skipped,runs=runs)
        guard.write(BASE/'execution.json',execution);print(json.dumps(execution),flush=True)
        assert all(r['returncode']==0 for r in runs)


if __name__=='__main__':main()
