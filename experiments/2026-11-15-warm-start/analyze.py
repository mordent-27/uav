"""Saved-point comparison, physical-prefix certificates and standalone figures."""
import csv
import gzip
import json
import math
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import controls as c


def prefix_certificate(doc):
    first = next((k for k, mode in enumerate(doc['modes']) if mode >= 0), len(doc['modes']))
    tasks = sorted((stamp, index) for index, stamp in enumerate(doc['task_stamp']) if stamp <= first)
    points = [doc['instance']['r0']] + [doc['instance']['tasks'][index] for stamp, index in tasks]
    distance = sum(math.dist(a, b) for a, b in zip(points, points[1:]))
    p = doc['phys']
    capacity = p['v_d']*(p['e_max']-p['e_min'])/p['zeta']
    return dict(first_charging_segment=first, prefix_tasks=[index for stamp, index in tasks],
        prefix_task_stamps=[stamp for stamp, index in tasks], distance_lower_bound_km=distance,
        battery_range_km=capacity, excess_km=distance-capacity, infeasible=distance > capacity,
        scope='fixed pure modes and task stamps, exact task restoration; not the full problem')


def read_lines(path):
    with gzip.open(path, 'rt') as handle:
        return [json.loads(line) for line in handle]


def main():
    rows, proofs = [], {}
    sources = [(path, False) for path in sorted((c.HERE / 'runs').glob('*'))]
    sources += [(c.HERE.parent / '2026-11-15-library-trace/runs' / backend, True) for backend in c.tr.BACKENDS]
    for path, reused in sources:
        data = json.loads((path / 'result.json').read_text())
        doc = json.loads((path / 'solution.json').read_text())
        default = reused or '-default-' in path.name
        route = 'homotopy' if reused else ('direct' if path.name.endswith('direct') else 'homotopy')
        backend = path.name if reused else path.name.removesuffix('-direct').removesuffix('-homotopy').removesuffix('-default')
        restored_path = c.HERE / 'restored' / path.name / 'result.json'
        restored = json.loads(restored_path.read_text()) if restored_path.exists() and not reused else None
        row = dict(name=('previous-' if reused else '')+path.name, seed='default' if default else 'good', route=route,
            backend=backend, objective=data['objective'], stat=data['original_kkt']['stat'], feas=data['original_kkt']['feas'],
            kkt=data['kkt_converged'], minimum_energy=data['selection']['audit']['pure_mode_min_energy'],
            seconds=data['seconds'], outer=data['outer_total'], source_reused=reused,
            restored_accepted=restored['accepted'] if restored else None,
            restored_objective=restored.get('objective') if restored else None)
        rows.append(row)
        proofs[row['name']] = prefix_certificate(doc)
    continuations = []
    for name in ['newton', 'newton-default']:
        if not (c.HERE / name / 'result.json').exists():
            continue
        result = json.loads((c.HERE / name / 'result.json').read_text())
        restored = json.loads((c.HERE / 'restored' / name / 'result.json').read_text())
        continuations.append(dict(name=name, objective=result['objective'], original_kkt=result['original_kkt'],
            kkt=result['kkt_converged'], extra_outer=result['outer_total'], total_outer=result['total_outer'],
            seconds=result['seconds'], total_seconds=result['total_seconds'],
            minimum_energy=result['selection']['audit']['pure_mode_min_energy'],
            restored_objective=restored.get('objective'), restored_accepted=restored['accepted']))
    with (c.HERE / 'comparison.csv').open('w') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)
    # The old default homotopy and additional default direct controls use the same initializer.
    m = c.tr.Model(0, 0, c.tr.LIBRARIES['normalized'])
    for backend in c.tr.BACKENDS:
        a = json.loads((c.HERE.parent / '2026-11-15-library-trace/runs' / backend / 'initial.json').read_text())
        b = json.loads((c.HERE / 'runs' / (backend+'-default-direct') / 'initial.json').read_text())
        np.testing.assert_allclose(a['y'], b['y'], rtol=1e-15, atol=1e-14)
        assert a['lam'] == b['lam'] and a['mu'] == b['mu'] and a['rho'] == b['rho']
    m.close()
    c.tr.write(c.HERE / 'prefix-certificates.json', proofs)
    c.tr.write(c.HERE / 'summary.json', dict(runs=rows, continuations=continuations,
        shared_default_initial_state_verified=True, paper_algorithm_reproduced=False))
    fig, axes = plt.subplots(2, 2, figsize=(11, 8))
    groups = [('default', 'homotopy', 'Original seed / 13 stages', '#3778b7'),
              ('default', 'direct', 'Original seed / final only', '#dd8836'),
              ('good', 'homotopy', 'Good seed / 13 stages', '#c65160'),
              ('good', 'direct', 'Good seed / final only', '#3f9b75')]
    for seed, route, label, color in groups:
        group = [next(row for row in rows if row['seed'] == seed and row['route'] == route and row['backend'] == backend)
                 for backend in c.tr.BACKENDS]
        x = np.arange(3)
        for ax, key in [(axes[0, 0], 'objective'), (axes[0, 1], 'minimum_energy'),
                        (axes[1, 0], 'stat'), (axes[1, 1], 'feas')]:
            ax.plot(x, [row[key] for row in group], '.-', label=label, color=color)
    axes[0, 0].set(title='Raw objective before physical restoration', ylabel='Mission time (h)')
    axes[0, 1].set(title='Battery replay after pure-mode selection', ylabel='Minimum battery fraction')
    axes[0, 1].axhline(0., linestyle=':', color='black', linewidth=1)
    for ax, title in [(axes[1, 0], 'Original stationarity residual'), (axes[1, 1], 'Original feasibility residual')]:
        ax.set(title=title, ylabel='Infinity norm', yscale='log')
        ax.axhline(1e-6, linestyle=':', color='black', linewidth=1)
    for ax in axes.ravel():
        ax.set_xticks(np.arange(3), ['Rust L-BFGS', 'SciPy L-BFGS-B', 'SciPy BFGS'])
        ax.tick_params(axis='x', labelsize=9)
        ax.grid(alpha=.18)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='lower center', ncol=2, frameon=False, bbox_to_anchor=(.5, .015))
    fig.suptitle('Same input, N=37 and AL settings: initializer and homotopy route both matter\nAll 12 quasi-Newton final points fail KKT within the common 150-outer budget', fontsize=12, y=.98)
    fig.subplots_adjust(left=.085, right=.98, bottom=.17, top=.86, hspace=.40, wspace=.28)
    fig.savefig(c.HERE / 'warmstart-comparison.png', dpi=170)
    fig.savefig(c.HERE / 'warmstart-comparison.svg')
    plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.5))
    for name, case, label, color in [('newton', 'scipy-bfgs-direct', 'Good seed', '#3f9b75'),
                                     ('newton-default', 'scipy-bfgs-default-direct', 'Original seed', '#dd8836')]:
        if not (c.HERE / name / 'outer.jsonl.gz').exists():
            continue
        parent = read_lines(c.HERE / 'runs' / case / 'outer.jsonl.gz')
        extra = read_lines(c.HERE / name / 'outer.jsonl.gz')
        points = parent+extra
        x = list(range(1, len(points)+1))
        axes[0].semilogy(x, [p['original_kkt']['feas'] for p in points], color=color, label=label)
        axes[1].semilogy(x, [p['original_kkt']['stat'] for p in points], color=color, label=label)
    for ax, title in zip(axes, ['Original feasibility residual', 'Original stationarity residual']):
        ax.set(title=title, xlabel='Total outer iterations', ylabel='Infinity norm')
        ax.axhline(1e-6, linestyle=':', color='black', linewidth=1)
        ax.axvline(150, linestyle='--', color='gray', linewidth=1)
        ax.grid(alpha=.18)
    axes[0].legend()
    fig.suptitle('BFGS to 150 outer iterations; then the prescribed Newton continuation', fontsize=12, y=.97)
    fig.subplots_adjust(left=.08, right=.98, bottom=.15, top=.82, wspace=.25)
    fig.savefig(c.HERE / 'continuation.png', dpi=170)
    fig.savefig(c.HERE / 'continuation.svg')
    plt.close(fig)
    print(json.dumps(dict(runs=rows, continuations=continuations), indent=2))


if __name__ == '__main__':
    main()
