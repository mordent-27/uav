import csv
import json
import os
from pathlib import Path
os.environ.setdefault('MPLCONFIGDIR', '/tmp/uav-stage-matplotlib')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

BASE = Path(__file__).resolve().parent
summary = json.loads((BASE / 'summary.json').read_text())
with (BASE / 'cases.csv').open() as stream:
    rows = list(csv.DictReader(stream))
fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), layout='constrained')
ax = axes[0]
for key, label, color, style in [('original_h', 'Original (includes infeasible)', '#999999', '--'),
                                ('baseline_h', 'Best feasible pre-AL candidate', '#dd9900', '-'),
                                ('returned_h', 'Returned feasible point', '#0077bb', '-')]:
    ax.plot(range(1, 10), [g['stages'][key]['median'] for g in summary['groups']],
            marker='o', label=label, color=color, linestyle=style)
ax.plot(range(1, 10), [g['paper_median_h'] for g in summary['groups']], marker='s',
        label='Paper NLP (different inputs)', color='#228833')
ax.set(xlabel='Number of tasks', ylabel='Median mission time [h]', xticks=range(1, 10),
       title='Medians; available sets differ by stage')
ax.legend(fontsize=8); ax.grid(alpha=.2)
ax = axes[1]
for route, color in [('G', '#ee7733'), ('fallback', '#0077bb')]:
    sub = [r for r in rows if r['route'] == route and r['baseline_h'] and r['returned_h']]
    ax.scatter([float(r['baseline_h']) for r in sub], [float(r['returned_h']) for r in sub],
               s=13, alpha=.45, color=color, label=f'{route}, n={len(sub)}')
limits = [0, max(float(r[k]) for r in rows for k in ['baseline_h', 'returned_h'] if r[k]) * 1.02]
ax.plot(limits, limits, color='black', linewidth=1, linestyle='--', label='Same mission time')
ax.set(xlim=limits, ylim=limits, xlabel='Best feasible pre-AL candidate [h]', ylabel='Returned point [h]',
       title='Paired feasible points; below line = shorter')
ax.set_aspect('equal', adjustable='box'); ax.legend(fontsize=8); ax.grid(alpha=.2)
fig.savefig(BASE / 'stage-objectives.png', dpi=180)
fig.savefig(BASE / 'stage-objectives.pdf')
plt.close(fig)
print('stage-objectives.png, stage-objectives.pdf')
