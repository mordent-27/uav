"""How far the index and nearest orders are from the shortest visiting order (straight legs only).

Geometry of the 900 instances, no solve. Exact shortest order by dynamic programming over subsets.
Standard library only. Writes route-slack.json.
"""
import json
import math
from pathlib import Path
from statistics import median

HERE = Path(__file__).resolve().parent


def shortest(inst):
    tasks, n = inst['tasks'], len(inst['tasks'])
    d = [[math.dist(a, b) for b in tasks] for a in tasks]
    best = {(1 << i, i): math.dist(inst['r0'], tasks[i]) for i in range(n)}
    for mask in range(1, 1 << n):
        for last in range(n):
            if (mask, last) not in best:
                continue
            value = best[(mask, last)]
            for nxt in range(n):
                if not mask & (1 << nxt):
                    key = (mask | (1 << nxt), nxt)
                    cand = value+d[last][nxt]
                    if cand < best.get(key, math.inf):
                        best[key] = cand
    full = (1 << n)-1
    return min(best[(full, i)]+math.dist(tasks[i], inst['rf']) for i in range(n))


def nearest_order(inst):
    left, at, out = list(range(len(inst['tasks']))), inst['r0'], []
    while left:
        i = min(left, key=lambda j: math.dist(at, inst['tasks'][j]))
        left.remove(i)
        at = inst['tasks'][i]
        out.append(i)
    return out


def route(inst, order):
    points = [inst['r0']]+[inst['tasks'][i] for i in order]+[inst['rf']]
    return sum(math.dist(a, b) for a, b in zip(points, points[1:]))


def main():
    rows = []
    for tau in range(1, 10):
        index, near = [], []
        for run in range(100):
            inst = json.loads((HERE/'mc-nearest/cases'/f'tau{tau}'/f'run{run:03d}'/'raw.json').read_text())['instance']
            best = shortest(inst)
            index.append(route(inst, range(tau))/best)
            near.append(route(inst, nearest_order(inst))/best)
        rows.append(dict(tau=tau, index_over_best_median=median(index), nearest_over_best_median=median(near),
                         nearest_is_best=sum(v < 1+1e-12 for v in near), index_is_best=sum(v < 1+1e-12 for v in index),
                         nearest_over_best_max=max(near)))
        print(rows[-1], flush=True)
    (HERE/'route-slack.json').write_text(json.dumps(rows, indent=2)+'\n')


if __name__ == '__main__':
    main()
