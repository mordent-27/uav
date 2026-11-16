"""R3s entry: r3a-cohort/solve.py with the G stage-13 outer-stall rule (g_case_stall.py), as tested in stall-e2e."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from time import monotonic
import traceback

ENTRY=Path(__file__).resolve().parent
CODE=ENTRY.parent/'2026-11-16-r2h-g-first'
STALL_CODE=ENTRY
ROOT=CODE.parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import g_first_policy


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2)+'\n')


def solve_case(case,entry,out=ENTRY,stall=True):
    assert re.fullmatch(r'fig1|tau[1-9]-seed[0-9]+',case),case
    out=Path(out).resolve();out.relative_to(ROOT)
    destination=out/'runs'/case;destination.mkdir(parents=True,exist_ok=False)
    logs=out/'logs'/case;logs.mkdir(parents=True,exist_ok=False)
    start=monotonic();steps=[]

    def child(script,phase='G',kind='original',extra=None):
        env=os.environ.copy()
        env.update(UAV_R2_CASE=case,UAV_R2H_PHASE=phase,UAV_R2H_OUT=str(out),UAV_R2F_KIND=kind,
            OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1')
        env.pop('UAV_R2F_BASELINE',None)
        for name in ['UAV_R2H_CANONICAL_INPUT','UAV_R2H_G_SOURCE','UAV_R2H_FALLBACK_EVALUATION']:
            env.pop(name,None)
        env.update(extra or {})
        index=len(steps);label=f'{index:02d}-{phase}-{script}'
        command=[sys.executable,str(STALL_CODE/'g_case_stall.py' if stall and script=='g_case' else CODE/(script+'.py'))]
        launch=dict(command=command,cwd=str(ROOT),started_utc=datetime.now(timezone.utc).isoformat(),
            environment={key:value for key,value in env.items() if key.startswith('UAV_') or key in
                ['PYTHONPATH','OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','PYTHONDONTWRITEBYTECODE']})
        write(logs/(label+'-launch.json'),launch)
        t=monotonic()
        with (logs/(label+'.log')).open('w') as stream:
            completed=subprocess.run(command,cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT)
        step=dict(script=script,phase=phase,kind=kind,seconds=monotonic()-t,returncode=completed.returncode)
        steps.append(step);write(destination/'steps.json',steps)
        if completed.returncode:raise RuntimeError(f'{label}: exit {completed.returncode}; see {logs}')

    try:
        canonical=entry.get('canonical_input')
        child('prepare',extra={'UAV_R2H_CANONICAL_INPUT':canonical} if canonical else None)
        g_source=entry.get('g_source')
        reused=bool(g_source)
        if not reused:
            child('g_case')
            g_source=str((out/'cases/G'/case).relative_to(ROOT))
        child('evaluate',extra={'UAV_R2H_G_SOURCE':g_source})
        g=json.loads((out/'evaluations/G'/case/'result.json').read_text())
        cache_used=False

        def fallback():
            nonlocal cache_used
            cached=entry.get('fallback_evaluation')
            if cached:
                cache_used=True
                child('evaluate','fallback',extra={'UAV_R2H_FALLBACK_EVALUATION':cached})
            else:
                child('guard','fallback')
                guard=json.loads((out/'initializations'/case/'guard.json').read_text())
                kind='original'
                if guard['accepted'] and guard['action']!='keep_original':
                    kind='repaired';child('initialize','fallback',kind)
                    accepted=json.loads((out/'initializations'/case/'result.json').read_text())['accepted']
                else:accepted=guard['accepted']
                if accepted:child('fallback_phase','fallback',kind)
                child('evaluate','fallback',kind)
            return json.loads((out/'evaluations/fallback'/case/'result.json').read_text())

        decision=g_first_policy.select(g,fallback)
        outcome=decision['outcome']
        if outcome['physical_point_available']:
            source=out/'evaluations'/decision['route']/case/'selected.json'
            selected=source.read_bytes();assert hashlib.sha256(selected).hexdigest()==outcome['selected_sha256']
            (destination/'selected.json').write_bytes(selected)
        result=dict(case=case,**decision,g_source=g_source,g_reused=reused,fallback_cache_used=cache_used,
            seconds=monotonic()-start,steps=steps,error=None,paper_reproduction=False)
    except Exception:
        result=dict(case=case,error=traceback.format_exc(),seconds=monotonic()-start,steps=steps)
    write(destination/'result.json',result)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case',required=True)
    parser.add_argument('--catalog',type=Path,default=ENTRY/'catalog.json')
    parser.add_argument('--out-root',type=Path,default=ENTRY)
    args=parser.parse_args()
    entries=json.loads(args.catalog.read_text())['cases'] if args.catalog.exists() else {}
    result=solve_case(args.case,entries.get(args.case,{}),args.out_root)
    print(json.dumps(result),flush=True)
    return int(result['error'] is not None)


if __name__=='__main__':sys.exit(main())
