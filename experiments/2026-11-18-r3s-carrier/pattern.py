"""Post-plan descriptive analysis (does not change any count): what happens between the two contacts of the worst pair."""
import collections, csv, json, math, statistics
from common import ROOT, HERE, read, sha

idx = {p['case']: p for p in read(HERE/'source-index.json')['points']}
rows = [r for r in csv.DictReader(open(HERE/'cases.csv')) if r['status'] == 'carrier_late']
out = []
for r in rows:
    p = idx[r['case']]; d = read(ROOT/p['path']); assert sha(ROOT/p['path']) == p['sha256']
    a, b = json.loads(r['worst_pair']); j = int(r['worst_region']); reg = d['instance']['regions'][j]
    pts = d['solution']['r'][a:b+1]; modes = d['modes'][a:b]
    inside = all(math.dist(q, reg['o']) <= reg['rho'] + 1e-6 for q in pts)
    task_between = any(a < k < b for k in d['task_stamp'])
    other_charge = any(m >= 0 and m != j for m in modes)
    out.append(dict(case=r['case'], tau=int(r['tau']), route=r['route'], gap_segments=b-a, all_discharge=all(m == -1 for m in modes),
                    stays_in_disk=inside, task_between=task_between, other_region_between=other_charge,
                    excess_km=float(r['max_excess_km']), ratio=float(r['worst_required_seconds'])/float(r['worst_available_seconds']),
                    gap_seconds=float(r['worst_available_seconds'])))
c = collections.Counter((o['stays_in_disk'], o['task_between'], o['other_region_between']) for o in out)
summary = dict(late=len(out), pattern_counts={f'stays_in_disk={k[0]},task_between={k[1]},other_region_between={k[2]}': v for k, v in c.items()},
               gap_segments=collections.Counter(o['gap_segments'] for o in out).most_common(8),
               ratio_at_vd_over_vc=sum(abs(o['ratio'] - 36/10.8) < 1e-6 for o in out),
               gap_seconds_median=statistics.median(o['gap_seconds'] for o in out))
(HERE/'pattern.json').write_text(json.dumps(dict(summary=summary, rows=out), indent=1))
print(json.dumps(summary, indent=1))
