"""Rust-check the saved R3s batch outputs; nothing is solved and no existing output is modified.

R3s change (2026-11-16, after batch 008): if the single call fails, every file is re-checked on its own.
A strict 1e-10 failure (the policy accepts 1e-6) is recorded per file and does not fail the audit; a metrics
disagreement, an unprintable file, or a returned point above 1e-6 still fails it. R3a used the single call only.

One call of scripts/verify_solutions.py for all files, as R2f's audit_outputs.py did. The evaluator
checks, for every file, that the saved metrics.viol and metrics.objective agree with the Rust
evaluation (serialization tolerance). Only files with a `diagnostic` key get the strict checks
(viol < 1e-10, exact endpoints, energy in [0,1], pure modes, dense battery history). The policy
limit 1e-6 is not asserted by the evaluator; it is counted here from the printed Rust values, in a
separate column. Smoothed-KKT points (cases/*/solution.json and stage solutions) have no
`diagnostic` key and are not original-feasible points.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
from time import monotonic

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE/'batches'/os.environ.get('UAV_R3_BATCH','000')
BATCH_CASES = set(case for p in OUT.glob('attempt*.json') for case in json.loads(p.read_text())['cases'])
GROUPS = [
    ('initialization NLP output', 'initializations/*/solution.json'),
    ('constructed witness', 'initializations/*/witness.json'),
    ('final smoothed AL point', 'cases/*/*/solution.json'),
    ('stage smoothed AL point', 'cases/*/*/stages/*/solution.json'),
    ('last restoration output', 'cases/*/*/restored/solution.json'),
    ('G evaluated output', 'evaluations/G/*/selected.json'),
    ('fallback evaluated output', 'evaluations/fallback/*/selected.json'),
    ('fallback certificate', 'evaluations/fallback/*/certificate.json'),
    ('returned output', 'runs/*/selected.json'),
]


PRINTED='{} objective {} original_violation {}'


def parse(stdout):
    printed={}
    for line in stdout.splitlines():
        parts=line.split()
        if len(parts)==5 and parts[1]=='objective' and parts[3]=='original_violation':
            printed[parts[0]]=dict(objective=float(parts[2]),original_violation=float(parts[4]))
    return printed


def classify(path,returncode,stdout):
    """One file checked alone: agree (line printed) and strict (zero return code), or the failing assertion."""
    printed=parse(stdout).get(str(path))
    failure=None
    if returncode:
        failure=next((l.strip() for l in stdout.splitlines() if l.strip().startswith('assertion failed')),'nonzero exit')
    return dict(path=str(path),printed=printed,returncode=returncode,metrics_agree=printed is not None,
        strict_passed=returncode==0,failure=failure)


def per_file(paths):
    rows=[]
    for path in paths:
        r=subprocess.run([sys.executable,str(ROOT/'scripts/verify_solutions.py'),str(path)],cwd=ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        rows.append(classify(path,r.returncode,r.stdout))
    return rows


def main():
    assert not (OUT/'rust-validation.log').exists() and not (OUT/'output-verification.json').exists(), 'refuse to overwrite'
    groups, paths, unusable = {}, [], []
    for label, pattern in GROUPS:
        files = sorted(p for p in HERE.glob(pattern) if any(case in p.parts for case in BATCH_CASES))
        usable = []
        for path in files:
            d = json.loads(path.read_text())
            if all(k in d for k in ['instance', 'phys', 'solution']) and all(k in d.get('metrics', {}) for k in ['viol', 'objective']):
                usable.append(path)
            else:
                unusable.append(dict(path=str(path.relative_to(ROOT)), reason='missing instance/phys/solution/metrics.viol/metrics.objective'))
        groups[label] = dict(pattern=pattern, files=len(files), checked=len(usable),
            with_diagnostic_key=sum('diagnostic' in json.loads(p.read_text()) for p in usable), paths=usable)
        paths += usable
    assert len(set(paths)) == len(paths)
    command = [sys.executable, str(ROOT/'scripts/verify_solutions.py'), *map(str, paths)]
    start = monotonic()
    result = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    seconds = monotonic()-start
    (OUT/'rust-validation.log').write_text(result.stdout)
    printed = parse(result.stdout);files=None
    if result.returncode:
        files = per_file(paths)
        printed = {r['path']:r['printed'] for r in files if r['printed']}
        (OUT/'rust-validation-per-file.json').write_text(json.dumps(files, indent=2)+'\n')
    strict_ok = (lambda p: result.returncode == 0) if files is None else (lambda p: next(r['strict_passed'] for r in files if r['path'] == str(p)))
    table = []
    for label, group in groups.items():
        group_paths = group.pop('paths')
        rows = [printed.get(str(p)) for p in group_paths]
        seen = [r for r in rows if r]
        strict = group['with_diagnostic_key']
        strict_passed = sum(strict_ok(p) for p in group_paths if 'diagnostic' in json.loads(p.read_text()))
        table.append(dict(kind=label, **group,
            # every printed line follows the two serialization assertions of that file
            rust_metrics_agree=len(seen),
            rust_original_violation_le_1e_6=sum(r['original_violation'] <= 1e-6 for r in seen),
            max_rust_original_violation=max((r['original_violation'] for r in seen), default=None),
            strict_1e_10_applicable=strict,
            # the strict assertions of a file run after its line is printed; a zero return code means all passed
            strict_1e_10_passed=strict_passed,
            strict_1e_10_failed=[str(p.relative_to(ROOT)) for p in group_paths if 'diagnostic' in json.loads(p.read_text()) and not strict_ok(p)]))
    rustc = subprocess.run(['rustc', '--version'], text=True, stdout=subprocess.PIPE).stdout.strip()
    report = dict(solver_launched=False, command=[command[0], 'scripts/verify_solutions.py', f'<{len(paths)} paths below>'],
        cwd=str(ROOT), rustc=rustc, python=sys.version, returncode=result.returncode, seconds=seconds,
        files_found=sum(row['files'] for row in table), files_checked=len(paths), files_not_checkable=unusable,
        printed_lines=len(printed),
        rust_metrics_agree=sum(row['rust_metrics_agree'] for row in table),
        strict_1e_10_applicable=sum(row['strict_1e_10_applicable'] for row in table),
        strict_1e_10_passed=sum(row['strict_1e_10_passed'] for row in table),
        per_file_recheck=files is not None,
        rust_original_violation_le_1e_6=sum(row['rust_original_violation_le_1e_6'] for row in table),
        note='1e-6 is counted from the printed Rust values (3 significant digits); smoothed AL points are not original-feasible and have no strict check',
        by_kind=table, paths=[str(p.relative_to(ROOT)) for p in paths])
    (OUT/'output-verification.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k: v for k, v in report.items() if k not in ['paths', 'by_kind']}))
    for row in table:
        print(json.dumps(row))
    returned = next(row for row in table if row['kind'] == 'returned output')
    fatal = report['rust_metrics_agree'] != len(paths) or unusable or returned['rust_original_violation_le_1e_6'] != returned['checked']
    if fatal:
        raise SystemExit(1)


if __name__ == '__main__':
    import driver as cohort_driver
    with cohort_driver.protocol_lock():main()
