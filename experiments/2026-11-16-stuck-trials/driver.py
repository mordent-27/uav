from datetime import datetime,timezone
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from time import monotonic

BASE=Path(__file__).resolve().parent;ROOT=BASE.parents[1]
spec=importlib.util.spec_from_file_location('stuck_trials_guard',BASE.parent/'2026-11-16-r3a-cohort/driver.py')
guard=importlib.util.module_from_spec(spec);spec.loader.exec_module(guard)


def check_inputs(targets):
    for name,digest in targets['reused_modules'].items():assert guard.sha(ROOT/name)==digest,name
    for t in targets['targets']:
        for key in ['checkpoint','result','trace']:assert guard.sha(ROOT/t[key])==t[key+'_sha256'],(t['name'],key)


def main():
    with guard.protocol_lock():
        targets=guard.read(BASE/'targets.json');check_inputs(targets)
        tests=(BASE/'tests.log').read_text();assert 'Ran 4 tests' in tests and tests.strip().endswith('OK')
        (BASE/'logs').mkdir(exist_ok=False);(BASE/'replays').mkdir(exist_ok=False);start=monotonic();runs=[]
        execution=dict(started_utc=datetime.now(timezone.utc).isoformat(),head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
            command=[sys.executable,*sys.argv],workers=1,blas_threads=1,python=sys.version,optimizer_launched=False,
            environment={k:os.environ.get(k) for k in ['PYTHONPATH','OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS']})
        guard.write(BASE/'execution.json',execution)
        for t in targets['targets']:
            env=dict(os.environ,UAV_R2_CASE=t['case'],UAV_STUCK_TARGET=t['name'],OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1')
            began=monotonic()
            with (BASE/'logs'/f"{t['name']}.log").open('x') as log:
                p=subprocess.run([sys.executable,str(BASE/'worker.py')],env=env,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
            runs.append(dict(name=t['name'],returncode=p.returncode,seconds=monotonic()-began))
        execution.update(finished_utc=datetime.now(timezone.utc).isoformat(),seconds=monotonic()-start,runs=runs)
        guard.write(BASE/'execution.json',execution);print(json.dumps(execution),flush=True)
        assert all(r['returncode']==0 for r in runs)


if __name__=='__main__':main()
