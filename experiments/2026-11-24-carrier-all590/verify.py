"""Independent recheck of every saved solution (verify_point.check only; no CasADi, no solver code).
usage (from uav/): python experiments/2026-11-24-carrier-all590/verify.py [--pilot]
"""
import argparse, json
from common import HERE, targets, load, with_solution, read_gz, check, carriers, classify, sha


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--pilot', action='store_true'); a = ap.parse_args()
    base = HERE/('pilot' if a.pilot else 'runs'); tag = 'pilot-' if a.pilot else ''
    rows = {r['case']: r for r in targets()}
    manifest = json.loads((HERE/f'{tag}solution-manifest.json').read_text())
    bad, n = [], 0
    for line in open(HERE/f'{tag}results.jsonl'):
        res = json.loads(line); ref = load(rows[res['case']]); assert res['input_sha256'] == rows[res['case']]['sha256']
        for m in ('base', 'R'):
            path = base/res['case']/f'{m}.json.gz'
            if 'error' in res[m]:
                assert not path.exists(); continue
            assert manifest[f"{res['case']}/{m}.json.gz"] == sha(path)
            d = with_solution(ref, read_gz(path))
            if m == 'R':
                d['carrier_positions'] = carriers(d)
            audit = check(d, ref)
            ok = audit['accepted'] if m == 'R' else (audit['original_residual'] < 1e-10 and audit['min_energy'] >= ref['phys']['e_min'] and audit['max_energy'] <= ref['phys']['e_max'])
            saved_ok = res[m]['cls'] != 'rejected'
            obj = sum(d['solution']['s'])
            if ok != saved_ok or abs(obj-res[m]['objective_hours']) > 1e-12 or abs(audit['R_excess_km']-res[m]['R_excess_km']) > 1e-12:
                bad.append((res['case'], m, ok, saved_ok, obj, res[m]['objective_hours']))
            n += 1
    out = dict(checked_solutions=n, mismatches=bad, method='verify_point.check on stored solutions with the original instance/modes')
    (HERE/f'{tag}verification.json').write_text(json.dumps(out, indent=1)+'\n')
    print(json.dumps(out, indent=1)); assert not bad


if __name__ == '__main__':
    main()
