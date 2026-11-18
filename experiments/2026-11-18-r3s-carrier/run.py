"""Carrier certificate (scripts/carrier_certificate.py, unchanged) on every indexed returned point."""
import collections
import csv
import json
import statistics
import sys
from common import ROOT, HERE, read, sha, tau, revisits, choose

sys.path.insert(0, str(ROOT/'scripts'))
import carrier_certificate as cc

index = read(HERE/'source-index.json')
rows, certs = [], {}
for p in index['points']:
    path = ROOT/p['path']
    assert sha(path) == p['sha256']
    d = read(path)
    row = dict(case=p['case'], tau=tau(p['case']), origin=p['origin'], route=p['route'], selected=p['selected'],
               hours=p['selected_hours'], charging_segments=sum(m >= 0 for m in d['modes']),
               regions_used=len({m for m in d['modes'] if m >= 0}), revisit_regions=revisits(d['modes']))
    try:
        cert = cc.certify(d)
    except ValueError as e:
        row.update(status='not_applicable', reason=str(e)); rows.append(row); continue
    fails = [f for c in cert['carriers'] for f in c['failures']]
    region = [f for f in fails if f['kind'] == 'outside_region']
    assert all(f['kind'] in ('unreachable', 'outside_region') for f in fails), fails
    assert all(f['excess_km'] <= 1e-6 for f in region), region  # returned points were accepted at 1e-6
    fails = [f for f in fails if f['kind'] == 'unreachable']
    if cert['feasible']:
        cc.check_constructed(d, cert)
    worst = max(fails, key=lambda f: f['excess_km'], default=None)
    worst_region = next((c['region'] for c in cert['carriers'] for f in c['failures'] if f is worst), None)
    row.update(status='carrier_late' if fails else ('feasible' if cert['feasible'] else 'region_tolerance_only'),
               failing_pairs=len(fails), region_excess_km=max((f['excess_km'] for f in region), default=0.),
               failing_regions=sorted({c['region'] for c in cert['carriers'] if any(f['kind'] == 'unreachable' for f in c['failures'])}),
               max_excess_km=worst['excess_km'] if worst else 0., worst_region=worst_region,
               worst_pair=None if worst is None else [worst['start_stamp'], worst['end_stamp']],
               worst_required_seconds=worst and worst['required_seconds'],
               worst_available_seconds=worst and worst['available_seconds'])
    rows.append(row)
    certs[p['case']] = cert

def tally(group):
    return dict(points=len(group), with_charging=sum(r['charging_segments'] > 0 for r in group),
                with_revisit=sum(bool(r['revisit_regions']) for r in group),
                carrier_late=sum(r['status'] == 'carrier_late' for r in group),
                region_tolerance_only=sum(r['status'] == 'region_tolerance_only' for r in group),
                not_applicable=sum(r['status'] == 'not_applicable' for r in group))

late = [r for r in rows if r['status'] == 'carrier_late']
ex = [r['max_excess_km'] for r in late]
summary = dict(date='2026-11-18', source_index_sha256=sha(HERE/'source-index.json'), new_solves=0,
               all=tally(rows),
               by_tau={t: tally([r for r in rows if r['tau'] == t]) for t in range(1, 10)},
               by_route={k: tally([r for r in rows if r['route'] == k]) for k in ('G', 'fallback')},
               by_origin={k: tally([r for r in rows if r['origin'] == k]) for k in sorted({r['origin'] for r in rows})},
               late_without_revisit=sum(not r['revisit_regions'] for r in late),
               excess_km=dict(max=max(ex), median=statistics.median(ex), min=min(ex)) if ex else None,
               ratio_required_over_available=dict(max=max(r['worst_required_seconds']/r['worst_available_seconds'] for r in late),
                   median=statistics.median(r['worst_required_seconds']/r['worst_available_seconds'] for r in late)) if late else None,
               experiment2_targets=choose([(r['max_excess_km'], r['case']) for r in late]),
               assumptions=['one independent carrier per disk', 'free initial carrier position in the disk',
                            'modes as stored in the returned point', 'distance tolerance 1e-9 km'])
(HERE/'summary.json').write_text(json.dumps(summary, indent=1))
(HERE/'certificates.json').write_text(json.dumps(certs))
keys = ['case', 'tau', 'origin', 'route', 'selected', 'hours', 'status', 'charging_segments', 'regions_used', 'revisit_regions',
        'failing_pairs', 'region_excess_km', 'failing_regions', 'max_excess_km', 'worst_region', 'worst_pair', 'worst_required_seconds', 'worst_available_seconds']
with open(HERE/'cases.csv', 'w', newline='') as f:
    w = csv.DictWriter(f, keys, extrasaction='ignore'); w.writeheader(); w.writerows(rows)
print(json.dumps({k: summary[k] for k in ('all', 'by_route', 'late_without_revisit', 'excess_km', 'ratio_required_over_available', 'experiment2_targets')}, indent=1))
