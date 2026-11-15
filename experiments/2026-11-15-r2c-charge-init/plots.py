"""Static scientific figures from saved initialization and stage records."""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent


def main():
    summary = json.loads((HERE/'summary.json').read_text())
    structure = json.loads((HERE/'structure.json').read_text())
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    rows = summary['rows']
    x = np.arange(len(rows))
    axes[0].bar(x-.18, [r['initialization']['initial_objective'] for r in rows], width=.36, label='Original initial trajectory')
    axes[0].bar(x+.18, [r['initialization']['objective'] for r in rows], width=.36, label='Fixed-geometry charge initialization')
    axes[0].set_xticks(x, [r['name'].replace('-seed', '/s') for r in rows], rotation=65, ha='right', fontsize=8)
    axes[0].set_ylabel('Initial mission time (hours)')
    axes[0].legend(fontsize=8)
    row = next(r for r in structure if r['case'] == 'tau1-seed2')
    for kind, style in [('baseline', '-o'), ('changed', '--s')]:
        axes[1].semilogy([r['stage'] for r in row[kind]],
            [max(r['max_original_charge_derivative_share'], 1e-300) for r in row[kind]], style, label=kind)
    axes[1].set_xlabel('Stage (0 = original initialization)')
    axes[1].set_ylabel('Largest derivative share at original charge candidates')
    axes[1].set_title('tau1/seed2: charging candidates lose influence')
    axes[1].legend()
    for ax in axes:
        ax.grid(axis='y', alpha=.25)
    fig.tight_layout()
    fig.savefig(HERE/'initialization-structure.png', dpi=180)
    plt.close(fig)


if __name__ == '__main__':
    main()
