"""Post-run readback of the 8 new phases with the existing verifier; no optimizer is launched.

Driver mode (no UAV_R2_CASE): start one process per saved phase, at most 8, one BLAS thread each.
Worker mode (UAV_R2_CASE and UAV_R2F_KIND set): load r2c-direct-final/verify.py unchanged and call
its main() on the saved state. Its only write, verification.json, is captured and compared with the
saved file instead of being written. Every comparison of the verifier goes through its close();
that function is wrapped to record the differences and then delegates to the original assertion.

Checks labelled `added` are not part of the existing verifier. They recompute, from saved states,
the initial AL gradient through the Jacobian, both KKT measures of the final point and the
stationarity through the Jacobian of the original constraints, and return the numbers.
New files go to reverification/ only; existing outputs are hashed before and after.
"""
from concurrent.futures import ThreadPoolExecutor
import gzip
import hashlib
import json
import linecache
import os
from pathlib import Path
import subprocess
import sys
from time import monotonic
import traceback

BASE = Path(__file__).resolve().parent
OUT = Path(os.environ.get('UAV_R2G_REVERIFY_OUT', BASE/'reverification'))  # override only for a dry run outside the repository
SUMMARY = OUT.with_suffix('.json')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot(folders):
    return {str(p): sha(p) for folder in folders for p in sorted(folder.rglob('*')) if p.is_file()}


def worker():
    import numpy as np
    import helpers as h
    start = monotonic()
    target = OUT/h.KIND/(h.CASE+'.json')
    assert not target.exists(), 'refuse to overwrite a reverification'
    before = snapshot([h.HERE, h.INIT])
    verify = h.load_from(h.DIRECT, 'verify')
    original_close, sites, captured = verify.close, {}, {}

    def recording_close(a, b, tol=1e-9):
        frame = sys._getframe(1)
        label = f'{frame.f_code.co_name}:{frame.f_lineno}: '+linecache.getline(frame.f_code.co_filename, frame.f_lineno).strip()
        x, y = np.atleast_1d(np.asarray(a, dtype=float)), np.atleast_1d(np.asarray(b, dtype=float))
        site = sites.setdefault(label, dict(calls=0, compared_values=0, max_abs_difference=0.,
            max_relative_difference=0., tolerance=tol))
        site['calls'] += 1
        site['compared_values'] += int(x.size)
        if x.shape == y.shape and x.size:
            diff = np.abs(x-y)
            site['max_abs_difference'] = max(site['max_abs_difference'], float(diff.max()))
            scale = np.maximum(np.abs(y), np.finfo(float).tiny)
            site['max_relative_difference'] = max(site['max_relative_difference'], float((diff/scale).max()))
        return original_close(a, b, tol)

    def capturing_write(path, data):
        assert Path(path) == h.HERE/'verification.json', path
        captured['verification'] = json.loads(json.dumps(data, allow_nan=False))

    verify.close, original_write, h.write = recording_close, h.write, capturing_write
    report = dict(case=h.CASE, kind=h.KIND, optimizer_launched=False,
        verifier='experiments/2026-11-15-r2c-direct-final/verify.py',
        verifier_sha256=sha(h.DIRECT/'verify.py'), existing_verifier_passed=False)
    try:
        verify.main()
        report['existing_verifier_passed'] = True
    except Exception:
        report['existing_verifier_error'] = traceback.format_exc()
    finally:
        verify.close, h.write = original_close, original_write
    report['existing_verifier_comparisons'] = sites
    saved = json.loads((h.HERE/'verification.json').read_text())
    recomputed = captured.get('verification')
    report['recomputed_verification'] = recomputed
    report['recomputed_equals_saved_verification'] = recomputed == saved
    report['saved_verification_sha256'] = sha(h.HERE/'verification.json')
    if recomputed:
        report['counts'] = {key: recomputed[key] for key in
            ['completed_outer', 'accepted_inner_points', 'interrupted_accepted_points']}
        report['saved_counts'] = {key: saved[key] for key in report['counts']}

    # Tally read from the saved outer log (no check; the update rule itself is asserted by the verifier above).
    rows = []
    for folder in sorted((h.HERE/'stages').glob('stage*')):
        with gzip.open(folder/'outer.jsonl.gz', 'rt') as handle:
            rows += [json.loads(line) for line in handle]
    report['outer_log_tally'] = dict(rows=len(rows), rho_first=rows[0]['rho'], rho_last_next=rows[-1]['rho_next'],
        rho_increases=sum(row['rho_next'] != row['rho'] for row in rows),
        inner_log_files=len(list((h.HERE/'stages').glob('stage*/inner*.jsonl.gz'))))

    added = {}
    try:
        source = json.loads(h.SOURCE.read_text())
        preflight = json.loads((h.HERE/'preflight.json').read_text())
        m = h.fidelity.Variant('R')
        m.stage(.0005, 12.)
        y = np.array(source['y'])
        lam, mu, rho = np.zeros(m.me), np.zeros(m.mi), 1e4
        assert not any(source['lam']) and not any(source['mu']) and source['rho'] == rho
        value, gradient = m.eval(y, lam, mu, rho)
        le, mi = lam+rho*m.h, np.maximum(0., mu+rho*m.g)
        jac = m.jacobian(y)
        _, gf = m.eval(y, np.zeros(m.me), np.zeros(m.mi), 0.)
        through_jacobian = gf+jac[:m.me].T@le+jac[m.me:].T@mi
        added['initial_al'] = dict(value=float(value), gradient_inf=float(max(abs(gradient))),
            saved_value=preflight['initial_al_value'], saved_gradient_inf=preflight['initial_al_gradient_inf'],
            value_difference=float(abs(value-preflight['initial_al_value'])),
            gradient_inf_difference=float(abs(max(abs(gradient))-preflight['initial_al_gradient_inf'])),
            gradient_minus_jacobian_form_inf=float(max(abs(gradient-through_jacobian))),
            saved_inner0001_input_gradient_inf=None)
        m.close()
        first = sorted((h.HERE/'stages').glob('stage*/inner0001.jsonl.gz'))[0]
        with gzip.open(first, 'rt') as handle:
            handle.readline()
            entry = json.loads(handle.readline())
        assert entry['kind'] == 'input' and entry['y'] == source['y']
        added['initial_al']['saved_inner0001_input_gradient_inf'] = entry['gradient_inf']

        overall = json.loads((h.HERE/'result.json').read_text())
        f = h.stage4.Frozen(overall)
        y, lam, mu = (np.array(overall[key]) for key in ['y', 'lam', 'mu'])
        measured = f.m.metrics(y, lam, mu)
        q, le, mi = f.m.reference_state(y, lam, mu)
        ref = f.m.reference
        jac = ref.jacobian(q)
        _, gf = ref.eval(q, np.zeros(ref.me), np.zeros(ref.mi), 0.)
        gradient = gf+jac[:ref.me].T@le+jac[ref.me:].T@mi
        stationarity = dict(common=float(max(abs(gradient))), paper_units=float(max(abs(gradient/ref.scale))))
        added['final_point'] = dict(common_kkt=measured['common_kkt'], paper_units_kkt=measured['paper_units_kkt'],
            saved_common_kkt=overall['common_kkt'], saved_paper_units_kkt=overall['paper_units_kkt'],
            max_common_kkt=max(measured['common_kkt'].values()), max_paper_units_kkt=max(measured['paper_units_kkt'].values()),
            max_difference_from_saved=max(abs(measured[key][name]-overall[key][name])
                for key in ['common_kkt', 'paper_units_kkt'] for name in measured[key]),
            original_jacobian_stationarity=stationarity,
            original_jacobian_stationarity_difference=max(abs(stationarity['common']-overall['common_kkt']['stat']),
                abs(stationarity['paper_units']-overall['paper_units_kkt']['stat'])),
            common_pass_recomputed=max(measured['common_kkt'].values()) <= 1e-6,
            both_scales_pass_recomputed=max(measured['common_kkt'].values()) <= 1e-6 and max(measured['paper_units_kkt'].values()) <= 1e-6,
            saved_final_common_pass=overall['final_common_pass'], saved_final_both_scales_pass=overall['final_both_scales_pass'])
        f.close()
        added['passed'] = bool(added['initial_al']['value_difference'] <= 1e-9
            and added['initial_al']['gradient_inf_difference'] <= 1e-9
            and added['initial_al']['gradient_minus_jacobian_form_inf'] <= 1e-8
            and added['final_point']['max_difference_from_saved'] <= 1e-9
            and added['final_point']['original_jacobian_stationarity_difference'] <= 1e-8
            and added['final_point']['common_pass_recomputed'] == overall['final_common_pass']
            and added['final_point']['both_scales_pass_recomputed'] == overall['final_both_scales_pass'])
    except Exception:
        added['passed'] = False
        added['error'] = traceback.format_exc()
    report['added'] = added
    after = snapshot([h.HERE, h.INIT])
    report['existing_files_hashed'] = len(before)
    report['existing_files_unchanged'] = before == after
    report['seconds'] = monotonic()-start
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('x') as handle:
        handle.write(json.dumps(report, indent=2, allow_nan=False)+'\n')
    print(json.dumps({k: report[k] for k in ['case', 'kind', 'existing_verifier_passed',
        'recomputed_equals_saved_verification', 'existing_files_unchanged', 'seconds']}
        | dict(added_passed=added['passed'], counts=report.get('counts'))), flush=True)
    if not (report['existing_verifier_passed'] and report['recomputed_equals_saved_verification']
            and added['passed'] and report['existing_files_unchanged']):
        raise SystemExit(1)


def launch(item):
    kind, case = item
    env = dict(os.environ, UAV_R2_CASE=case, UAV_R2F_KIND=kind, PYTHONDONTWRITEBYTECODE='1',
        OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1')
    env.pop('UAV_R2F_BASELINE', None)
    start = monotonic()
    with (OUT/'logs'/f'{case}-{kind}.log').open('x') as log:
        run = subprocess.run([sys.executable, str(Path(__file__).resolve())], env=env, stdout=log, stderr=subprocess.STDOUT)
    return dict(case=case, kind=kind, returncode=run.returncode, seconds=monotonic()-start)


def driver():
    assert not OUT.exists() and not SUMMARY.exists(), 'refuse to overwrite a reverification'
    phases = sorted((p.parent.name, p.name) for p in (BASE/'cases').glob('*/*') if p.is_dir())
    (OUT/'logs').mkdir(parents=True)
    start = monotonic()
    with ThreadPoolExecutor(8) as pool:
        runs = list(pool.map(launch, phases))
    reports = []
    for run in runs:
        path = OUT/run['kind']/(run['case']+'.json')
        reports.append(json.loads(path.read_text()) if path.exists() else None)
    done = [r for r in reports if r]
    full = [r for r in done if 'initial_al' in r['added'] and 'final_point' in r['added'] and 'counts' in r]
    comparisons = {}
    for report in done:
        for label, site in report['existing_verifier_comparisons'].items():
            total = comparisons.setdefault(label, dict(calls=0, compared_values=0, max_abs_difference=0.,
                max_relative_difference=0., tolerance=site['tolerance']))
            for key in ['calls', 'compared_values']:
                total[key] += site[key]
            for key in ['max_abs_difference', 'max_relative_difference']:
                total[key] = max(total[key], site[key])
    summary = dict(optimizer_launched=False, phases=len(phases), reports_written=len(done),
        workers=8, blas_threads=1, seconds=monotonic()-start, python=sys.version, executable=sys.executable,
        runs=runs,
        existing_verifier=dict(
            script='experiments/2026-11-15-r2c-direct-final/verify.py',
            checks_al_multiplier_update=True, checks_rho_update_rule=True,
            passed=sum(r['existing_verifier_passed'] for r in done),
            recomputed_equals_saved_verification=sum(r['recomputed_equals_saved_verification'] for r in done),
            completed_outer=sum(r['counts']['completed_outer'] for r in done if 'counts' in r),
            accepted_inner_points=sum(r['counts']['accepted_inner_points'] for r in done if 'counts' in r),
            interrupted_accepted_points=sum(r['counts']['interrupted_accepted_points'] for r in done if 'counts' in r),
            comparisons=comparisons,
            max_abs_difference_all_comparisons=max((s['max_abs_difference'] for s in comparisons.values()), default=None)),
        added=dict(
            note='not part of the existing verifier; recomputed from saved states in reverify.py',
            passed=sum(r['added']['passed'] for r in full),
            max_initial_al_value_difference=max(r['added']['initial_al']['value_difference'] for r in full),
            max_initial_al_gradient_difference=max(r['added']['initial_al']['gradient_inf_difference'] for r in full),
            max_initial_gradient_minus_jacobian_form=max(r['added']['initial_al']['gradient_minus_jacobian_form_inf'] for r in full),
            max_final_common_kkt=max(r['added']['final_point']['max_common_kkt'] for r in full),
            max_final_paper_units_kkt=max(r['added']['final_point']['max_paper_units_kkt'] for r in full),
            max_final_kkt_difference_from_saved=max(r['added']['final_point']['max_difference_from_saved'] for r in full),
            max_original_jacobian_stationarity_difference=max(r['added']['final_point']['original_jacobian_stationarity_difference'] for r in full)),
        outer_log_tally=dict(rows=sum(r['outer_log_tally']['rows'] for r in done),
            rho_increases=sum(r['outer_log_tally']['rho_increases'] for r in done),
            inner_log_files=sum(r['outer_log_tally']['inner_log_files'] for r in done)),
        existing_files_hashed=sum(r['existing_files_hashed'] for r in done),
        existing_files_unchanged=sum(r['existing_files_unchanged'] for r in done),
        phase_rows=[dict(case=r['case'], kind=r['kind'], **r['counts'],
            existing_verifier_passed=r['existing_verifier_passed'],
            recomputed_equals_saved_verification=r['recomputed_equals_saved_verification'],
            rho_increases=r['outer_log_tally']['rho_increases'], rho_last=r['outer_log_tally']['rho_last_next'],
            initial_al_gradient_inf=r['added']['initial_al']['gradient_inf'],
            final_common_kkt_max=r['added']['final_point']['max_common_kkt'],
            final_paper_units_kkt_max=r['added']['final_point']['max_paper_units_kkt'],
            max_abs_difference=max(s['max_abs_difference'] for s in r['existing_verifier_comparisons'].values()),
            seconds=r['seconds']) for r in full])
    with SUMMARY.open('x') as handle:
        handle.write(json.dumps(summary, indent=2, allow_nan=False)+'\n')
    print(json.dumps({k: v for k, v in summary.items() if k not in ['runs', 'phase_rows', 'existing_verifier', 'added']}
        | dict(existing_passed=summary['existing_verifier']['passed'], added_passed=summary['added']['passed'],
               outer=summary['existing_verifier']['completed_outer'], inner=summary['existing_verifier']['accepted_inner_points'],
               interrupted=summary['existing_verifier']['interrupted_accepted_points'])))
    if any(run['returncode'] for run in runs) or len(full) != len(phases):
        raise SystemExit(1)


if __name__ == '__main__':
    worker() if os.environ.get('UAV_R2_CASE') else driver()
