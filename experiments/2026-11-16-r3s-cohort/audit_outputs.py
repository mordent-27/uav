"""Rust-check the saved R3a batch outputs; nothing is solved and no existing output is modified.

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
    printed = {}
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) == 5 and parts[1] == 'objective' and parts[3] == 'original_violation':
            printed[parts[0]] = dict(objective=float(parts[2]), original_violation=float(parts[4]))
    table = []
    for label, group in groups.items():
        rows = [printed.get(str(p)) for p in group.pop('paths')]
        seen = [r for r in rows if r]
        strict = group['with_diagnostic_key']
        table.append(dict(kind=label, **group,
            # every printed line follows the two serialization assertions of that file
            rust_metrics_agree=len(seen),
            rust_original_violation_le_1e_6=sum(r['original_violation'] <= 1e-6 for r in seen),
            max_rust_original_violation=max((r['original_violation'] for r in seen), default=None),
            strict_1e_10_applicable=strict,
            # the strict assertions of a file run after its line is printed; a zero return code means all passed
            strict_1e_10_passed=strict if result.returncode == 0 else None))
    rustc = subprocess.run(['rustc', '--version'], text=True, stdout=subprocess.PIPE).stdout.strip()
    report = dict(solver_launched=False, command=[command[0], 'scripts/verify_solutions.py', f'<{len(paths)} paths below>'],
        cwd=str(ROOT), rustc=rustc, python=sys.version, returncode=result.returncode, seconds=seconds,
        files_found=sum(row['files'] for row in table), files_checked=len(paths), files_not_checkable=unusable,
        printed_lines=len(printed),
        rust_metrics_agree=sum(row['rust_metrics_agree'] for row in table),
        strict_1e_10_applicable=sum(row['strict_1e_10_applicable'] for row in table),
        strict_1e_10_passed=None if result.returncode else sum(row['strict_1e_10_passed'] for row in table),
        rust_original_violation_le_1e_6=sum(row['rust_original_violation_le_1e_6'] for row in table),
        note='1e-6 is counted from the printed Rust values (3 significant digits); smoothed AL points are not original-feasible and have no strict check',
        by_kind=table, paths=[str(p.relative_to(ROOT)) for p in paths])
    (OUT/'output-verification.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k: v for k, v in report.items() if k not in ['paths', 'by_kind']}))
    for row in table:
        print(json.dumps(row))
    if result.returncode:
        raise SystemExit(1)


if __name__ == '__main__':
    import driver as cohort_driver
    with cohort_driver.protocol_lock():main()
