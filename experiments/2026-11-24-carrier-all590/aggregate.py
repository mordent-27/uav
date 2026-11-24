"""Collect runs/*/result.json -> results.jsonl, summary.json, solution-manifest.json.
usage (from uav/): python experiments/2026-11-24-carrier-all590/aggregate.py [--pilot]
"""
import argparse, collections, json, statistics
from common import HERE, sha, targets


def q(xs, p):
    xs = sorted(xs); return xs[min(len(xs)-1, round(p*(len(xs)-1)))] if xs else None


def stats(xs):
    return dict(n=len(xs), median=statistics.median(xs) if xs else None, p90=q(xs, .9), max=max(xs) if xs else None, min=min(xs) if xs else None)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--pilot', action='store_true'); a = ap.parse_args()
    base = HERE/('pilot' if a.pilot else 'runs'); tag = 'pilot-' if a.pilot else ''
    names = {r['case'] for r in targets()}
    rows = [json.loads((p/'result.json').read_text()) for p in sorted(base.iterdir()) if (p/'result.json').exists()]
    assert all(r['case'] in names for r in rows)
    (HERE/f'{tag}results.jsonl').write_text(''.join(json.dumps(r, sort_keys=True)+'\n' for r in rows))
    manifest = {f'{r["case"]}/{m}.json.gz': sha(base/r['case']/f'{m}.json.gz') for r in rows for m in ('base', 'R')
                if (base/r['case']/f'{m}.json.gz').exists()}
    (HERE/f'{tag}solution-manifest.json').write_text(json.dumps(manifest, indent=1, sort_keys=True)+'\n')

    def group(sel):
        g = [r for r in rows if sel(r)]
        both = [r for r in g if r['base']['cls'] == 'success' and r['R']['cls'] == 'success']
        inc = [3600*(r['R']['objective_hours']-r['base']['objective_hours']) for r in both]
        rel = [100*(r['R']['objective_hours']/r['base']['objective_hours']-1) for r in both]
        rs = [r for r in g if r['R']['cls'] == 'success']
        return dict(points=len(g),
                    R=dict(collections.Counter(r['R']['cls'] for r in g)), base=dict(collections.Counter(r['base']['cls'] for r in g)),
                    both_success=len(both), increase_seconds=stats(inc), increase_percent=stats(rel),
                    R_minus_returned_seconds=stats([3600*(r['R']['objective_hours']-r['returned_hours']) for r in rs]),
                    base_success_still_short=sum(r['base']['cls'] == 'success' and r['base']['R_excess_km'] > 1e-9 for r in g))
    summary = dict(solved=len(rows), planned=590 if not a.pilot else 6, all=group(lambda r: True),
                   jump=group(lambda r: r['jump']), other=group(lambda r: not r['jump']),
                   by_route={k: group(lambda r, k=k: r['route'] == k) for k in ('G', 'fallback')},
                   by_tau={t: group(lambda r, t=t: r['tau'] == t) for t in range(1, 10)},
                   errors=[(r['case'], m, r[m]['error']) for r in rows for m in ('base', 'R') if 'error' in r[m]],
                   notes=['local Ipopt solutions with fixed assignment; increases are differences of local solutions',
                          'R rejected is not an infeasibility proof'])
    (HERE/f'{tag}summary.json').write_text(json.dumps(summary, indent=1)+'\n')
    print(json.dumps({k: summary[k] for k in ('solved', 'all', 'jump', 'other')}, indent=1))


if __name__ == '__main__':
    main()
