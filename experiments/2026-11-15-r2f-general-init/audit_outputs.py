"""Rust-check new outputs and paired reused baselines, including the diagnostic certificate."""
import json
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
summary=json.loads((HERE/'summary.json').read_text())
new=list((HERE/'cases').glob('*/*/solution.json'))+list((HERE/'cases').glob('*/*/stages/*/solution.json'))
new+=list((HERE/'cases').glob('*/*/restored/solution.json'))
new+=list((HERE/'initializations').glob('*/solution.json'))+list((HERE/'initializations').glob('*/witness.json'))
new+=list((HERE/'diagnostics').glob('*/incumbent.json'))
paths=list(new)
for row in summary['cases']:
    if row['baseline_reused']:
        folder=ROOT/row['baseline']['path'];paths.append(folder/'solution.json')
        if (folder/'restored/solution.json').exists():paths.append(folder/'restored/solution.json')
paths=sorted(set(paths))
result=subprocess.run([sys.executable,str(ROOT/'scripts/verify_solutions.py'),*map(str,paths)],cwd=ROOT,
    text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
(HERE/'rust-validation.log').write_text(result.stdout)
report=dict(new_outputs=len(new),unique_rust_outputs=len(paths),returncode=result.returncode,
    paths=[str(p.relative_to(ROOT)) for p in paths])
(HERE/'output-verification.json').write_text(json.dumps(report,indent=2)+'\n')
assert result.returncode==0,'keep the log; distinguish strict 1e-10 from policy acceptance 1e-6'
print(json.dumps({k:v for k,v in report.items() if k!='paths'}))
