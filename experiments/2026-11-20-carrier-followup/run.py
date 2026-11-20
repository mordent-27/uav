"""Frozen sequential experiment; never overwrite results."""
import copy
import hashlib
import json
import os
from pathlib import Path
import platform
from time import monotonic
import casadi as ca
import numpy as np
from model import HERE, ROOT, TARGETS, load, make_branch, solve, construct_fixed_positions, old


def save(path,value):
    assert not path.exists(),path
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=1,allow_nan=False)+'\n')


def main():
    for rel,digest in json.loads((HERE/'source-index.json').read_text()).items():
        assert hashlib.sha256((ROOT/rel).read_bytes()).hexdigest()==digest,rel
    assert not (HERE/'runs').exists()
    assert all(os.environ.get(k)=='1' for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'))
    save(HERE/'environment.json',dict(python=platform.python_version(),platform=platform.platform(),
         numpy=np.__version__,casadi=ca.__version__,options=old.OPTIONS,
         threads={k:os.environ[k] for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS')}))
    candidates={};construction=[]
    hard=[c for c in TARGETS if c.startswith('tau9-')]
    for case in hard:
        d,audit=construct_fixed_positions(load(case));candidates[case]=d if audit['accepted'] else None
        save(HERE/'construction'/f'{case}.json',d)
        construction.append(dict(case=case,accepted=audit['accepted'],objective_hours=sum(d['solution']['s']),independent=audit))
        print('construction',case,json.dumps(construction[-1]),flush=True)
    save(HERE/'construction.json',construction)
    rows=[];builds=[]
    for case in TARGETS:
        reference=load(case);models={}
        for method in ('R','q'):
            start=monotonic();models[method]=make_branch(reference,method)
            builds.append(dict(case=case,method=method,seconds=monotonic()-start))
        for rep in range(-1,5):
            order=('R','q') if rep%2 else ('q','R')
            for method in order:
                assert len(os.listdir('/proc/self/task'))==1,'parallel threads would invalidate the planned cost comparison'
                d,result,raw=solve(models[method],method,reference)
                name='warmup' if rep<0 else f'rep{rep+1}'
                dest=HERE/'runs'/case/f'{method}-{name}.json'
                save(dest,d);save(dest.with_name(dest.stem+'-solver.json'),raw)
                result.update(case=case,phase='comparison',warmup=rep<0,rep=rep+1,
                              solution_path=str(dest.relative_to(ROOT)),point_sha256=hashlib.sha256(dest.read_bytes()).hexdigest())
                rows.append(result)
                if case in candidates and candidates[case] is None and result['accepted'] and method=='R':
                    candidates[case]=copy.deepcopy(d)
                if rep==4:
                    print('comparison',case,method,json.dumps({k:result[k] for k in ('accepted','objective_hours','iterations','seconds','kkt')}),flush=True)
    save(HERE/'model-build-times.json',builds)
    save(HERE/'comparison.json',rows)
    # Feasible-start runs are separate from the original-start cost comparison.
    for case in hard:
        initial=candidates[case]
        if initial is None:
            print('geometry construction required',case,flush=True)
            continue
        save(HERE/'feasible-starts'/f'{case}.json',initial)
        reference=load(case)
        for method in ('R','q'):
            branch=make_branch(initial,method);d,result,raw=solve(branch,method,reference)
            dest=HERE/'warm-start-runs'/case/f'{method}.json';save(dest,d);save(dest.with_name(dest.stem+'-solver.json'),raw)
            result.update(case=case,phase='feasible-start',warmup=False,rep=0,
                          solution_path=str(dest.relative_to(ROOT)),point_sha256=hashlib.sha256(dest.read_bytes()).hexdigest())
            rows.append(result)
            print('feasible-start',case,method,json.dumps({k:result[k] for k in ('accepted','objective_hours','iterations','seconds','kkt')}),flush=True)
    save(HERE/'results.json',rows)


if __name__=='__main__':main()
