"""Read-only diagnosis of stored points; never imports or invokes an optimizer."""
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys
from time import monotonic

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from repair_initialization import audit
from diagnose_solution import residuals

COHORT = ROOT / 'experiments/2026-11-16-r3s-cohort'
PREVIOUS = ROOT / 'experiments/2026-11-17-r3s-paper-comparison'


def read(p):
    return json.loads(p.read_text())


def write(p, value):
    p.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def hours(point):
    # input.metrics may belong to the old template instead of this trajectory.
    values = point['solution']['s']
    assert values and all(math.isfinite(v) for v in values)
    return math.fsum(values)


def change(before, after):
    seconds = (after - before) * 3600
    return 'shorter' if seconds < -1 else 'longer' if seconds > 1 else 'within_one_second'


def dist(values):
    values = sorted(values)
    return dict(n=len(values), median=statistics.median(values) if values else None,
                mean=statistics.mean(values) if values else None,
                min=min(values) if values else None, max=max(values) if values else None)


def paired(rows):
    valid = [r for r in rows if r['baseline_h'] is not None and r['returned_h'] is not None]
    return dict(n=len(valid), counts={name: sum(r['change'] == name for r in valid)
                for name in ['shorter', 'within_one_second', 'longer']},
                delta_seconds=dist([3600 * (r['returned_h'] - r['baseline_h']) for r in valid]),
                relative_reduction=dist([1 - r['returned_h'] / r['baseline_h'] for r in valid]))


def collect():
    sources = {}

    def load(path):
        path = path.resolve()
        data = path.read_bytes()
        sources[str(path.relative_to(ROOT))] = hashlib.sha256(data).hexdigest()
        return json.loads(data)

    summary = load(COHORT / 'summary.json')
    paper = load(PREVIOUS / 'summary.json')
    load(PREVIOUS / 'source-index.json')
    assert summary['finished'] == summary['planned'] == 900
    rows, points = [], []
    for r in summary['cases']:
        cid = r['case']; origin = ROOT / 'experiments' / r['origin']
        raw = load(origin / 'runs' / cid / 'result.json'); outcome = raw['outcome']
        assert raw['route'] == r['route']
        tau = int(cid.split('-')[0][3:])
        common = dict(case=cid, tau=tau, origin=r['origin'], route=r['route'], selected=r['selected'])
        added = {}

        def add(label, path, *, al=None, certified=False):
            data = load(path)
            exported = hours(data)
            objective = exported if al is None else al['objective']
            if al is not None:
                # The Rust export serializes each segment at nine decimals.
                assert abs(objective - exported) <= len(data['solution']['s']) * .51e-9 + 1e-12
            checks = residuals(data)
            try:
                checked = audit(data)
                accepted = checked['accepted']; reason = None
                minimum = checked['dense_min_energy']
            except (ValueError, OverflowError) as error:
                accepted = False; reason = str(error); minimum = None
            row = dict(common, point=label, source=str(path.relative_to(ROOT)), objective_h=objective,
                       exported_objective_h=exported, original_residual=checks['viol'],
                       physical_audit=accepted, audit_error=reason, replay_min_energy=minimum,
                       al_export_rounded=al is not None, fixed_branch_kkt=certified,
                       al_stage=None if al is None else al['stage'],
                       al_common_kkt=None if al is None else al['final_common_pass'],
                       al_both_scales_kkt=None if al is None else al['final_both_scales_pass'])
            points.append(row); added[label] = row
            return row

        original = add('original', origin / 'inputs' / cid / 'input.json')
        assert original['physical_audit'] == r['original_audit']['accepted']
        init_dir = ROOT / outcome['initialization_source']
        if r['route'] == 'fallback':
            load(init_dir / 'guard.json')
            # The copied input must represent exactly the same original trajectory.
            copied = load(init_dir / 'input.json')
            original_data = load(origin / 'inputs' / cid / 'input.json')
            assert copied['solution'] == original_data['solution']
            witness = init_dir / 'witness.json'
            if witness.exists():
                assert add('constructed', witness)['physical_audit']
            if (init_dir / 'result.json').exists():
                initialization = load(init_dir / 'result.json')
                if initialization['accepted']:
                    assert add('initialization', init_dir / 'solution.json', certified=True)['physical_audit']
                else:
                    assert not (init_dir / 'solution.json').exists()
        candidates = [p for label, p in added.items() if p['physical_audit']]
        baseline = min(candidates, key=lambda p: p['objective_h']) if candidates else None
        branch_values = {}
        for branch in ['G', 'fallback']:
            phase = r[branch]
            if phase is None:
                continue
            folder = ROOT / phase['folder']; final = load(folder / 'result.json')
            entry = load(folder / 'source.json')
            entry_point = original if branch == 'G' or 'initialization' not in added else added['initialization']
            assert math.isclose(entry['objective'], entry_point['objective_h'], abs_tol=1e-10, rel_tol=1e-12)
            branch_values[branch + '_entry_h'] = entry['objective']
            branch_values[branch + '_AL_h'] = final['objective']
            add(branch + '_AL', folder / 'solution.json', al=final)
            if phase['restoration_accepted']:
                result = load(folder / 'restored/result.json'); assert result['accepted']
                assert add(branch + '_restoration', folder / 'restored/solution.json', certified=True)['physical_audit']
            assert final['objective'] == phase['final_AL_objective_hours']
        returned = None
        if outcome['physical_point_available']:
            returned = add('returned', origin / 'runs' / cid / 'selected.json',
                           certified=outcome['selected_same_final_branch_kkt'])
            assert returned['physical_audit']
            assert abs(returned['objective_h'] - outcome['selected_hours']) < 1e-12
        row = dict(common, original_h=original['objective_h'], original_feasible=original['physical_audit'],
                   constructed_h=added.get('constructed', {}).get('objective_h'),
                   initialization_h=added.get('initialization', {}).get('objective_h'),
                   baseline_h=None if baseline is None else baseline['objective_h'],
                   baseline_point=None if baseline is None else baseline['point'],
                   returned_h=None if returned is None else returned['objective_h'],
                   fixed_branch_kkt=outcome['selected_same_final_branch_kkt'],
                   change=None if baseline is None or returned is None else change(baseline['objective_h'], returned['objective_h']),
                   G_entry_h=branch_values.get('G_entry_h'), G_AL_h=branch_values.get('G_AL_h'),
                   fallback_entry_h=branch_values.get('fallback_entry_h'), fallback_AL_h=branch_values.get('fallback_AL_h'))
        rows.append(row)
    assert len(rows) == len({r['case'] for r in rows}) == 900
    return rows, points, sources, paper


def summarize(rows, points, paper):
    groups = []
    for tau in range(1, 10):
        cases = [r for r in rows if r['tau'] == tau]
        assert len(cases) == 100
        stages = {name: dist([r[name] for r in cases if r[name] is not None]) for name in
                  ['original_h', 'constructed_h', 'initialization_h', 'baseline_h', 'G_entry_h', 'G_AL_h',
                   'fallback_entry_h', 'fallback_AL_h', 'returned_h']}
        reference = next(g for g in paper['groups'] if g['tau'] == tau)
        assert stages['returned_h']['n'] == reference['returned']
        assert math.isclose(stages['returned_h']['median'], reference['selected']['median'], abs_tol=1e-12)
        groups.append(dict(tau=tau, original_feasible=sum(r['original_feasible'] for r in cases),
                      paper_median_h=reference['paper']['NLP']['median'], stages=stages, paired=paired(cases),
                      by_route={route: paired([r for r in cases if r['route'] == route]) for route in ['G', 'fallback']}))
    return dict(cases=len(rows), returned=sum(r['returned_h'] is not None for r in rows),
                original_feasible=sum(r['original_feasible'] for r in rows), groups=groups, paired=paired(rows),
                by_route={route: paired([r for r in rows if r['route'] == route]) for route in ['G', 'fallback']},
                by_selected={selection: paired([r for r in rows if r['selected'] == selection])
                             for selection in ['restoration', 'certificate', 'original', 'constructed', None]},
                point_counts={label: dict(n=sum(p['point'] == label for p in points),
                              audit_pass=sum(p['point'] == label and p['physical_audit'] for p in points))
                              for label in sorted({p['point'] for p in points})},
                kkt_recomputed=False, new_optimization=False)


def verify_sources():
    manifest = read(BASE / 'source-index.json')
    for name, expected in manifest.items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected, name
    return len(manifest)


def main():
    start = monotonic()
    if '--freeze' not in sys.argv:
        verify_sources()
    rows, points, sources, paper = collect()
    if '--freeze' in sys.argv:
        assert not (BASE / 'source-index.json').exists()
        write(BASE / 'source-index.json', sources)
        print(json.dumps(dict(sources=len(sources), cases=len(rows), points=len(points))))
        return
    assert sources == read(BASE / 'source-index.json')
    assert not (BASE / 'summary.json').exists()
    for name, data in [('cases.csv', rows), ('points.csv', points)]:
        with (BASE / name).open('w') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(data[0])); writer.writeheader(); writer.writerows(data)
    result = summarize(rows, points, paper)
    write(BASE / 'summary.json', result)
    write(BASE / 'execution.json', dict(seconds=monotonic() - start, sources=len(sources), new_optimization=False))
    print(json.dumps(dict(cases=len(rows), points=len(points), paired=result['paired'], by_route=result['by_route'])))


if __name__ == '__main__':
    main()
