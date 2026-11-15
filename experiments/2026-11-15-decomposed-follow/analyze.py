"""Stage summaries, physical audits and figures from saved states only."""
import json
import math

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import helpers as h


def battery_curve(data):
    tr, ph = data['solution'], data['phys']
    replay = h.tr.diag.replay(data)
    times, energies, elapsed = [], [], 0.
    for k, (duration, mode) in enumerate(zip(tr['s'], data['modes'])):
        for fraction in np.linspace(0., 1., 61):
            time = fraction*duration
            e = h.tr.diag.charge(ph, replay[k], time) if mode >= 0 else replay[k]-ph['zeta']*time
            times.append(elapsed+time)
            energies.append(e)
        elapsed += duration
    return times, energies


def main():
    overall = json.loads((h.HERE/'result.json').read_text())
    phases = [json.loads(p.read_text()) for p in sorted((h.HERE/'stages').glob('stage*/result.json'))]
    lines = ['| 段階 | 外側 | 共通stat | 共通feas | 物理変数stat | 時間 h | 秒 | 判定 |',
             '|---:|---:|---:|---:|---:|---:|---:|---|']
    for r in phases:
        lines.append(f"| {r['stage']} | {r['completed_outer']} | {r['common_kkt']['stat']:.3e} | {r['common_kkt']['feas']:.3e} | {r['paper_units_kkt']['stat']:.3e} | {r['objective']:.9f} | {r['seconds']:.2f} | {'両尺度到達' if r['physical_pass'] and r['common_pass'] else ('共通尺度のみ' if r['common_pass'] else '未達')} |")
    (h.HERE/'stages.md').write_text('\n'.join(lines)+'\n')
    raw = json.loads((h.HERE/'solution.json').read_text())
    f = h.stage4.Frozen(overall)
    raw['solution'] = h.tr.decode(f.m, np.array(overall['y']), f.m.source)
    f.close()
    original = h.tr.diag.residuals(raw)
    pure_t, pure_e = battery_curve(raw)
    raw_audit = dict(original_residuals=original, pure_min_energy=min(pure_e), pure_final_energy=pure_e[-1],
        objective=sum(raw['solution']['s']), task_stamps=raw['task_stamp'], modes=raw['modes'],
        charging_segments=sum(mode >= 0 for mode in raw['modes']))
    h.write(h.HERE/'raw-audit.json', raw_audit)
    first = json.loads((h.HERE/'stages/stage13/first-common-kkt.json').read_text()) if overall['final_common_pass'] else None
    summary = dict(completed_outer=overall['total_outer'], seconds=overall['elapsed'], last_stage=overall['stage'],
        final_common_pass=overall['final_common_pass'], final_both_scales_pass=overall['final_both_scales_pass'],
        first_final_common_outer=first['outer'] if first else None,
        first_final_common_seconds=first['elapsed'] if first else None,
        raw=raw_audit, paper_reading_hours=1.8932, paper_reproduction=False, monte_carlo=False)
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.8))
    stages = [r['stage'] for r in phases]
    axes[0].plot(stages, [r['objective'] for r in phases], 'o-')
    axes[0].set_ylabel('Mission time (hours)')
    axes[0].set_title('Different smoothing stages')
    axes[1].semilogy(stages, [max(r['common_kkt'].values()) for r in phases], 'o-', label='common scale')
    axes[1].semilogy(stages, [max(r['paper_units_kkt'].values()) for r in phases], 's-', label='physical variables')
    axes[1].axhline(1e-6, color='black', ls='--', lw=.8)
    axes[1].set_ylabel('Maximum KKT residual')
    axes[1].legend(fontsize=8)
    axes[2].plot(stages, [r['selection']['audit'].get('pure_mode_min_energy') for r in phases], 'o-')
    axes[2].axhline(0., color='black', ls='--', lw=.8)
    axes[2].set_ylabel('Pure-mode minimum battery')
    for ax in axes:
        ax.set_xlabel('Stage')
        ax.grid(alpha=.25)
    fig.tight_layout()
    fig.savefig(h.HERE/'stage-progress.png', dpi=180)
    plt.close(fig)
    if (h.HERE/'restored/solution.json').exists():
        restored = json.loads((h.HERE/'restored/solution.json').read_text())
        restored_result = json.loads((h.HERE/'restored/result.json').read_text())
        final_t, final_e = battery_curve(restored)
        summary['restored'] = dict(**restored_result,
            dense_min_energy=min(final_e), dense_max_energy=max(final_e),
            max_position_change_km=max(math.dist(a, b) for a, b in zip(raw['solution']['r'], restored['solution']['r'])),
            difference_from_paper_seconds=(restored_result['objective']-1.8932)*3600,
            relative_difference_from_paper=(restored_result['objective']/1.8932-1))
        fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))
        ax = axes[0]
        for region in raw['instance']['regions']:
            ax.add_patch(plt.Circle(region['o'], region['rho'], alpha=.13, color='tab:blue'))
        a, b = np.array(raw['solution']['r']), np.array(restored['solution']['r'])
        ax.plot(a[:, 0], a[:, 1], '--', color='gray', lw=1.3, label='Smoothed KKT point')
        ax.plot(b[:, 0], b[:, 1], '-', color='tab:green', lw=1.3, label='Original constraints restored')
        for k, mode in enumerate(restored['modes']):
            if mode >= 0:
                ax.plot(b[k:k+2, 0], b[k:k+2, 1], color='tab:orange', lw=3)
        tasks = np.array(raw['instance']['tasks'])
        ax.scatter(tasks[:, 0], tasks[:, 1], marker='x', color='black')
        for i, task in enumerate(tasks):
            ax.annotate(str(i+1), task, xytext=(4, 4), textcoords='offset points')
        ax.scatter([b[0, 0], b[-1, 0]], [b[0, 1], b[-1, 1]], marker='*', color='black', s=70)
        ax.set_aspect('equal')
        ax.set_xlabel('x (km)')
        ax.set_ylabel('y (km)')
        ax.legend(fontsize=8)
        ax.grid(alpha=.2)
        axes[1].plot(pure_t, pure_e, '--', color='gray', label='Smoothed point, pure-mode replay')
        axes[1].plot(final_t, final_e, color='tab:green', label='Restored')
        axes[1].axhline(0., color='black', lw=.8)
        axes[1].set_xlabel('Mission time (hours)')
        axes[1].set_ylabel('Battery fraction')
        axes[1].legend(fontsize=8)
        axes[1].grid(alpha=.2)
        fig.tight_layout()
        fig.savefig(h.HERE/'trajectory-battery.png', dpi=180)
        plt.close(fig)
    h.write(h.HERE/'summary.json', summary)


if __name__ == '__main__':
    main()
