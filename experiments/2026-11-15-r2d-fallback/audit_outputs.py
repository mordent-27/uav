"""Check output adoption and evaluate all new outputs plus adopted outputs with Rust."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def main():
    summary = json.loads((HERE/'summary.json').read_text())
    rows = summary['regression_cases']+summary['diagnostic_holdout_cases']
    adopted = []
    for row in rows:
        if not row['accepted']:
            continue
        path = ROOT/row['adopted']['path']
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row['adopted']['sha256']
        assert row['G']['accepted'] == (row['selected_phase'] == 'G')
        if row['G']['accepted']:
            assert path == ROOT/row['G']['path']/'restored/solution.json'
        adopted.append(path)
    new = sorted((HERE/'cases').glob('*/*/solution.json'))
    new += sorted((HERE/'cases').glob('*/*/stages/*/solution.json'))
    new += sorted((HERE/'cases').glob('*/*/restored/solution.json'))
    paths = sorted(set(new+adopted))
    run = subprocess.run([sys.executable, str(ROOT/'scripts/verify_solutions.py'), *map(str, paths)],
        cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    (HERE/'rust-validation.log').write_text(run.stdout)
    report = dict(new_outputs=len(new), adopted_outputs=len(adopted), unique_rust_outputs=len(paths),
        returncode=run.returncode, G_adoption_without_replacement_verified=True,
        output_paths=[str(path.relative_to(ROOT)) for path in paths])
    (HERE/'output-verification.json').write_text(json.dumps(report, indent=2)+'\n')
    assert run.returncode == 0, 'Rust check failed; keep log and distinguish strict 1e-10 from policy 1e-6'
    print(json.dumps({k:v for k,v in report.items() if k != 'output_paths'}))


if __name__ == '__main__':
    main()
