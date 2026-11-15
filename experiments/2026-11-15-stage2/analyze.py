"""Saved result tables and static scientific figures, with initial-state metadata repaired."""
import csv
import gzip
import json

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import common as c


def read_rows(folder):
    with gzip.open(folder/'outer.jsonl.gz', 'rt') as f:
        return [json.loads(line) for line in f]


def main():
    names = ['fixed-bfgs', 'fixed-newton', 'raised-bfgs', 'adaptive-bfgs', 'guarded-bfgs']
    folders = [c.HERE/'cases'/name for name in names]
    folders += [p for p in [c.HERE/'follow', c.HERE/'follow-guarded'] if (p/'result.json').exists()]
    m, summary = c.model(), []
    for folder in folders:
        result = json.loads((folder/'result.json').read_text())
        initial = json.loads((folder/'initial.json').read_text())
        doc = json.loads((folder/'solution.json').read_text())
        # The bridge exports Rust's default initializer; these are continuations.
        # Correct only init metadata to the actual saved start; do not change the solution.
        doc['init'] = c.fidelity.tr.decode(m, np.array(initial['y']), m.source)
        doc['metrics']['init_objective'] = sum(doc['init']['s'])
        c.write(folder/'solution.json', doc)
        rows = read_rows(folder)
        summary.append(dict(name=folder.name, stage=result['stage'], stop=result['stop'],
            extra_outer=result['additional_outer'], seconds=result['seconds'], rho=result['rho'],
            target_kkt_pass=result['target_kkt_pass'], final_kkt_pass=result['final_kkt_pass'],
            objective=result['objective'], stat=result['common_kkt']['stat'], feas=result['common_kkt']['feas'],
            comp=result['common_kkt']['comp'], physical_stat=result['paper_units_kkt']['stat'],
            physical_feas=result['paper_units_kkt']['feas'],
            inner_gradient_pass=sum(row['inner']['gradient_pass'] for row in rows),
            inner_evaluations=sum(row['inner']['evaluations'] for row in rows)))
    m.close()
    with (c.HERE/'comparison.csv').open('w') as f:
        w = csv.DictWriter(f, fieldnames=list(summary[0]), lineterminator='\n')
        w.writeheader()
        w.writerows(summary)
    c.write(c.HERE/'summary.json', dict(results=summary, paper_reproduction=False,
        physical_restoration_performed=False, init_metadata='actual saved starting points; solution arrays unchanged'))
    fig, axes = plt.subplots(2, 2, figsize=(11, 8))
    for name, label, color in zip(names, ['Fixed / BFGS', 'Fixed / Newton', 'One rho increase', 'Adaptive', 'Guarded adaptive'],
                                  ['#357bb6', '#a56ab1', '#d88b3b', '#c85b65', '#38966e']):
        rows = read_rows(c.HERE/'cases'/name)
        x = [row['extra_outer'] for row in rows]
        axes[0, 0].loglog(x, [row['common_kkt']['feas'] for row in rows], color=color, label=label)
        axes[0, 1].loglog(x, [max(1e-18, row['common_kkt']['stat']) for row in rows], color=color)
        axes[1, 0].loglog(x, [row['rho'] for row in rows], color=color)
        axes[1, 1].loglog(x, [max(1e-18, row['inner']['gradient_inf']) for row in rows], color=color)
    for ax, title in zip(axes.ravel(), ['Common feasibility', 'Common stationarity', 'Penalty used by inner solve', 'Inner AL gradient infinity norm']):
        ax.set(title=title, xlabel='Additional outer iterations')
        ax.grid(alpha=.18)
    for ax in axes[0]:
        ax.axhline(1e-6, linestyle=':', color='black', linewidth=1)
    axes[1, 1].axhline(1e-8, linestyle=':', color='black', linewidth=1)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='lower center', ncol=3, frameon=False, fontsize=9, bbox_to_anchor=(.5, .01))
    fig.suptitle('Same saved stage-2 state: inner method and penalty updates', y=.98, fontsize=13)
    fig.subplots_adjust(left=.085, right=.98, bottom=.17, top=.88, hspace=.40, wspace=.26)
    fig.savefig(c.HERE/'continuation.png', dpi=170)
    fig.savefig(c.HERE/'continuation.svg')
    plt.close(fig)
    spectra = json.loads((c.HERE/'curvature.json').read_text())
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.8))
    for target, label, color in [('solved', 'AL actually minimized', '#357bb6'), ('next', 'AL after multiplier update', '#d88b3b')]:
        data = sorted([row for row in spectra if row['target'] == target], key=lambda row: row['step'])
        axes[0].semilogx([row['step'] for row in data], [row['minimum_eigenvalue'] for row in data], '.-', label=label, color=color)
    axes[0].set(yscale='symlog', title='FD minimum eigenvalue depends on step', xlabel='Gradient-difference step', ylabel='Minimum eigenvalue')
    axes[0].set_yscale('symlog', linthresh=1e-3)
    axes[0].legend(fontsize=8)
    for step, color in [(1e-6, '#d88b3b'), (1e-7, '#357bb6')]:
        row = next(row for row in spectra if row['target'] == 'solved' and row['step'] == step)
        axes[1].loglog([s['distance'] for s in row['samples']], [s['centered_delta'] for s in row['samples']], '.-', color=color, label=f'FD step {step:g}')
    axes[1].set(title='Symmetric AL value change along tested directions', xlabel='Direction step', ylabel='(AL(y+tv)+AL(y-tv))/2 - AL(y)')
    axes[1].legend(fontsize=8)
    for ax in axes:
        ax.grid(alpha=.18)
    fig.subplots_adjust(left=.085, right=.98, bottom=.17, top=.86, wspace=.30)
    fig.savefig(c.HERE/'curvature.png', dpi=170)
    fig.savefig(c.HERE/'curvature.svg')
    plt.close(fig)
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
