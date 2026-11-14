"""Scientific figures and tables from frozen solver traces; no further solves."""
import csv
import gzip
import json
import math
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

import trace as tr


def csv_write(path, rows):
    with path.open('w') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def main():
    data, summary = {}, []
    for backend in tr.BACKENDS:
        folder = tr.HERE / 'runs' / backend
        result = json.loads((folder / 'result.json').read_text())
        ends = [json.loads((folder / f'stage{stage:02d}-end.json').read_text()) for stage in range(1, result['stage']+1)]
        with gzip.open(folder / 'outer.jsonl.gz', 'rt') as handle:
            rows = [json.loads(line) for line in handle]
        data[backend] = ends
        summary.append(dict(backend=backend, stage=result['stage'], objective=result['objective'],
            kkt=result['kkt_converged'], stat=result['original_kkt']['stat'], feas=result['original_kkt']['feas'],
            original_violation=result['selection']['audit']['original_residuals']['viol'],
            pure_mode_min_energy=result['selection']['audit'].get('pure_mode_min_energy'), seconds=result['seconds'],
            inner_gradient_pass=sum(r['inner']['gradient_pass'] for r in rows), outer=result['outer_total'],
            evaluations=sum(r['inner']['evaluations'] for r in rows),
            last_mode29=result['selection']['modes'][29]['winner']))
    csv_write(tr.HERE / 'runs.csv', summary)
    probe_rows = [{key: row[key] for key in ['representation', 'stage', 'backend', 'value', 'gradient_inf',
        'gradient_pass', 'iterations', 'evaluations', 'seconds', 'status']} for row in json.loads((tr.HERE / 'probe-summary.json').read_text()) if not row.get('missing')]
    csv_write(tr.HERE / 'probes.csv', probe_rows)
    # Additional analysis only: sharpen eps/p at the same saved geometry and charging durations.
    # This isolates the derivative-weight change from movement of the trajectory itself.
    model = tr.Model(0, 0, tr.LIBRARIES['normalized'])
    template = model.solution(model.y)
    fixed = []
    for stage in [3, 4, 5, 6]:
        saved = data['rust'][stage-1]
        y = np.array(saved['y'])
        old = tr.describe(model, y, template, saved['eps'], saved['p'])['modes'][29]
        sharp = tr.describe(model, y, template, .0005, 12.)['modes'][29]
        fixed.append(dict(saved_stage=stage, winner=old['winner'],
            stage_discharge_weight=old['dphi_dz'][0], final_parameters_discharge_weight=sharp['dphi_dz'][0],
            stage_discharge_share=old['derivative_share'][0], final_parameters_discharge_share=sharp['derivative_share'][0]))
    model.close()
    # A geometric certificate for the BFGS pure-mode branch, after exact task restoration.
    bfgs = json.loads((tr.HERE / 'runs/scipy-bfgs/solution.json').read_text())
    first_charge = next(k for k, mode in enumerate(bfgs['modes']) if mode >= 0)
    prefix_tasks = sorted((stamp, index) for index, stamp in enumerate(bfgs['task_stamp']) if stamp <= first_charge)
    waypoints = [bfgs['instance']['r0']] + [bfgs['instance']['tasks'][index] for stamp, index in prefix_tasks]
    distance = sum(math.dist(a, b) for a, b in zip(waypoints, waypoints[1:]))
    battery_range = bfgs['phys']['v_d'] * (bfgs['phys']['e_max'] - bfgs['phys']['e_min']) / bfgs['phys']['zeta']
    certificate = dict(scope='BFGS final pure modes and task stamps; exact task restoration',
        first_charging_segment=first_charge, prefix_task_stamps=[s for s, i in prefix_tasks],
        prefix_task_indices=[i for s, i in prefix_tasks], distance_lower_bound_km=distance,
        battery_range_km=battery_range, excess_km=distance-battery_range,
        minimum_flight_hours=distance/bfgs['phys']['v_d'],
        battery_upper_bound_at_last_prefix_task=bfgs['phys']['e_max'] - bfgs['phys']['zeta']*distance/bfgs['phys']['v_d'],
        infeasible=bool(distance > battery_range))
    tr.write(tr.HERE / 'bfgs-prefix-certificate.json', certificate)
    tr.write(tr.HERE / 'analysis.json', dict(runs=summary, fixed_point_sharpening=fixed,
        bfgs_prefix_certificate=certificate,
        purpose='additional saved-point analysis; no new optimization or parameter selection'))
    fig, axes = plt.subplots(2, 2, figsize=(11, 8))
    colors = ['#3576b7', '#dd8336', '#4b9667']
    labels = ['Rust L-BFGS', 'SciPy L-BFGS-B', 'SciPy BFGS']
    for backend, color, label in zip(tr.BACKENDS, colors, labels):
        ends = data[backend]
        stages = [row['stage'] for row in ends]
        axes[0, 0].plot(stages, [row['objective'] for row in ends], '.-', color=color, label=label)
        axes[0, 1].semilogy(stages, [row['original_kkt']['stat'] for row in ends], '.-', color=color, label=label)
        axes[1, 0].semilogy(stages, [row['selection']['modes'][29]['derivative_share'][0] for row in ends], '.-', color=color, label=label)
        axes[1, 1].plot(stages, [row['selection']['audit'].get('pure_mode_min_energy', math.nan) for row in ends], '.-', color=color, label=label)
    axes[0, 0].set_title('Objective before feasibility restoration')
    axes[0, 0].set_ylabel('Mission time (h)')
    axes[0, 0].legend(fontsize=9)
    axes[0, 1].set_title('Stationarity in original constraint representation')
    axes[0, 1].set_ylabel('Infinity norm')
    axes[0, 1].axhline(1e-6, linestyle=':', color='black', linewidth=1)
    axes[1, 0].set_title('Segment 29: normalized discharge derivative weight')
    axes[1, 0].set_ylabel('Share of d(phi)/dz weights')
    axes[1, 1].set_title('Battery replay after pure-mode selection')
    axes[1, 1].set_ylabel('Minimum battery fraction')
    axes[1, 1].axhline(0., linestyle=':', color='black', linewidth=1)
    for ax in axes.ravel():
        ax.set_xlabel('Homotopy stage')
        ax.set_xticks([1, 3, 5, 7, 9, 11, 13])
        ax.grid(alpha=.18)
    fig.suptitle('Same Figure 1 initialization, rho=10,000 and analytic gradient\nChanging the inner solver changes the path; none passes final KKT', fontsize=13, y=.98)
    fig.subplots_adjust(left=.085, right=.98, bottom=.085, top=.86, hspace=.46, wspace=.27)
    fig.savefig(tr.HERE / 'library-trace.png', dpi=170)
    fig.savefig(tr.HERE / 'library-trace.svg')
    plt.close(fig)
    print(json.dumps(dict(runs=summary, fixed_point_sharpening=fixed), indent=2))


if __name__ == '__main__':
    main()
