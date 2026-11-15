"""Saved-point summaries; distinguish incomplete runs from final-NLP outcomes."""
import csv
import json
import math

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import numpy as np
import run as r


def prefix(doc):
    first = next((k for k, mode in enumerate(doc['modes']) if mode >= 0), len(doc['modes']))
    tasks = sorted((stamp, i) for i, stamp in enumerate(doc['task_stamp']) if stamp <= first)
    points = [doc['instance']['r0']]+[doc['instance']['tasks'][i] for stamp, i in tasks]
    distance = sum(math.dist(a, b) for a, b in zip(points, points[1:]))
    ph = doc['phys']
    capacity = ph['v_d']*(ph['e_max']-ph['e_min'])/ph['zeta']
    return dict(first_charging_segment=first, prefix_tasks=[i for stamp, i in tasks],
        prefix_stamps=[stamp for stamp, i in tasks], lower_distance_km=distance, range_km=capacity,
        infeasible=bool(distance > capacity), scope='fixed pure modes/task stamps after exact task restoration')


def main():
    rows, documents, proofs = [], {}, {}
    for kind in ['N', 'R', 'Q', 'U']:
        for budget in ['short', 'expanded']:
            name = kind+'-'+budget
            folder = r.HERE/'cases'/name
            d = json.loads((folder/'result.json').read_text())
            documents[name] = d
            audit = d['selection']['audit']
            row = dict(case=name, last_stage=d['stage'], stop=d['stop'], completed_schedule=d['completed_schedule'],
                passed_stages=d['passed_stages'], total_outer=d['total_outer'], seconds=d['seconds'],
                last_objective=d['objective'], common_stat=d['common_kkt']['stat'], common_feas=d['common_kkt']['feas'],
                physical_stat=d['paper_units_kkt']['stat'], physical_feas=d['paper_units_kkt']['feas'],
                final_kkt_pass=d['final_kkt_pass'] if d['completed_schedule'] else None,
                original_violation=audit['original_residuals']['viol'],
                pure_min_energy=audit.get('pure_mode_min_energy'),
                final_objective=d['objective'] if d['completed_schedule'] else None)
            rows.append(row)
            if d['completed_schedule']:
                proof = prefix(json.loads((folder/'solution.json').read_text()))
                proofs[name] = proof
    with (r.HERE/'comparison.csv').open('w') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)
    r.tr.write(r.HERE/'summary.json', dict(cases=rows, final_branch_prefix_checks=proofs,
        final_comparisons_exclude_timeouts=True, author_settings_identified=False))
    fig, ax = plt.subplots(figsize=(10.5, 5.2))
    colors = {'passed': '#85bf9d', 'limit': '#de9699', 'timeout': '#e7c278', 'missing': '#ededed'}
    for i, (name, doc) in enumerate(documents.items()):
        for stage in range(1, 14):
            found = next((s for s in doc['stages'] if s['stage'] == stage), None)
            status = 'missing' if found is None else ('passed' if found['common_kkt_pass'] else 'limit')
            if found and doc['stop'] == 'timeout' and stage == doc['stage']:
                status = 'timeout'
            ax.add_patch(plt.Rectangle((stage-.5, i-.5), 1, 1, facecolor=colors[status], edgecolor='white'))
            if found:
                ax.text(stage, i, str(found['completed_outer']), ha='center', va='center', fontsize=8)
    ax.set(xlim=(.5, 13.5), ylim=(7.5, -.5), xlabel='Homotopy stage', title='Numbers: completed outer iterations; colors: common-coordinate KKT outcome')
    ax.set_xticks(range(1, 14))
    ax.set_yticks(range(8), list(documents))
    fig.legend(handles=[Patch(color=colors[k], label=label) for k, label in
        [('passed', 'KKT reached'), ('limit', 'Stage budget exhausted'), ('timeout', 'Run time limit'), ('missing', 'Not reached')]],
        loc='lower center', ncol=4, frameon=False, fontsize=9, bbox_to_anchor=(.5, .015))
    fig.suptitle('Same physical seed and model: scaling and stage budgets', fontsize=13, y=.98)
    fig.subplots_adjust(left=.15, right=.98, bottom=.20, top=.84)
    fig.savefig(r.HERE/'stage-status.png', dpi=170)
    fig.savefig(r.HERE/'stage-status.svg')
    plt.close(fig)
    fig, axes = plt.subplots(2, 2, figsize=(11, 8))
    for kind, color in zip(['N', 'R', 'Q', 'U'], ['#3579b4', '#dd8938', '#4f9d73', '#a765a5']):
        for budget, style in [('short', '--'), ('expanded', '-')]:
            doc = documents[kind+'-'+budget]
            states = [json.loads((r.HERE/'cases'/(kind+'-'+budget)/f'stage{s:02d}-end.json').read_text()) for s in range(1, doc['stage']+1)]
            x = [s['stage'] for s in states]
            label = kind+' / '+budget
            axes[0, 0].semilogy(x, [s['common_kkt']['feas'] for s in states], style, color=color, label=label)
            axes[0, 1].semilogy(x, [s['common_kkt']['stat'] for s in states], style, color=color)
            axes[1, 0].plot(x, [s['objective'] for s in states], style, color=color)
            axes[1, 1].plot(x, [s['selection']['audit'].get('pure_mode_min_energy', math.nan) for s in states], style, color=color)
    for ax, title, ylabel in [(axes[0, 0], 'Common feasibility', 'Infinity norm'),
        (axes[0, 1], 'Common stationarity', 'Infinity norm'),
        (axes[1, 0], 'Objective before physical restoration', 'Mission time (h)'),
        (axes[1, 1], 'Pure-mode battery replay', 'Minimum battery fraction')]:
        ax.set(title=title, ylabel=ylabel, xlabel='Homotopy stage', xlim=(1, 13))
        ax.set_xticks([1, 3, 5, 7, 9, 11, 13])
        ax.grid(alpha=.18)
    for ax in axes[0]:
        ax.axhline(1e-6, linestyle=':', color='black', linewidth=1)
    axes[1, 1].axhline(0., linestyle=':', color='black', linewidth=1)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='lower center', ncol=4, frameon=False, fontsize=9, bbox_to_anchor=(.5, .01))
    fig.suptitle('Stage endpoints; incomplete runs stop at their last reached stage', fontsize=13, y=.98)
    fig.subplots_adjust(left=.085, right=.98, bottom=.17, top=.88, wspace=.28, hspace=.40)
    fig.savefig(r.HERE/'stage-trace.png', dpi=170)
    fig.savefig(r.HERE/'stage-trace.svg')
    plt.close(fig)
    print(json.dumps(rows, indent=2))


if __name__ == '__main__':
    main()
