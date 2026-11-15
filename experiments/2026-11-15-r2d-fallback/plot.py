"""Plot the fixed policy outcomes without omitting failures."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
summary = json.loads((HERE/'summary.json').read_text())
fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), constrained_layout=True)
for ax, key, label in zip(axes, ['regression_cases', 'diagnostic_holdout_cases'],
        ['13 design/regression cases', 'One held-out seed: 4 nested problem sizes']):
    rows = summary[key]
    for i, row in enumerate(rows):
        if row['accepted']:
            ax.bar(i, row['selected_hours'], color='#287ca5' if row['selected_phase'] == 'G' else '#d18b32')
        else:
            ax.text(i, .15, 'failed', rotation=90, ha='center')
    ax.set_xticks(range(len(rows)), [r['case'] for r in rows], rotation=60, ha='right', fontsize=8)
    ax.set_ylabel('Adopted feasible mission time (h)')
    ax.set_title(label)
    ax.set_ylim(bottom=0)
    ax.set_xlim(-.6, len(rows)-.4)
from matplotlib.patches import Patch
fig.legend(handles=[Patch(color='#287ca5', label='G accepted: keep G'),
                    Patch(color='#d18b32', label='G failed: direct start accepted')],
           loc='upper center', bbox_to_anchor=(.5, 1.09), ncol=2, frameon=False)
fig.savefig(HERE/'policy-results.png', dpi=160, bbox_inches='tight')
