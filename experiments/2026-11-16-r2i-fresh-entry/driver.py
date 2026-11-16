"""Prospective eight-input run of the unchanged R2h single-input entry, without caches."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
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
R2H=BASE.parent/'2026-11-16-r2h-g-first'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,data):path.write_text(json.dumps(data,indent=2)+'\n')


def dependencies():
    previous=json.loads((R2H/'provenance.json').read_text())
    sources={path:sha(ROOT/path) for path in previous['source_hashes']}
    evaluators={path:sha(Path(path)) for path in previous['evaluator_hashes']}
    assert sources==previous['source_hashes'],'R2h source changed'
    assert evaluators==previous['evaluator_hashes'],'native evaluator changed'
    return dict(source_hashes=sources,evaluator_hashes=evaluators)


def main():
    assert not (BASE/'execution.json').exists(),'refuse to repeat this run'
    expected=json.loads((BASE/'preflight.json').read_text())
    assert dependencies()==expected['dependencies']
    targets=json.loads((BASE/'targets.json').read_text())
    assert len(set(targets['cases']))==8 and targets['reused_entry_for_every_case']=={}
    spec=importlib.util.spec_from_file_location('r2h_single_entry',R2H/'solve.py')
    solve=importlib.util.module_from_spec(spec);spec.loader.exec_module(solve)
    start=monotonic()
    execution=dict(started_utc=datetime.now(timezone.utc).isoformat(),command=[sys.executable,*sys.argv],
        cwd=str(Path.cwd()),head=subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,text=True,stdout=subprocess.PIPE,check=True).stdout.strip(),
        python=sys.version,packages={p:importlib.metadata.version(p) for p in ['numpy','scipy','casadi']},
        environment={k:os.environ.get(k) for k in ['PYTHONPATH','OPENBLAS_NUM_THREADS','OMP_NUM_THREADS',
            'MKL_NUM_THREADS','PYTHONDONTWRITEBYTECODE']},workers=8,blas_threads=1,
        affinity=sorted(os.sched_getaffinity(0)),all_solves_fresh=True,dependency_check_passed=True)
    write(BASE/'execution.json',execution)
    results=[]
    with ThreadPoolExecutor(8) as pool:
        jobs={pool.submit(solve.solve_case,case,{},BASE):case for case in targets['cases']}
        for future in as_completed(jobs):
            result=future.result();results.append(result)
            print(json.dumps(dict(case=result['case'],route=result.get('route'),error=result['error'],seconds=result['seconds'])),flush=True)
    execution.update(finished_utc=datetime.now(timezone.utc).isoformat(),seconds=monotonic()-start,
        completed=len(results),errors=sum(r['error'] is not None for r in results),cached_solves=0)
    write(BASE/'execution.json',execution)
    return int(execution['errors']>0)


if __name__=='__main__':
    if '--preflight' in sys.argv:
        assert not (BASE/'preflight.json').exists()
        write(BASE/'preflight.json',dict(dependencies=dependencies(),no_optimizer_launched=True,
            prior_seed_search=dict(folders=['experiments','out'],extensions=['json','jsonl'],matching_seed_records=0)))
    else:sys.exit(main())
