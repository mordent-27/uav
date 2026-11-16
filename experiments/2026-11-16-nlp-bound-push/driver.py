from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from time import monotonic

BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[1]
spec=importlib.util.spec_from_file_location('cohort_guard',BASE.parent/'2026-11-16-r3a-cohort/driver.py')
guard=importlib.util.module_from_spec(spec);spec.loader.exec_module(guard)


def main():
    with guard.protocol_lock():
        assert not (BASE/'execution.json').exists()
        targets=guard.read(BASE/'targets.json');assert not (ROOT/'ipopt.opt').exists()
        for entry in targets['cases'].values():
            for p,digest in entry['hashes'].items():assert guard.sha(ROOT/p)==digest
        start=monotonic();(BASE/'logs').mkdir()
        execution=dict(started_utc=datetime.now(timezone.utc).isoformat(),command=[sys.executable,*sys.argv],
            head=subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,text=True,stdout=subprocess.PIPE,check=True).stdout.strip(),
            python=sys.version,packages={p:importlib.metadata.version(p) for p in ['numpy','scipy','casadi']},workers=8,blas_threads=1,
            environment={k:os.environ.get(k) for k in ['PYTHONPATH','OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS']})
        guard.write(BASE/'execution.json',execution)
        def launch(item):
            case,arm=item;env=dict(os.environ,UAV_DIAG_CASE=case,UAV_DIAG_ARM=arm,UAV_R2_CASE='fig1',
                OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1')
            with (BASE/'logs'/f'{case}-{arm}.log').open('x') as log:
                run=subprocess.run([sys.executable,str(BASE/'run.py')],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
            return dict(case=case,arm=arm,returncode=run.returncode)
        jobs=[(case,arm) for case in targets['cases'] for arm in ['baseline','small_push']]
        with ThreadPoolExecutor(8) as pool:runs=list(pool.map(launch,jobs))
        execution.update(finished_utc=datetime.now(timezone.utc).isoformat(),seconds=monotonic()-start,runs=runs)
        guard.write(BASE/'execution.json',execution);print(json.dumps(execution),flush=True)
        assert all(r['returncode']==0 for r in runs)


if __name__=='__main__':main()
