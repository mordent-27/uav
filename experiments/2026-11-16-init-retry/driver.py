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
import policy

BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[1]
spec=importlib.util.spec_from_file_location('retry_guard',BASE.parent/'2026-11-16-r3a-cohort/driver.py')
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
            python=sys.version,packages={p:importlib.metadata.version(p) for p in ['numpy','scipy','casadi']},workers=4,blas_threads=1,
            environment={k:os.environ.get(k) for k in ['PYTHONPATH','OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS']})
        guard.write(BASE/'execution.json',execution)
        def run_case(case):
            t=monotonic();entry=targets['cases'][case];calls=[]
            def solve(arm):
                env=dict(os.environ,UAV_DIAG_CASE=case,UAV_DIAG_ARM=arm,UAV_R2_CASE='fig1',
                    OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1')
                with (BASE/'logs'/f'{case}-{arm}.log').open('x') as log:
                    run=subprocess.run([sys.executable,str(BASE/'run.py')],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
                calls.append(dict(arm=arm,returncode=run.returncode));assert run.returncode==0
                return guard.read(BASE/'cases'/arm/case/'result.json')
            if entry['construction_accepted']:
                baseline=solve('baseline');choice=policy.choose(baseline,lambda:solve('small_push'))
                selected=choice['selected'];source=BASE/'cases'/selected/case/'solution.json' if selected else ROOT/entry['source']/'witness.json'
                certified=selected is not None
            else:
                choice=dict(selected=None,retried=False,result=None);source=None;certified=False
            out=BASE/'selected'/case;out.mkdir(parents=True,exist_ok=False)
            if source:(out/'solution.json').write_bytes(source.read_bytes())
            result=dict(case=case,**choice,physical_point_available=source is not None,branch_kkt_pass=certified,
                output_kind=choice['selected'] or ('constructed' if source else None),calls=calls,seconds=monotonic()-t,
                source=None if source is None else str(source.relative_to(ROOT)),
                selected_sha256=None if source is None else guard.sha(source),paper_reproduction=False)
            guard.write(out/'result.json',result);return result
        with ThreadPoolExecutor(4) as pool:results=list(pool.map(run_case,targets['cases']))
        execution.update(finished_utc=datetime.now(timezone.utc).isoformat(),seconds=monotonic()-start,
            completed=len(results),nlp_solves=sum(len(r['calls']) for r in results))
        guard.write(BASE/'execution.json',execution)
        print(json.dumps(dict(completed=len(results),nlp_solves=execution['nlp_solves'],seconds=execution['seconds'])))


if __name__=='__main__':main()
