"""Figures for report.tex (run from anywhere with the uv Python that has matplotlib).
usage: python make_figs.py
  fig-carrier.pdf : tau8-seed8000015 returned point (R3s), the in-disk dash that one carrier cannot follow
  fig-fig3.pdf    : objective distribution, paper Fig.3 NLP (read from the vector PDF) vs our 894 returned points
"""
import csv, json, math
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Circle

HERE = Path(__file__).resolve().parent
UAV = HERE.parents[1]/'uav'
plt.rcParams.update({'font.family': 'Noto Sans CJK JP', 'font.size': 8, 'pdf.fonttype': 3, 'axes.linewidth': .6})

def draw(ax, d, color_c='#1f5fbf', color_d='0.45', lw=1.0, alpha=1., hl=None, label=None, ks=None):
    r, m = d['solution']['r'], d['modes']
    for k, mode in enumerate(m):
        if ks is not None and k not in ks: continue
        (x0, y0), (x1, y1) = r[k], r[k+1]
        if hl is not None and k == hl:
            ax.plot([x0, x1], [y0, y1], color='#d9480f', lw=2.2, alpha=alpha, zorder=4, solid_capstyle='round')
        elif mode >= 0:
            ax.plot([x0, x1], [y0, y1], color=color_c, lw=2.4*lw, alpha=alpha, zorder=3, solid_capstyle='round')
        else:
            ax.plot([x0, x1], [y0, y1], color=color_d, lw=.8*lw, alpha=alpha, zorder=2)

def base_map(ax, d):
    for j, reg in enumerate(d['instance']['regions']):
        ax.add_patch(Circle(reg['o'], reg['rho'], fc='#dbe8f7', ec='#7aa6d8', lw=.6, zorder=0))
        ax.text(reg['o'][0]-reg['rho']*.75, reg['o'][1]+reg['rho']*.85, f'領域{j+1}', ha='right', fontsize=7, color='#3a6aa5', clip_on=True)
    t = list(zip(*d['instance']['tasks']))
    ax.plot(*t, '*', color='#c92a2a', ms=7, zorder=5)
    ax.set_aspect('equal'); ax.tick_params(length=2)

def fig_carrier():
    ret = json.loads((UAV/'experiments/2026-11-16-r3s-cohort/runs/tau8-seed8000015/selected.json').read_text())
    from matplotlib.lines import Line2D
    fig, ax = plt.subplots(figsize=(3.7, 3.2))
    base_map(ax, ret); draw(ax, ret, hl=20)
    ax.plot(*ret['instance']['r0'], 'ks', ms=4, zorder=6); ax.plot(*ret['instance']['rf'], 'k^', ms=4, zorder=6)
    ax.set_xlim(-10, 10); ax.set_ylim(-9, 9.5)
    ax.set_xlabel('x [km]'); ax.set_ylabel('y [km]')
    ax.annotate('区間21：充電を切り\n放電のまま円板内を\n2.12 km / 212 s で移動', xy=(1.1, -1.7), xytext=(3.0, 3.6), fontsize=7,
                arrowprops=dict(arrowstyle='->', lw=.6))
    ax.legend(handles=[Line2D([], [], color='#1f5fbf', lw=2.4, label='充電区間'), Line2D([], [], color='0.45', lw=.8, label='放電区間'),
                       Line2D([], [], color='#d9480f', lw=2.2, label='区間21'), Line2D([], [], color='#c92a2a', marker='*', ls='', label='タスク')],
              fontsize=7, loc='lower right', frameon=False)
    fig.tight_layout(); fig.savefig(HERE/'fig-carrier.pdf'); plt.close(fig)

def fig_fig3():
    paper = {t: [] for t in range(1, 10)}
    for row in csv.DictReader(open(UAV/'data/paper_fig3.csv')):
        if row['quantity'] == 'objective_h' and row['method'] == 'NLP':
            paper[int(row['tau'])].append(float(row['value']))
    ours = {t: [] for t in range(1, 10)}
    for row in csv.DictReader(open(UAV/'experiments/2026-11-17-r3s-paper-comparison/cases.csv')):
        if row['physical_point_available'] == 'True':
            ours[int(row['tau'])].append(float(row['objective_h']))
    assert sum(map(len, paper.values())) == 900 and sum(map(len, ours.values())) == 894
    fig, ax = plt.subplots(figsize=(6.3, 2.1))
    kw = dict(widths=.32, whis=(10, 90), showfliers=False, patch_artist=True, medianprops=dict(color='k', lw=1))
    b1 = ax.boxplot([paper[t] for t in range(1, 10)], positions=[t-.18 for t in range(1, 10)], **kw)
    b2 = ax.boxplot([ours[t] for t in range(1, 10)], positions=[t+.18 for t in range(1, 10)], **kw)
    for b, c in ((b1, '#74a9cf'), (b2, '#f4a582')):
        for p in b['boxes']: p.set(fc=c, lw=.6)
    ax.set_xticks(range(1, 10), [str(t) for t in range(1, 10)]); ax.set_xlim(.4, 9.6); ax.set_xlabel('タスク数 τ'); ax.set_ylabel('ミッション時間 [h]')
    ax.legend([b1['boxes'][0], b2['boxes'][0]], ['論文 図3のNLP（各100点）', '本検討の独自計算（原制約を満たす返却点 894点）'], fontsize=6.5, frameon=False, loc='upper left')
    ax.grid(axis='y', lw=.3, color='0.85')
    fig.tight_layout(); fig.savefig(HERE/'fig-fig3.pdf'); plt.close(fig)

fig_carrier(); fig_fig3(); print('ok')
