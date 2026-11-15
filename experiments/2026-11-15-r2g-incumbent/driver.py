"""Replay 21 fixed cases and run the screened negative-battery cohort, at most 8 processes."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import sys
from time import monotonic

HERE=Path(__file__).resolve().parent
R2F=HERE.parent/'2026-11-15-r2f-general-init'


def execute(case,script,kind):
    env=dict(os.environ,UAV_R2_CASE=case,UAV_R2F_KIND=kind,
        OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
    env.pop('UAV_R2F_BASELINE',None)
    start=monotonic()
    with (HERE/'logs'/f'{case}-{kind}-{script}.log').open('w') as log:
        run=subprocess.run([sys.executable,str(HERE/(script+'.py'))],env=env,stdout=log,stderr=subprocess.STDOUT)
    row=dict(script=script,kind=kind,returncode=run.returncode,seconds=monotonic()-start)
    assert run.returncode==0,row
    return row


def job(item):
    case,group=item;start=monotonic();steps=[]
    try:
        if group=='regression':steps.append(execute(case,'replay','original'))
        else:
            steps.append(execute(case,'guard','original'))
            steps.append(execute(case,'phase','original'))
            guard=json.loads((HERE/'initializations'/case/'guard.json').read_text())
            completed=False
            if guard['accepted']:
                assert guard['action']=='repair','selected negative-battery input must require repair'
                steps.append(execute(case,'initialize','repaired'))
                initialization=json.loads((HERE/'initializations'/case/'result.json').read_text())
                if initialization['accepted']:
                    steps.append(execute(case,'phase','repaired'));completed=True
            if not completed:steps.append(execute(case,'missing','repaired'))
        row=dict(case=case,group=group,steps=steps,seconds=monotonic()-start,error=None)
    except Exception as error:row=dict(case=case,group=group,steps=steps,seconds=monotonic()-start,error=repr(error))
    (HERE/'jobs'/f'{case}.json').write_text(json.dumps(row,indent=2)+'\n');print(json.dumps(row),flush=True);return row


if __name__=='__main__':
    screening=json.loads((HERE/'screening.json').read_text())
    regression=json.loads((R2F/'summary.json').read_text())
    jobs=[(case,'negative_holdout') for case in screening['selected']]+[(r['case'],'regression') for r in regression['cases']]
    (HERE/'logs').mkdir(exist_ok=False);(HERE/'jobs').mkdir(exist_ok=False)
    start=monotonic()
    with ThreadPoolExecutor(8) as pool:results=list(pool.map(job,jobs))
    (HERE/'execution.json').write_text(json.dumps(dict(workers=8,blas_threads=1,affinity_cpus=len(os.sched_getaffinity(0)),
        seconds=monotonic()-start,jobs=results),indent=2)+'\n')
    if any(row['error'] for row in results):raise SystemExit(1)
