"""Rust-check every new output in both experiments and the two reused direct baselines."""
import json
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
FOLLOW=HERE.parent/'2026-11-15-r2e-feasible-start'
paths=[]
for folder in [HERE,FOLLOW]:
    paths+=list((folder/'cases').glob('*/*/solution.json'))
    paths+=list((folder/'cases').glob('*/*/stages/*/solution.json'))
    paths+=list((folder/'cases').glob('*/*/restored/solution.json'))
    paths+=list((folder/'initializations').glob('*/solution.json'))
    paths+=list((folder/'initializations').glob('*/witness.json'))
new_count=len(paths)
for case in ['tau5-seed3','tau7-seed3']:
    folder=HERE.parent/'2026-11-15-r2d-fallback/cases/direct'/case
    paths.append(folder/'solution.json')
    if (folder/'restored/solution.json').exists():paths.append(folder/'restored/solution.json')
paths=sorted(set(paths))
answer=subprocess.run([sys.executable,str(ROOT/'scripts/verify_solutions.py'),*map(str,paths)],
    cwd=ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
(HERE/'rust-validation.log').write_text(answer.stdout)
report=dict(new_outputs=new_count,unique_rust_outputs=len(paths),returncode=answer.returncode,
    paths=[str(path.relative_to(ROOT)) for path in paths])
(HERE/'output-verification.json').write_text(json.dumps(report,indent=2)+'\n')
assert answer.returncode==0,'Rust check failed; preserve log and distinguish policy 1e-6 from strict 1e-10'
print(json.dumps({k:v for k,v in report.items() if k!='paths'}))
