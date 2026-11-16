from datetime import datetime,timezone
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from time import monotonic

BASE=Path(__file__).resolve().parent;ROOT=BASE.parents[1]
spec=importlib.util.spec_from_file_location('precise_inner_guard',BASE.parent/'2026-11-16-r3a-cohort/driver.py')
guard=importlib.util.module_from_spec(spec);spec.loader.exec_module(guard)


def main():
    with guard.protocol_lock():
        targets=guard.read(BASE/'targets.json');assert guard.sha(ROOT/targets['full_precision_tasks'])==targets['full_precision_tasks_sha256']
        for row in targets['contexts']:
            for name in ['samples','result','metadata']:assert guard.sha(ROOT/row[name if name!='metadata' else 'metadata_source'])==row[name+'_sha256']
        assert 'Ran 19 tests' in (BASE/'tests.log').read_text() and (BASE/'tests.log').read_text().strip().endswith('OK')
        (BASE/'gradient-checks').mkdir(exist_ok=False);(BASE/'logs').mkdir(exist_ok=False)
        start=monotonic();runs=[]
        execution=dict(started_utc=datetime.now(timezone.utc).isoformat(),head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
            command=[sys.executable,*sys.argv],workers=1,blas_threads=1,seconds_per_inner=30,max_iterations=300,gradient_inf_tolerance=1e-8,
            python=sys.version,outer_solver_launched=False,environment={k:os.environ.get(k) for k in ['PYTHONPATH','OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS']})
        guard.write(BASE/'execution.json',execution)
        def run(case,method=None):
            env=dict(os.environ,UAV_R2_CASE=case,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1')
            if method:env['UAV_INNER_METHOD']=method
            args=[] if method else ['--check-gradient'];name=f"{case}-{method or 'gradient'}"
            with (BASE/'logs'/f'{name}.log').open('x') as log:
                process=subprocess.run([sys.executable,str(BASE/'worker.py'),*args],env=env,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
            runs.append(dict(case=case,method=method or 'gradient',returncode=process.returncode));return process.returncode==0
        checks=[run(row['case']) for row in targets['contexts']]
        passed=all(checks) and all(guard.read(BASE/'gradient-checks'/f"{row['case']}.json")['passed'] for row in targets['contexts'])
        if passed:
            (BASE/'inner').mkdir(exist_ok=False)
            for row in targets['contexts']:
                for method in targets['inner']['methods']:run(row['case'],method)
        execution.update(finished_utc=datetime.now(timezone.utc).isoformat(),seconds=monotonic()-start,runs=runs,
            gradient_gate_passed=passed,optimizer_launched=passed,inner_solves=4 if passed else 0)
        guard.write(BASE/'execution.json',execution);print(json.dumps(execution),flush=True)
        assert all(r['returncode']==0 for r in runs)


if __name__=='__main__':main()
