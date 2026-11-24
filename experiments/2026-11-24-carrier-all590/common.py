"""Paths, targets and the classification fixed in PLAN.md (no CasADi here)."""
import csv, gzip, hashlib, json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
EXP1 = ROOT/'experiments/2026-11-18-r3s-carrier'
FOLLOW = ROOT/'experiments/2026-11-20-carrier-followup'
sys.path.insert(0, str(FOLLOW))
from verify_point import check, carriers  # independent physical checks

CORRECTION_TOL = 1e-12  # hours
PILOT = ['tau4-seed4000012', 'tau6-seed6000032', 'tau9-seed9000076',
         'tau9-seed9000001', 'tau8-seed8000015', 'tau7-seed7000053']


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path): return json.loads(Path(path).read_text())


def targets():
    """The 590 carrier_late points of experiment 1, with route and worst-pair pattern."""
    index = {p['case']: p for p in read(EXP1/'source-index.json')['points']}
    pattern = {o['case']: o for o in read(EXP1/'pattern.json')['rows']}
    rows = []
    for r in csv.DictReader(open(EXP1/'cases.csv')):
        if r['status'] != 'carrier_late':
            continue
        o = pattern[r['case']]
        rows.append(dict(case=r['case'], tau=int(r['tau']), route=r['route'], selected=r['selected'],
                         returned_hours=float(r['hours']), excess_km=float(r['max_excess_km']),
                         jump=bool(o['stays_in_disk'] and not o['task_between']),
                         path=index[r['case']]['path'], sha256=index[r['case']]['sha256']))
    return rows


def load(row):
    path = ROOT/row['path']
    assert sha(path) == row['sha256'], row['case']
    return read(path)


def classify(method, solver_success, correction_hours, audit, energy_bounds):
    """'success' / 'corrected_feasible' / 'rejected' (PLAN.md)."""
    lo, hi = energy_bounds
    original_ok = audit['original_residual'] < 1e-10 and audit['min_energy'] >= lo and audit['max_energy'] <= hi
    ok = original_ok if method == 'base' else audit['accepted']
    if not ok:
        return 'rejected'
    return 'success' if solver_success and correction_hours <= CORRECTION_TOL else 'corrected_feasible'


def with_solution(reference, solution):
    d = dict(reference); d['solution'] = solution; d.pop('carrier_positions', None)
    return d


def write_gz(path, value):
    tmp = path.with_name(path.name+'.tmp')
    with gzip.open(tmp, 'wt') as f:
        json.dump(value, f, allow_nan=False)
    tmp.rename(path)


def read_gz(path):
    with gzip.open(path, 'rt') as f:
        return json.load(f)
