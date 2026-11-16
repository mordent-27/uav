"""Run the 11 cases through the unchanged R3 entry (control/) and the stall-rule entry (stall/), interleaved on 8 threads."""
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from time import monotonic

BASE=Path(__file__).resolve().parent;ROOT=BASE.parents[1]
spec=importlib.util.spec_from_file_location('stall_e2e_guard',BASE.parent/'2026-11-16-r3a-cohort/driver.py')
guard=importlib.util.module_from_spec(spec);spec.loader.exec_module(guard)


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def check_inputs(targets):
    for name,digest in targets['reused_modules'].items():assert sha(ROOT/name)==digest,name
    for name,digest in targets['evaluator_hashes'].items():assert sha(Path(name))==digest,name


def main():
    with guard.protocol_lock():
        targets=json.loads((BASE/'targets.json').read_text());check_inputs(targets)
        tests=(BASE/'tests.log').read_text();assert 'Ran 4 tests' in tests and tests.strip().endswith('OK')
        assert not (BASE/'control').exists() and not (BASE/'stall').exists()
        spec=importlib.util.spec_from_file_location('stall_e2e_entry',BASE/'entry.py');entry=importlib.util.module_from_spec(spec);spec.loader.exec_module(entry)
        start=monotonic();results=[]
        execution=dict(started_utc=datetime.now(timezone.utc).isoformat(),head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
            command=[sys.executable,*sys.argv],workers=targets['workers'],blas_threads=1,python=sys.version,cases=targets['cases'],
            environment={k:os.environ.get(k) for k in ['PYTHONPATH','OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','PYTHONDONTWRITEBYTECODE']})
        (BASE/'execution.json').write_text(json.dumps(execution,indent=2)+'\n')
        with ThreadPoolExecutor(targets['workers']) as pool:
            jobs={}
            for case in targets['cases']:
                for arm in ['control','stall']:
                    jobs[pool.submit(entry.solve_case,case,{},BASE/arm,arm=='stall')]=(case,arm)
            for future in as_completed(jobs):
                case,arm=jobs[future];r=future.result();results.append(dict(case=case,arm=arm,route=r.get('route'),error=r['error'],seconds=r['seconds']))
                print(json.dumps(results[-1]),flush=True)
        execution.update(finished_utc=datetime.now(timezone.utc).isoformat(),seconds=monotonic()-start,results=results,
            software_errors=sum(r['error'] is not None for r in results))
        (BASE/'execution.json').write_text(json.dumps(execution,indent=2)+'\n');check_inputs(targets)
        return int(execution['software_errors']>0)


if __name__=='__main__':sys.exit(main())
