"""Fix the 894 returned points (path + sha256) before reading any carrier result."""
import json
from common import COHORT, ROOT, HERE, read, sha

summary = read(COHORT/'summary.json')
rows = []
for r in summary['cases']:
    if not r.get('physical_point_available'):
        continue
    base = ROOT/'experiments'/r['origin']
    path = base/'runs'/r['case']/'selected.json'
    outcome = read(base/'runs'/r['case']/'result.json')['outcome']
    digest = sha(path)
    assert digest == outcome['selected_sha256'], r['case']
    rows.append(dict(case=r['case'], origin=r['origin'], route=r['route'], selected=r['selected'],
                     selected_hours=r['selected_hours'], path=str(path.relative_to(ROOT)), sha256=digest))
assert len(rows) == 894, len(rows)
(HERE/'source-index.json').write_text(json.dumps(dict(summary_sha256=sha(COHORT/'summary.json'), points=rows), indent=1))
print(len(rows), 'points indexed')
