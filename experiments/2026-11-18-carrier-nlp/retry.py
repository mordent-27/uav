"""PLAN.md addendum 2: tau7-seed7000053 without carrier, started from the accepted carrier solution."""
import json
from solve import Branch, HERE

case = 'tau7-seed7000053'
out = HERE/'runs'/case
start = json.loads((out/'carrier.json').read_text())
assert json.loads((HERE/'results.json').read_text())[-1]['carrier']['accepted']
target = out/'base-from-carrier.json'
assert not target.exists()
sol, res, raw = Branch(start, False).solve()
target.write_text(json.dumps(sol, indent=1, allow_nan=False)+'\n')
(out/'base-from-carrier-solver.json').write_text(json.dumps(raw, allow_nan=False)+'\n')
(out/'base-from-carrier-result.json').write_text(json.dumps(res, indent=1, allow_nan=False)+'\n')
print(json.dumps(res, indent=1))
