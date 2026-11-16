from datetime import datetime,timezone
import json
import os
from pathlib import Path
import subprocess
import sys
from time import monotonic
import driver
from inner_cg import analytic_checks

BASE=Path(__file__).resolve().parent


def main():
    with driver.guard.protocol_lock():
        assert json.loads((BASE/'summary.json').read_text())['states_passing']==4
        (BASE/'inner').mkdir(exist_ok=False)
        checks=analytic_checks()
        (BASE/'inner/analytic-checks.json').write_text(json.dumps(checks,indent=2)+'\n')
        start=monotonic();runs=[]
        execution=dict(started_utc=datetime.now(timezone.utc).isoformat(),
            command=[sys.executable,*sys.argv],head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=driver.ROOT,text=True).strip(),
            workers=1,blas_threads=1,seconds_per_solve=30,max_iterations=300,gradient_inf_tolerance=1e-8,
            frozen_al_only=True,outer_solver_launched=False,analytic_checks_passed=4)
        driver.guard.write(BASE/'inner/execution.json',execution)
        for case in ['tau2-seed2000001','tau6-seed6000002']:
            for method in ['dense','cg']:
                env=dict(os.environ,UAV_R2_CASE=case,UAV_INNER_METHOD=method,
                    OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1')
                with (BASE/'inner'/f'{case}-{method}.log').open('x') as log:
                    run=subprocess.run([sys.executable,str(BASE/'inner_worker.py')],cwd=driver.ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
                runs.append(dict(case=case,method=method,returncode=run.returncode))
        execution.update(finished_utc=datetime.now(timezone.utc).isoformat(),seconds=monotonic()-start,runs=runs)
        driver.guard.write(BASE/'inner/execution.json',execution);print(json.dumps(execution),flush=True)
        assert all(r['returncode']==0 for r in runs)


if __name__=='__main__':main()
