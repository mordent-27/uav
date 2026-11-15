"""Geometric Index/Nearest screen from saved inputs; no optimization."""
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = HERE.parent/'2026-11-15-r2b-coarse/cases/G'
FAILED = {'tau1-seed2', 'tau5-seed0', 'tau5-seed1', 'tau7-seed0', 'tau7-seed1'}


def order_nearest(inst):
    left, out, at = list(range(len(inst['tasks']))), [], inst['r0']
    while left:
        pos = min(range(len(left)), key=lambda k: math.dist(at, inst['tasks'][left[k]]))
        i = left[pos]
        out.append(i)
        at = inst['tasks'][i]
        left[pos] = left[-1]  # Match Rust swap_remove.
        left.pop()
    return out


def positions(inst, order):
    path = [inst['r0']]
    for i in order:
        task = inst['tasks'][i]
        reg = min(inst['regions'], key=lambda r: math.dist(task, r['o'])-r['rho'])
        delta = [task[k]-reg['o'][k] for k in range(2)]
        length, reach = math.hypot(*delta), .9*reg['rho']
        contact = task if length <= reach else [reg['o'][k]+delta[k]/length*reach for k in range(2)]
        path.extend([contact, contact, task, contact, contact])
    path.append(inst['rf'])
    return path


def main():
    assert not (HERE/'results.json').exists(), 'refuse to overwrite'
    checks = []
    for folder in sorted(BASE.iterdir()):
        source = folder/'solution.json'
        if not source.exists():
            continue
        data = json.loads(source.read_text())
        order = order_nearest(data['instance'])
        a = positions(data['instance'], range(len(order)))
        b = positions(data['instance'], order)
        assert len(a) == len(data['init']['r'])
        error = max(math.dist(x, y) for x, y in zip(a, data['init']['r']))
        assert error < 1e-7
        distance = lambda path: sum(math.dist(x, y) for x, y in zip(path, path[1:]))
        checks.append(dict(name=folder.name, baseline_pass=folder.name not in FAILED,
            nearest_order=order, same_order=order == list(range(len(order))),
            index_initial_km=distance(a), nearest_initial_km=distance(b),
            index_reconstruction_max_error_km=error, source=str(source.relative_to(ROOT)),
            source_sha256=hashlib.sha256(source.read_bytes()).hexdigest()))
    assert len(checks) == 13 and sum(r['baseline_pass'] for r in checks) == 8
    result = dict(date='2026-11-15', base_commit='be587e1', new_solves=False,
        note='Geometry from rounded JSON; verify actual Rust Nearest full initial state before solving.',
        unchanged=[r['name'] for r in checks if r['same_order']], cases=checks)
    (HERE/'results.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(dict(cases=len(checks), unchanged=result['unchanged'], new_solves=False)))


if __name__ == '__main__':
    main()
