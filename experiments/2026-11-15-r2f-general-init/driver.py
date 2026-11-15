"""Fixed 17 regression inputs and 4 new seeds, at most 8 independent one-thread jobs."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import sys
from time import monotonic

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
REGRESSION=['fig1']+[f'tau{tau}-seed{seed}' for tau in [1,3,5,7] for seed in [0,1,2,3]]
HOLDOUT=[f'tau{tau}-seed{seed}' for tau,seed in [(1,101),(3,103),(5,105),(7,107)]]
CACHED=[HERE.parent/'2026-11-15-r2c-direct-final/cases',HERE.parent/'2026-11-15-r2d-fallback/cases/direct',
        HERE.parent/'2026-11-15-r2e-position-init/cases/original']


def cached(case):
    return next((p/case for p in CACHED if (p/case/'result.json').exists()),None)


def execute(case,script,kind,baseline):
    env=dict(os.environ,UAV_R2_CASE=case,UAV_R2F_KIND=kind,
        OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
    if baseline:env['UAV_R2F_BASELINE']=str(baseline.relative_to(ROOT))
    else:env.pop('UAV_R2F_BASELINE',None)
    start=monotonic()
    with (HERE/'logs'/f'{case}-{kind}-{script}.log').open('w') as log:
        result=subprocess.run([sys.executable,str(HERE/(script+'.py'))],env=env,stdout=log,stderr=subprocess.STDOUT)
    row=dict(script=script,kind=kind,returncode=result.returncode,seconds=monotonic()-start)
    assert result.returncode==0,row
    return row


def job(case):
    start=monotonic();steps=[];baseline=cached(case) if case in REGRESSION else None
    reused=baseline is not None
    try:
        steps.append(execute(case,'guard','original',baseline))
        if baseline is None:
            steps.append(execute(case,'phase','original',None));baseline=HERE/'cases/original'/case
        assert json.loads((baseline/'steps.json').read_text())==dict(run='ok',restore='ok',verify='ok')
        original=json.loads((HERE/'initializations'/case/'original-state.json').read_text())
        assert original['y']==json.loads((baseline/'source.json').read_text())['y']
        guard=json.loads((HERE/'initializations'/case/'guard.json').read_text())
        candidate=None;reason=None
        if guard['accepted'] and guard['action']=='keep_original':candidate=baseline
        elif guard['accepted']:
            steps.append(execute(case,'initialize','repaired',baseline))
            initialization=json.loads((HERE/'initializations'/case/'result.json').read_text())
            if initialization['accepted']:
                steps.append(execute(case,'phase','repaired',baseline));candidate=HERE/'cases/repaired'/case
            else:reason='initialization_not_accepted'
        else:reason='construction_not_accepted'
        row=dict(case=case,group='regression' if case in REGRESSION else 'holdout',
            baseline=str(baseline.relative_to(ROOT)),baseline_reused=reused,
            candidate=None if candidate is None else str(candidate.relative_to(ROOT)),
            candidate_reuses_baseline=candidate==baseline,guard_action=guard['action'],guard_accepted=guard['accepted'],
            reason=reason,steps=steps,seconds=monotonic()-start,error=None)
    except Exception as error:
        row=dict(case=case,steps=steps,seconds=monotonic()-start,error=repr(error))
    (HERE/'jobs'/f'{case}.json').write_text(json.dumps(row,indent=2)+'\n');print(json.dumps(row),flush=True);return row


if __name__=='__main__':
    (HERE/'logs').mkdir(exist_ok=False);(HERE/'jobs').mkdir(exist_ok=False)
    start=monotonic()
    with ThreadPoolExecutor(8) as pool:jobs=list(pool.map(job,REGRESSION+HOLDOUT))
    (HERE/'execution.json').write_text(json.dumps(dict(workers=8,blas_threads=1,affinity_cpus=len(os.sched_getaffinity(0)),
        seconds=monotonic()-start,jobs=jobs),indent=2)+'\n')
    if any(row['error'] for row in jobs):raise SystemExit(1)
