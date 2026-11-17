from concurrent.futures import ThreadPoolExecutor,as_completed
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from time import monotonic

BASE=Path(__file__).resolve().parent;ROOT=BASE.parents[1]
CASES=['tau9-seed9000035','tau8-seed8000006','tau8-seed8000062','tau7-seed7000005']
PRIOR=ROOT/'experiments/2026-11-16-r3s-cohort'


def read(p):return json.loads(p.read_text())
def write(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2)+'\n')


def freeze():
    assert not (BASE/'source-index.json').exists()
    sources=read(ROOT/'experiments/2026-11-17-r3s-gradient-only/source-index.json')
    extras=[PRIOR/'summary.json',ROOT/'experiments/2026-11-17-r3s-gradient-only/fast_hessian.py',PRIOR/'solve.py']
    for case in CASES:
        extras.extend([PRIOR/'runs'/case/'result.json',PRIOR/'inputs'/case/'input.json',PRIOR/'runs'/case/'selected.json'])
    for path in extras:sources[str(path.relative_to(ROOT))]=hashlib.sha256(path.read_bytes()).hexdigest()
    summary=read(PRIOR/'summary.json')
    controls=sorted(r['case'] for r in summary['cases'] if r['origin']==PRIOR.name and r['route']=='G' and r['case'].startswith('tau7-'))
    assert controls[0]==CASES[-1]
    write(BASE/'source-index.json',sources);write(BASE/'targets.json',dict(cases=CASES,modes=['original','fast'],jobs=8))
    print(json.dumps(dict(sources=len(sources),jobs=8)))


def worker(mode,case):
    os.environ['UAV_GRADIENT_MODE']=mode
    spec=importlib.util.spec_from_file_location('original_r3s_solve',PRIOR/'solve.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.STALL_CODE=BASE
    result=module.solve_case(case,{},BASE/mode)
    print(json.dumps(dict(mode=mode,case=case,error=result['error'],seconds=result['seconds'])),flush=True)
    return int(result['error'] is not None)


def main():
    if '--freeze' in sys.argv:freeze();return
    for name,digest in read(BASE/'source-index.json').items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
    if '--worker' in sys.argv:
        i=sys.argv.index('--worker');return worker(sys.argv[i+1],sys.argv[i+2])
    assert not (BASE/'execution.json').exists() and not any((BASE/m).exists() for m in ['original','fast'])
    env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1')
    start=monotonic();write(BASE/'execution.json',dict(command=sys.argv,executable=sys.executable,jobs=8,new_full_runs=8))
    def launch(mode,case):
        with (BASE/f'{mode}-{case}.log').open('w') as stream:
            p=subprocess.run([sys.executable,__file__,'--worker',mode,case],env=env,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT)
        return dict(mode=mode,case=case,returncode=p.returncode,elapsed=monotonic()-start)
    done=[]
    with ThreadPoolExecutor(max_workers=8) as pool:
        jobs=[pool.submit(launch,mode,case) for case in CASES for mode in ['original','fast']]
        for future in as_completed(jobs):
            result=future.result();done.append(result);write(BASE/'progress.json',dict(finished=len(done),planned=8,results=done));print(json.dumps(result),flush=True)
    write(BASE/'completion.json',dict(wall_seconds=monotonic()-start,results=done))
    return int(any(r['returncode'] for r in done))


if __name__=='__main__':sys.exit(main() or 0)
