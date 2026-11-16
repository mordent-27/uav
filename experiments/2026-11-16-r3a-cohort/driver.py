"""Run one frozen batch, at most eight fresh solves; never repeat a failed/interrupted input."""
import argparse
from concurrent.futures import ThreadPoolExecutor,as_completed
from contextlib import contextmanager
from datetime import datetime,timezone
import fcntl
import hashlib
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
PRIOR=BASE.parent/'2026-11-16-r2i-fresh-entry'


def read(path):return json.loads(path.read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(data,indent=2)+'\n');temporary.replace(path)


@contextmanager
def protocol_lock():
    with (BASE/'driver.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        try:yield
        finally:fcntl.flock(lock,fcntl.LOCK_UN)


def case_states(base,names):
    states={}
    for case in names:
        result=base/'runs'/case/'result.json'
        if result.exists():
            try:
                raw=read(result)
                if raw['case']!=case:raise ValueError('case mismatch')
                states[case]=dict(state='software_error' if raw['error'] else 'finished',result=raw)
            except (ValueError,KeyError) as error:states[case]=dict(state='unreadable_result',error=str(error))
        elif (base/'interruptions'/f'{case}.json').exists():
            record=read(base/'interruptions'/f'{case}.json')
            assert record['confirmed_no_live_processes'] is True
            states[case]=dict(state='interrupted_recorded',record=record)
        elif any(p.exists() for p in [base/'runs'/case,base/'logs'/case,base/'inputs'/case,
                base/'cases/G'/case,base/'cases/fallback'/case,base/'initializations'/case]):
            states[case]=dict(state='partial_unresolved')
        else:states[case]=dict(state='pending')
    return states


def choose_batch(names,states,batch=None,limit=8):
    assert 1<=limit<=8
    partial=[case for case in names if states[case]['state']=='partial_unresolved']
    if partial:raise RuntimeError(f'partial outputs require a process audit, no automatic retry: {partial}')
    batches=[names[i:i+8] for i in range(0,len(names),8)]
    indices=range(len(batches)) if batch is None else [batch]
    for index in indices:
        pending=[case for case in batches[index] if states[case]['state']=='pending']
        if pending:return index,pending[:limit]
    return None,[]


def dependencies():
    prior=read(PRIOR/'preflight.json')['dependencies']
    sources={p:sha(ROOT/p) for p in prior['source_hashes']}
    evaluators={p:sha(Path(p)) for p in prior['evaluator_hashes']}
    assert sources==prior['source_hashes'] and evaluators==prior['evaluator_hashes']
    for p in [BASE/'solve.py',BASE/'driver.py']:
        sources[str(p.relative_to(ROOT))]=sha(p)
    return dict(source_hashes=sources,evaluator_hashes=evaluators,targets_sha256=sha(BASE/'targets.json'))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--freeze',action='store_true')
    parser.add_argument('--batch',type=int)
    parser.add_argument('--limit',type=int,default=8)
    args=parser.parse_args()
    with protocol_lock():
        if args.freeze:
            assert not (BASE/'protocol.json').exists()
            write(BASE/'protocol.json',dict(dependencies=dependencies(),numerical_method='R2h G-first, unchanged',
                prior_seed_records_found=0,main_Rust_changed=False,cache_reuse=False,
                budgets=dict(G_total=960,G_stage=120,G_coarse_outer=10,final_outer=600,
                    fallback_AL=120,initialization=30,restoration=30),workers=8,blas_threads=1,
                interrupted_cases_retried=False,failures_removed=False))
            return 0
        assert dependencies()==read(BASE/'protocol.json')['dependencies'],'frozen source/configuration changed'
        targets=read(BASE/'targets.json');states=case_states(BASE,targets['cases'])
        batch,names=choose_batch(targets['cases'],states,args.batch,args.limit)
        if not names:print('No pending inputs in the requested scope.');return 0
        folder=BASE/'batches'/f'{batch:03d}';folder.mkdir(parents=True,exist_ok=True)
        attempt=folder/f'attempt{len(list(folder.glob("attempt*.json"))):03d}.json'
        assert not attempt.exists()
        start=monotonic()
        record=dict(batch=batch,cases=names,status='running',started_utc=datetime.now(timezone.utc).isoformat(),
            command=[sys.executable,*sys.argv],cwd=str(Path.cwd()),
            head=subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,text=True,stdout=subprocess.PIPE,check=True).stdout.strip(),
            python=sys.version,packages={p:importlib.metadata.version(p) for p in ['numpy','scipy','casadi']},
            workers=8,blas_threads=1,affinity=sorted(os.sched_getaffinity(0)),pid=os.getpid(),
            environment={k:os.environ.get(k) for k in ['PYTHONPATH','OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','PYTHONDONTWRITEBYTECODE']},
            cache_reuse=False,protocol_sha256=sha(BASE/'protocol.json'),targets_sha256=sha(BASE/'targets.json'))
        write(attempt,record)
        spec=importlib.util.spec_from_file_location('r3a_single_entry',BASE/'solve.py')
        solve=importlib.util.module_from_spec(spec);spec.loader.exec_module(solve)
        results=[]
        with ThreadPoolExecutor(8) as pool:
            jobs={pool.submit(solve.solve_case,case,{},BASE):case for case in names}
            for future in as_completed(jobs):
                result=future.result();results.append(result)
                print(json.dumps(dict(case=result['case'],route=result.get('route'),error=result['error'],seconds=result['seconds'])),flush=True)
        record.update(status='complete',finished_utc=datetime.now(timezone.utc).isoformat(),seconds=monotonic()-start,
            completed=len(results),software_errors=sum(r['error'] is not None for r in results))
        write(attempt,record)
        return int(record['software_errors']>0)


if __name__=='__main__':sys.exit(main())
