"""Independent CSV readback and manual order-statistic checks; no solving."""
import csv
import hashlib
import json
from pathlib import Path
import math
import sys

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[1]


def median(values):
    values = sorted(values)
    n = len(values)
    return None if not n else (values[(n - 1) // 2] + values[n // 2]) / 2


def close(a, b):
    assert a is None and b is None or a is not None and b is not None and math.isclose(a, b, abs_tol=1e-10, rel_tol=1e-12), (a, b)


def read_csv(path):
    with path.open() as stream:
        return list(csv.DictReader(stream))


def main():
    sources = json.loads((BASE / 'source-index.json').read_text())
    for name, digest in sources.items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest, name
    rows = read_csv(BASE / 'cases.csv'); points = read_csv(BASE / 'points.csv')
    old = {r['case']: r for r in read_csv(ROOT / 'experiments/2026-11-17-r3s-paper-comparison/cases.csv')}
    result = json.loads((BASE / 'summary.json').read_text())
    assert len(rows) == len({r['case'] for r in rows}) == 900
    assert set(old) == {r['case'] for r in rows}
    by_case = {}
    for p in points:
        by_case.setdefault(p['case'], {})[p['point']] = p
        source = json.loads((ROOT / p['source']).read_text())
        close(float(p['exported_objective_h']), sum(source['solution']['s']))
    counts = dict(shorter=0, within_one_second=0, longer=0)
    deltas = []
    for r in rows:
        ps = by_case[r['case']]
        assert r['selected'] == old[r['case']]['selected']
        assert r['route'] == old[r['case']]['route']
        assert bool(r['returned_h']) == (old[r['case']]['physical_point_available'] == 'True')
        if r['returned_h']:
            close(float(r['returned_h']), float(old[r['case']]['objective_h']))
        eligible = [p for label, p in ps.items() if label in ['original', 'constructed', 'initialization'] and p['physical_audit'] == 'True']
        if r['route'] == 'G':
            assert all(p['point'] == 'original' for p in eligible)
        close(float(r['baseline_h']) if r['baseline_h'] else None,
              min((float(p['objective_h']) for p in eligible), default=None))
        if r['baseline_h'] and r['returned_h']:
            delta = 3600 * (float(r['returned_h']) - float(r['baseline_h']))
            label = 'shorter' if delta < -1 else 'longer' if delta > 1 else 'within_one_second'
            assert r['change'] == label
            counts[label] += 1; deltas.append(delta)
    assert result['paired']['n'] == len(deltas)
    assert counts == result['paired']['counts']
    close(median(deltas), result['paired']['delta_seconds']['median'])
    for group in result['groups']:
        subset = [r for r in rows if int(r['tau']) == group['tau']]
        assert len(subset) == 100
        assert sum(r['original_feasible'] == 'True' for r in subset) == group['original_feasible']
        for stage, stats in group['stages'].items():
            vals = [float(r[stage]) for r in subset if r[stage]]
            assert stats['n'] == len(vals)
            close(median(vals), stats['median'])
            close(sum(vals) / len(vals) if vals else None, stats['mean'])
        paired = [r for r in subset if r['baseline_h'] and r['returned_h']]
        assert len(paired) == group['paired']['n']
        close(median([3600 * (float(r['returned_h']) - float(r['baseline_h'])) for r in paired]), group['paired']['delta_seconds']['median'])
        for route, stats in group['by_route'].items():
            selection = [r for r in paired if r['route'] == route]
            assert stats['n'] == len(selection)
            assert stats['counts'] == {name: sum(r['change'] == name for r in selection) for name in counts}
    verification = dict(passed=True, input_hashes=len(sources), cases=900, points=len(points),
                        returned=sum(bool(r['returned_h']) for r in rows), paired_counts=counts,
                        independent_csv_order_statistics=True, prior_900_cases_match=True,
                        kkt_recomputed=False, new_optimization=False)
    if '--check-only' not in sys.argv:
        assert not (BASE / 'verification.json').exists()
        (BASE / 'verification.json').write_text(json.dumps(verification, indent=2) + '\n')
    print(json.dumps(verification))


if __name__ == '__main__':
    main()
