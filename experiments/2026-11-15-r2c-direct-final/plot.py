"""Plot saved paired outcomes; missing feasible outputs are not assigned zero cost."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
data = json.loads((HERE/'summary.json').read_text())['cases']
fig, (ax, bx) = plt.subplots(1, 2, figsize=(11, 4), constrained_layout=True)
for i, row in enumerate(data):
    ax.bar(i+.17, row['restored_hours'], .32, color='#2379a4', label='Direct final NLP' if i == 0 else None)
    old = row['baseline_restored_hours']
    if old is not None:
        ax.bar(i-.17, old, .32, color='#d68c3a', label='Coarse path G' if i == 4 else None)
    else:
        ax.text(i-.17, .15, 'failed', rotation=90, ha='center', fontsize=9, color='#845019')
ax.set_xticks(range(6), [r['case'] for r in data], rotation=40, ha='right')
ax.set_ylabel('Mission time after physical restoration (h)')
ax.set_title('4 failures rescued; 2 controls become slower')
ax.legend(fontsize=9)
for i, row in enumerate(data):
    bx.bar(i-.17, row['baseline_charges'], .32, color='#d68c3a')
    bx.bar(i+.17, row['direct_charges'], .32, color='#2379a4')
bx.set_xticks(range(6), [r['case'] for r in data], rotation=40, ha='right')
bx.set_ylabel('Charging segments at final smoothed point')
bx.set_title('Direct start retains all initial mode assignments')
fig.savefig(HERE/'comparison.png', dpi=160)
