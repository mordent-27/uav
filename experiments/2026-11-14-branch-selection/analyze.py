"""Tables and static scientific figure from saved certificates, without solving."""
import csv
import json
import math
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Circle

HERE = Path(__file__).resolve().parent


def totals(d):
    tr = d['solution']
    return dict(objective_hours=sum(tr['s']),
        charging_hours=sum(t for t, m in zip(tr['s'], d['modes']) if m >= 0),
        discharging_hours=sum(t for t, m in zip(tr['s'], d['modes']) if m < 0),
        distance_km=sum(math.dist(a, b) for a, b in zip(tr['r'], tr['r'][1:])),
        charging_segments=sum(m >= 0 for m in d['modes']))


def main():
    summary = json.loads((HERE / 'summary.json').read_text())
    source = json.loads((HERE.parent / '2026-11-14-restoration/geometry.json').read_text())
    best = json.loads((HERE / 'best.json').read_text())
    with (HERE / 'cases.csv').open('w') as handle:
        fields = ['name', 'segment', 'old_region', 'new_region', 'accepted', 'solver_status',
                  'objective', 'improvement_seconds', 'seconds']
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(summary['cases'])
    comparison = dict(source=totals(source), best=totals(best), groups={})
    for label in ['remove', 'region']:
        rows = [r for r in summary['cases'] if (r['new_region'] < 0) == (label == 'remove')]
        accepted = [r for r in rows if r['accepted']]
        comparison['groups'][label] = dict(total=len(rows), accepted=len(accepted),
            improved=sum(r['improvement_seconds'] > 1e-3 for r in accepted),
            best=min(r['objective'] for r in accepted))
    comparison['sum_case_seconds'] = sum(r['seconds'] for r in summary['cases'])
    (HERE / 'comparison.json').write_text(json.dumps(comparison, indent=2) + '\n')
    fig, axes = plt.subplots(1, 2, figsize=(10, 6.5), sharex=True, sharey=True)
    for ax, (d, title) in zip(axes, [(source, 'Original charging choices'), (best, 'One charging segment removed')]):
        for j, region in enumerate(d['instance']['regions']):
            ax.add_patch(Circle(region['o'], region['rho'], facecolor='#eef4fa', edgecolor='#9db6ce', linewidth=1))
            ax.text(region['o'][0], region['o'][1], f'R{j+1}', ha='center', color='#64809c', fontsize=9)
        r = d['solution']['r']
        for k, mode in enumerate(d['modes']):
            x, y = zip(r[k], r[k + 1])
            ax.plot(x, y, color='#226dab' if mode >= 0 else '#6d7075',
                linestyle='--' if mode >= 0 else '-', linewidth=1.9 if mode >= 0 else 1.2)
        # Highlight the entire task-6-to-next-contact subpath, including changed segment 29.
        highlighted = r[28:32]
        x, y = zip(*highlighted)
        ax.plot(x, y, color='#df6a23', linewidth=3, alpha=.85)
        if d is source:
            ax.plot(*zip(r[29], r[30]), color='#226dab', linestyle='--', linewidth=2.6)
        for i, point in enumerate(d['instance']['tasks']):
            ax.scatter(*point, marker='*', s=85, color='#b12f3a', zorder=5)
            ax.annotate(str(i+1), point, xytext=(5, 5), textcoords='offset points', fontsize=9)
        ax.scatter(*d['instance']['r0'], marker='s', s=35, color='black', zorder=5)
        ax.scatter(*d['instance']['rf'], marker='o', s=35, color='black', zorder=5)
        ax.set(title=f'{title}\nT = {sum(d["solution"]["s"]):.6f} h', xlabel='X (km)',
               xlim=(-10.8, 11), ylim=(-11, 9))
        ax.set_aspect('equal')
        ax.grid(alpha=.16)
    axes[0].set_ylabel('Y (km)')
    fig.legend(handles=[Line2D([0], [0], color='#6d7075', label='Discharging'),
                        Line2D([0], [0], color='#226dab', linestyle='--', label='Charging'),
                        Line2D([0], [0], color='#df6a23', linewidth=3, label='Subpath after task 6')],
               loc='lower center', ncol=3, frameon=False, bbox_to_anchor=(.5, .025))
    fig.suptitle('Same N=37, task stamps and physical parameters', fontsize=13, y=.96)
    fig.subplots_adjust(left=.07, right=.99, bottom=.20, top=.80, wspace=.06)
    fig.savefig(HERE / 'branch-comparison.png', dpi=170)
    fig.savefig(HERE / 'branch-comparison.svg')
    plt.close(fig)


if __name__ == '__main__':
    main()
