"""Frozen 13-case pilot of the equivalent speed scaling and dense BFGS AL.

Original model feasible set; no c<=s addition, psi change, or postprocessing.
Reuse the two diagnostics already run; every other case is attempted once.
"""
from concurrent.futures import ThreadPoolExecutor,as_completed
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
OUT=HERE/'pilot';OUT.mkdir(exist_ok=True)
cases=[('fig1',0,0)]+[(f'tau{tau}-seed{seed}',tau,seed) for tau in [1,3,5,7] for seed in [0,1,2]]
reuse={'fig1':HERE/'diagnostics/fig1-speed-full.json',
       'tau1-seed0':HERE/'diagnostics/tau1-speed-full.json'}
manifest=dict(cases=cases,library_sha256=hashlib.sha256(Path('/tmp/uav-reproduction-speed.so').read_bytes()).hexdigest(),
    backend='equivalent speed constraint scaling plus dense BFGS AL; diagnostic, not MATLAB L-BFGS',
    workers=2,timeout_seconds=90,source_sha256=hashlib.sha256((HERE/'independent_al.py').read_bytes()).hexdigest())
(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')


def run(case):
    name,tau,seed=case
    if name in reuse:return dict(case=name,source=str(reuse[name].relative_to(HERE)),reused=True)
    path=OUT/(name+'.json')
    if path.exists():raise RuntimeError('pilot case already exists; explicit review required before retry')
    command=[sys.executable,str(HERE/'independent_al.py'),'--tau',str(tau),'--seed',str(seed),
             '--backend','scipy-bfgs','--library','/tmp/uav-reproduction-speed.so','--out',str(path)]
    with (OUT/(name+'.log')).open('w') as log:
        result=subprocess.run(command,stdout=log,stderr=log,timeout=110)
    return dict(case=name,source=str(path.relative_to(HERE)),reused=False,exit_code=result.returncode)


rows=[]
with ThreadPoolExecutor(max_workers=2) as executor:
    for future in as_completed([executor.submit(run,case) for case in cases]):
        row=future.result();rows.append(row)
        (OUT/'cases.json').write_text(json.dumps(sorted(rows,key=lambda r:r['case']),indent=2)+'\n')
        print(json.dumps(row),flush=True)
