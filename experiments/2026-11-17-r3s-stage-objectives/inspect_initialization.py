"""Exploratory follow-up: equal objective does not imply equal trajectory."""
import csv
import json
import math
from pathlib import Path

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[1]


def main():
    with (BASE / 'cases.csv').open() as stream:
        rows = list(csv.DictReader(stream))
    with (BASE / 'points.csv').open() as stream:
        points = list(csv.DictReader(stream))
    by_case = {}
    for p in points:
        by_case.setdefault(p['case'], {})[p['point']] = p
    comparison = []
    for r in rows:
        if not r['initialization_h']:
            continue
        ps = by_case[r['case']]
        initial = json.loads((ROOT / ps['initialization']['source']).read_text())
        returned = json.loads((ROOT / ps['returned']['source']).read_text())
        a, b = initial['solution'], returned['solution']
        assert len(a['r']) == len(b['r']) and len(a['s']) == len(b['s'])
        comparison.append(dict(case=r['case'], tau=int(r['tau']), selected=r['selected'],
            returned_minus_init_seconds=3600 * (float(r['returned_h']) - float(r['initialization_h'])),
            AL_minus_init_seconds=3600 * (float(r['fallback_AL_h']) - float(r['initialization_h'])),
            same_modes=initial['modes'] == returned['modes'],
            same_task_stamps=initial['task_stamp'] == returned['task_stamp'],
            max_position_difference_km=max(math.dist(x, y) for x, y in zip(a['r'], b['r'])),
            max_duration_difference_seconds=3600 * max(abs(x-y) for x, y in zip(a['s'], b['s']))))
    assert len(comparison) == 202
    assert not (BASE / 'initialization-pairs.csv').exists()
    with (BASE / 'initialization-pairs.csv').open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(comparison[0]), lineterminator='\n'); writer.writeheader(); writer.writerows(comparison)
    def extrema(key):
        return dict(min=min(r[key] for r in comparison), max=max(r[key] for r in comparison))
    stats = dict(exploratory=True, n=len(comparison),
                 returned_minus_init_seconds=extrema('returned_minus_init_seconds'),
                 AL_minus_init_seconds=extrema('AL_minus_init_seconds'),
                 same_modes=sum(r['same_modes'] for r in comparison),
                 same_task_stamps=sum(r['same_task_stamps'] for r in comparison),
                 position_difference_km=extrema('max_position_difference_km'),
                 segment_duration_difference_seconds=extrema('max_duration_difference_seconds'),
                 original_infeasible_decomposition=dict(
                     total=sum(r['original_feasible'] == 'False' for r in rows),
                     G_return=sum(r['route'] == 'G' and r['original_feasible'] == 'False' for r in rows),
                     accepted_initialization=sum(bool(r['initialization_h']) for r in rows),
                     constructed_return=sum(r['selected'] == 'constructed' for r in rows),
                     missing=sum(not r['returned_h'] for r in rows)),
                 AL_export_residual_pass={label: sum(p['point'] == label and float(p['original_residual']) <= 1e-6 for p in points)
                                          for label in ['G_AL', 'fallback_AL']})
    (BASE / 'initialization-inspection.json').write_text(json.dumps(stats, indent=2) + '\n')
    print(json.dumps(stats))


if __name__ == '__main__':
    main()
