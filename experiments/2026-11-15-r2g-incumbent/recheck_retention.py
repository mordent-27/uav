"""Run retain.finalize again on the saved states, into a temporary folder outside the repository,
and compare what it writes with the saved retention outputs. No optimizer is launched (retain.py
only re-evaluates stored points) and no existing output is written: finalize() creates its
destination with exist_ok=False and writes only there.

Set UAV_R2_CASE to any valid case name (helpers.py needs it at import; finalize() takes the case
as an argument). Needs the solve-time Python environment (NumPy, CasADi).
"""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from time import monotonic

import helpers as h
import retain

BASE = Path(__file__).resolve().parent
REPORT = BASE/'retention-recheck.json'


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot(folder):
    return {str(p): sha(p) for p in sorted(folder.rglob('*')) if p.is_file()}


def main():
    assert not REPORT.exists(), 'refuse to overwrite'
    start = monotonic()
    old = read(h.R2F/'summary.json')
    items = [('regression', row['case'], h.ROOT/row['candidate']['path'], h.R2F/'initializations'/row['case'],
              BASE/'regression'/row['case'], True) for row in old['cases']]
    for saved in sorted((BASE/'evaluations').glob('*/*')):
        kind, case = saved.parent.name, saved.name
        items.append((kind, case, BASE/'cases'/kind/case, BASE/'initializations'/case, saved, kind == 'repaired'))
    scratch = Path(tempfile.mkdtemp(prefix='uav-r2g-retention-recheck-'))
    assert h.ROOT not in scratch.parents
    rows = []
    for group, case, solver_folder, init_folder, saved, allow in items:
        inputs = [solver_folder, init_folder, saved]
        before = [snapshot(folder) for folder in inputs]
        destination = scratch/group/case
        row = dict(group=group, case=case, saved=str(saved.relative_to(h.ROOT)))
        try:
            result = retain.finalize(case, solver_folder, init_folder, destination, allow)
            old_result, new_result = read(saved/'result.json'), read(destination/'result.json')
            timing = {'seconds'}
            row.update(recomputed=True,
                files_saved=sorted(p.name for p in saved.iterdir()),
                files_recomputed=sorted(p.name for p in destination.iterdir()),
                result_equal_except_seconds={k: v for k, v in old_result.items() if k not in timing} ==
                    {k: v for k, v in new_result.items() if k not in timing},
                validation_equal=read(saved/'validation.json') == read(destination/'validation.json'),
                selected_bytes_equal=(saved/'selected.json').read_bytes() == (destination/'selected.json').read_bytes(),
                certificate_bytes_equal=None if not (saved/'certificate.json').exists() else
                    (destination/'certificate.json').exists() and
                    (saved/'certificate.json').read_bytes() == (destination/'certificate.json').read_bytes(),
                selected=result['selected'], selected_same_final_branch_kkt=result['selected_same_final_branch_kkt'],
                physical_point_available=result['physical_point_available'],
                initialization_certificate_valid=result['initialization_certificate_valid'],
                recheck_seconds=new_result['seconds'])
            row['same_files'] = row['files_saved'] == row['files_recomputed']
            row['all_equal'] = bool(row['same_files'] and row['result_equal_except_seconds'] and row['validation_equal']
                and row['selected_bytes_equal'] and row['certificate_bytes_equal'] in (None, True))
        except Exception as error:
            row.update(recomputed=False, all_equal=False, error=repr(error))
        row['inputs_unchanged'] = before == [snapshot(folder) for folder in inputs]
        rows.append(row)
    report = dict(optimizer_launched=False, function='retain.finalize (unchanged) with a temporary destination',
        temporary_destination=str(scratch), python=sys.version, executable=sys.executable,
        evaluations=len(rows), recomputed=sum(r['recomputed'] for r in rows), all_equal=sum(r['all_equal'] for r in rows),
        inputs_unchanged=sum(r['inputs_unchanged'] for r in rows),
        retain_sha256=sha(BASE/'retain.py'), feasible_incumbent_sha256=sha(h.ROOT/'scripts/feasible_incumbent.py'),
        seconds=monotonic()-start, rows=rows)
    REPORT.write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'rows'}))
    if report['all_equal'] != len(rows) or report['inputs_unchanged'] != len(rows):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
