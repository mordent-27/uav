"""Show the initial and final trajectory and the per-stage residuals of a `uav solve --out` JSON."""
import json
import sys

d = json.load(open(sys.argv[1]))


def show(t, name):
    r, e, s, c = t['r'], t['e'], t['s'], t['c']
    print(f'{name}: total {sum(s):.4f} h')
    print('   k       x       y      e     s[s]    c[s]')
    for k in range(len(s)):
        print(f'  {k:2d} {r[k][0]:7.3f} {r[k][1]:7.3f} {e[k]:6.3f} {s[k]*3600:8.1f} {c[k]*3600:7.2f}')


show(d['init'], 'initial trajectory')
show(d['solution'], 'final trajectory')
print('final modes (-1 discharge, j charge in region j):', d['modes'])
print('stage: eps p objective[h] stat feas original-violation')
for st in d['stages']:
    print(f'  {st["eps"]:.4f} {st["p"]:5.2f} {st["f"]:.4f} {st["stat"]:.1e} {st["feas"]:.1e} {st["viol"]:.1e}')
