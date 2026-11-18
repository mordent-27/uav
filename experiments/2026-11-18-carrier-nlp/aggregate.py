"""Table for REPORT.md from results.json and the single retry."""
import json
from pathlib import Path
HERE = Path(__file__).resolve().parent
rows = json.loads((HERE/'results.json').read_text())
retry = json.loads((HERE/'runs/tau7-seed7000053/base-from-carrier-result.json').read_text())
out = []
for r in rows:
    b, c = r['base'], r['carrier']
    item = dict(case=r['case'], returned_hours=r['returned_sum_s_hours'], base_accepted=b['accepted'], base_hours=b['objective_hours'],
                base_late_km=b['certify_unreachable_max_km'], carrier_accepted=c['accepted'], carrier_hours=c['objective_hours'],
                carrier_status=c['solver_status'], carrier_iterations=c['iterations'], base_status=b['solver_status'], base_iterations=b['iterations'],
                carrier_kkt=c['kkt'], base_kkt=b['kkt'])
    if b['accepted'] and c['accepted']:
        item['increase_seconds'] = 3600*(c['objective_hours']-b['objective_hours'])
        item['increase_percent'] = 100*(c['objective_hours']/b['objective_hours']-1)
    if c['accepted']:
        item['carrier_minus_returned_seconds'] = 3600*(c['objective_hours']-r['returned_sum_s_hours'])
    out.append(item)
summary = dict(cases=out, retry_tau7_base_from_carrier=dict(accepted=retry['accepted'], status=retry['solver_status'],
               hours=retry['objective_hours'], kkt=retry['kkt']))
(HERE/'summary.json').write_text(json.dumps(summary, indent=1)+'\n')
for i in out:
    print(i['case'], '%.6f' % i['returned_hours'], i['base_accepted'], '%.6f' % i['base_hours'], '%.3f' % i['base_late_km'],
          i['carrier_accepted'], '%.6f' % i['carrier_hours'], i.get('increase_seconds'), i.get('increase_percent'), i.get('carrier_minus_returned_seconds'),
          i['base_iterations'], i['carrier_iterations'])
