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
spec=importlib.util.spec_from_file_location('reference_guard',BASE.parent/'2026-11-16-r3a-cohort/driver.py')
guard=importlib.util.module_from_spec(spec);spec.loader.exec_module(guard)


def main():
    with guard.protocol_lock():
        targets=guard.read(BASE/'targets.json');verify='--verify' in sys.argv
        for row in targets['contexts']:
            assert guard.sha(ROOT/row['samples'])==row['samples_sha256']
            assert guard.sha(ROOT/row['result'])==row['result_sha256']
        if verify:(BASE/'reverification').mkdir(exist_ok=False)
        else:
            assert (BASE/'tests.log').read_text().strip().endswith('OK')
            (BASE/'cases').mkdir(exist_ok=False)
        start=monotonic();runs=[]
        record=dict(started_utc=datetime.now(timezone.utc).isoformat(),command=[sys.executable,*sys.argv],
            head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
            workers=1,blas_threads=1,optimizer_launched=False,decimal_precisions=targets['precisions'],
            python=sys.version,environment={k:os.environ.get(k) for k in ['PYTHONPATH','OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS']})
        if not verify:guard.write(BASE/'execution.json',record)
        for row in targets['contexts']:
            env=dict(os.environ,UAV_R2_CASE=row['case'],OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1')
            command=[sys.executable,str(BASE/'worker.py')]+(['--verify'] if verify else [])
            log=BASE/('reverification' if verify else 'cases')/(row['case']+'.log')
            with log.open('x') as stream:
                run=subprocess.run(command,cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT)
            runs.append(dict(case=row['case'],returncode=run.returncode))
        record.update(seconds=monotonic()-start,finished_utc=datetime.now(timezone.utc).isoformat(),runs=runs)
        guard.write(BASE/('verification-execution.json' if verify else 'execution.json'),record)
        print(json.dumps(record),flush=True);assert all(r['returncode']==0 for r in runs)


if __name__=='__main__':main()
