"""Paired comparison of the nearest-order cohort (N) with the saved index-order cohort (I). Saved files only.

Writes mc-order.csv, mc-order.json, pairs.csv, summary.md and mc-order.png. Needs NumPy and Matplotlib.
"""
import csv
import json
import math
import tarfile
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Patch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OLD = HERE.parent/'2026-11-14-conditioning/mc-rho1e4'
read = lambda p: list(csv.DictReader(open(p)))
ok = lambda r: r['original_violation_le_1e_3'] == 'True'
med = lambda v: float(np.median(v)) if len(v) else None


def nearest_order(inst):
    left, at, out = list(range(len(inst['tasks']))), inst['r0'], []
    while left:
        i = min(left, key=lambda j: math.dist(at, inst['tasks'][j]))
        left.remove(i)
        at = inst['tasks'][i]
        out.append(i)
    return out


def route(inst, order):
    points = [inst['r0']]+[inst['tasks'][i] for i in order]+[inst['rf']]
    return sum(math.dist(a, b) for a, b in zip(points, points[1:]))


def main():
    new, old = read(HERE/'mc-nearest/results.csv'), read(OLD/'results.csv')
    paper = read(ROOT/'data/paper_fig3.csv')
    assert len(new) == len(old) == 900
    key = lambda r: (int(r['tau']), int(r['run']))
    old_by = {key(r): r for r in old}
    assert all(old_by[key(r)]['seed'] == r['seed'] for r in new)
    archive = tarfile.open(OLD/'cases.tar.gz')
    pairs, groups = [], []
    for r in new:
        tau, run = key(r)
        o = old_by[(tau, run)]
        row = dict(tau=tau, run=run, seed=int(r['seed']), ok_I=ok(o), ok_N=ok(r),
                   objective_I=float(o['objective']) if o['objective'] else None,
                   objective_N=float(r['objective']) if r['objective'] else None)
        raw_path = HERE/'mc-nearest/cases'/f'tau{tau}'/f'run{run:03d}'/'raw.json'
        if raw_path.exists():
            raw = json.loads(raw_path.read_text())
            inst = raw['instance']
            order = nearest_order(inst)
            row.update(route_index=route(inst, range(tau)), route_nearest=route(inst, order),
                       order_kept_N=[int(i) for i in np.argsort(raw['task_stamp'], kind='stable')] == order)
            saved = json.load(archive.extractfile(f'cases/tau{tau}/run{run:03d}/raw.json'))
            assert saved['instance'] == inst
            row['order_kept_I'] = [int(i) for i in np.argsort(saved['task_stamp'], kind='stable')] == list(range(tau))
            row['same_order'] = order == list(range(tau))
        pairs.append(row)
    with open(HERE/'pairs.csv', 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(pairs[0]) + [k for k in ['route_index', 'route_nearest', 'order_kept_N', 'order_kept_I', 'same_order'] if k not in pairs[0]],
                           lineterminator='\n')
        w.writeheader()
        w.writerows(pairs)
    for tau in range(1, 10):
        a = [r for r in new if int(r['tau']) == tau]
        b = [old_by[key(r)] for r in a]
        p = [x for x in pairs if x['tau'] == tau]
        ref = [float(v['value']) for v in paper if v['method'] == 'NLP' and int(v['tau']) == tau and v['quantity'] == 'objective_h']
        assert len(ref) == 100
        done = [r for r in a if r['completed'] == 'True']
        both = [x for x in p if x['ok_I'] and x['ok_N']]
        ratios = [x['objective_N']/x['objective_I'] for x in both]
        geo = [x['route_nearest']/x['route_index'] for x in both if 'route_index' in x]
        paper_median = med(ref)
        g = dict(tau=tau, completed=len(done), timed_out=sum(r['timed_out'] == 'True' for r in a),
            kkt_N=sum(r['kkt_converged'] == 'True' for r in a),
            viol_ok_I=sum(map(ok, b)), viol_ok_N=sum(map(ok, a)),
            gained=sum(ok(x) and not ok(y) for x, y in zip(a, b)), lost=sum(ok(y) and not ok(x) for x, y in zip(a, b)),
            audit_I=sum(r['physical_audit_pass'] == 'True' for r in b), audit_N=sum(r['physical_audit_pass'] == 'True' for r in a),
            median_all_I=med([float(r['objective']) for r in b if r['completed'] == 'True']),
            median_all_N=med([float(r['objective']) for r in done]),
            median_ok_I=med([float(r['objective']) for r in b if ok(r)]),
            median_ok_N=med([float(r['objective']) for r in a if ok(r)]),
            median_paper=paper_median, pairs_both_ok=len(both),
            paired_ratio_median=med(ratios),
            paired_ratio_q1=float(np.percentile(ratios, 25)) if ratios else None,
            paired_ratio_q3=float(np.percentile(ratios, 75)) if ratios else None,
            paired_better=sum(v < 0.999 for v in ratios), paired_worse=sum(v > 1.001 for v in ratios),
            route_ratio_median=med(geo),
            corr_log_route_log_objective=float(np.corrcoef(np.log(geo), np.log(ratios))[0, 1]) if len(geo) > 2 and np.std(geo) > 0 else None,
            order_kept_I=sum(bool(x.get('order_kept_I')) for x in p), order_kept_N=sum(bool(x.get('order_kept_N')) for x in p),
            same_order=sum(bool(x.get('same_order')) for x in p),
            identical_objective=sum(x['objective_I'] == x['objective_N'] for x in p if x['objective_N'] is not None),
            median_seconds_N=med([float(r['solver_seconds']) for r in done]))
        g['ratio_to_paper_all_I'] = g['median_all_I']/paper_median
        g['ratio_to_paper_all_N'] = g['median_all_N']/paper_median
        g['ratio_to_paper_ok_I'] = g['median_ok_I']/paper_median if g['median_ok_I'] else None
        g['ratio_to_paper_ok_N'] = g['median_ok_N']/paper_median if g['median_ok_N'] else None
        groups.append(g)
    (HERE/'mc-order.json').write_text(json.dumps(groups, indent=2)+'\n')
    with open(HERE/'mc-order.csv', 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(groups[0]), lineterminator='\n')
        w.writeheader()
        w.writerows(groups)
    total = lambda k: sum(g[k] for g in groups)
    out = ['| タスク数 | 違反<=1e-3 I | N | 新たに合格 | 転落 | 目的の中央値[h] I（合格のみ） | N（合格のみ） | 図3読取 | 図3比 I | 図3比 N | 対の比N/Iの中央値（四分位） | 対の数 | 直線距離の比の中央値 |',
           '|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|']
    for g in groups:
        out.append(f"| {g['tau']} | {g['viol_ok_I']} | {g['viol_ok_N']} | {g['gained']} | {g['lost']} | {g['median_ok_I']:.3f} | {g['median_ok_N']:.3f} "
                   f"| {g['median_paper']:.3f} | {g['ratio_to_paper_ok_I']:.2f} | {g['ratio_to_paper_ok_N']:.2f} "
                   f"| {g['paired_ratio_median']:.3f}（{g['paired_ratio_q1']:.3f}〜{g['paired_ratio_q3']:.3f}） | {g['pairs_both_ok']} | {g['route_ratio_median']:.3f} |")
    out += ['', f"合計：違反<=1e-3はI {total('viol_ok_I')}/900、N {total('viol_ok_N')}/900（新たに合格 {total('gained')}、転落 {total('lost')}）。"
            f"純モード電池の監査はI {total('audit_I')}/900、N {total('audit_N')}/900。KKTはN {total('kkt_N')}/900。時間切れ {total('timed_out')}。", '',
            '| タスク数 | 目的の中央値[h] I（全出力） | N（全出力） | 図3比 I | 図3比 N | 対で改善/悪化（0.1%超） | 距離比と目的比の相関（対数） | 最終の訪問順が出発点のまま I | N | 訪問順が同じ例 | 秒の中央値 N |',
            '|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|']
    for g in groups:
        corr = '—' if g['corr_log_route_log_objective'] is None else f"{g['corr_log_route_log_objective']:.2f}"
        out.append(f"| {g['tau']} | {g['median_all_I']:.3f} | {g['median_all_N']:.3f} | {g['ratio_to_paper_all_I']:.2f} | {g['ratio_to_paper_all_N']:.2f} "
                   f"| {g['paired_better']}/{g['paired_worse']} | {corr} | {g['order_kept_I']} | {g['order_kept_N']} | {g['same_order']} | {g['median_seconds_N']:.1f} |")
    (HERE/'summary.md').write_text('\n'.join(out)+'\n')
    print('\n'.join(out))

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.6), layout='constrained')
    colors = ['#3673b9', '#c45536', '#3a9a5c']
    series = [('Paper NLP (digitized Fig. 3)', lambda tau: [float(v['value']) for v in paper if v['method'] == 'NLP' and int(v['tau']) == tau and v['quantity'] == 'objective_h']),
              ('Index-order warm start', lambda tau: [x['objective_I'] for x in pairs if x['tau'] == tau and x['ok_I']]),
              ('Nearest-order warm start', lambda tau: [x['objective_N'] for x in pairs if x['tau'] == tau and x['ok_N']])]
    for (label, values), color, offset in zip(series, colors, (-.27, 0., .27)):
        box = axes[0].boxplot([values(tau) for tau in range(1, 10)], positions=np.arange(1, 10)+offset, widths=.22,
                              patch_artist=True, showfliers=False, manage_ticks=False)
        for patch in box['boxes']:
            patch.set_facecolor(color)
            patch.set_alpha(.65)
    axes[0].set_xticks(range(1, 10))
    axes[0].set_xlabel('Number of tasks')
    axes[0].set_ylabel('Mission time (h), outputs with violation <= 1e-3')
    axes[0].legend(handles=[Patch(color=c, alpha=.65, label=s[0]) for s, c in zip(series, colors)], fontsize=8)
    axes[0].grid(axis='y', alpha=.2)
    taus = range(1, 10)
    axes[1].plot(taus, [g['ratio_to_paper_ok_I'] for g in groups], 'o-', color=colors[1], label='Index order / paper')
    axes[1].plot(taus, [g['ratio_to_paper_ok_N'] for g in groups], 's-', color=colors[2], label='Nearest order / paper')
    axes[1].axhline(1., color='black', lw=.8, ls='--')
    axes[1].set_xticks(range(1, 10))
    axes[1].set_xlabel('Number of tasks')
    axes[1].set_ylabel('Ratio of median mission time to the paper')
    axes[1].legend(fontsize=8)
    axes[1].grid(alpha=.2)
    fig.suptitle('Own random instances and settings; distributions compared, not matched instances', fontsize=10)
    fig.savefig(HERE/'mc-order.png', dpi=170)


if __name__ == '__main__':
    main()
