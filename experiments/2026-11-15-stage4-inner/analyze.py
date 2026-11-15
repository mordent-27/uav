"""Tables and figures from immutable solver outputs; no optimization."""
import gzip
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import support as s


def main():
    results = [json.loads(p.read_text()) for p in sorted((s.HERE/'cases').glob('*/*/result.json'))]
    lines = ['| 固定AL | 内側法 | 内側勾配 | 反復 | 秒 | 停止理由 |',
             '|---|---|---:|---:|---:|---|']
    for r in results:
        lines.append(f"| {r['problem']} | {r['method']} | {r['gradient_inf']:.3e} | {r['iterations']} | {r['seconds']:.3f} | {r['status']} |")
    (s.HERE/'comparison.md').write_text('\n'.join(lines)+'\n')
    fig, axes = plt.subplots(1, 3, figsize=(13, 4))
    for ax, problem in zip(axes, ['before-raise', 'after-raise', 'stalled']):
        subset = [r for r in results if r['problem'] == problem]
        ax.barh([r['method'] for r in subset], [r['gradient_inf'] for r in subset])
        ax.set_xscale('log')
        ax.axvline(1e-8, color='black', ls='--', label='inner target 1e-8')
        ax.axvline(1e-6, color='tab:red', ls=':', label='outer tolerance 1e-6')
        ax.set_title(problem)
        ax.set_xlabel('Actual frozen-AL gradient infinity norm')
        ax.grid(axis='x', alpha=.25)
    axes[0].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(s.HERE/'inner-comparison.png', dpi=180)
    plt.close(fig)
    direct = json.loads((s.HERE/'curvature.json').read_text())
    extended = json.loads((s.HERE/'decomposition.json').read_text())
    fig, axes = plt.subplots(1, 3, figsize=(12, 4))
    for ax, problem, entry in zip(axes, ['before-raise', 'after-raise', 'stalled'], extended):
        assert entry['problem'] == problem
        rows = [dict(v, kind='direct') for v in direct if v['problem'] == problem]+entry['estimates']
        for kind in ['direct', 'decomposed']:
            subset = sorted([r for r in rows if r['kind'] == kind], key=lambda r: r['step'])
            ax.loglog([r['step'] for r in subset], [r['max_asymmetry'] for r in subset], 'o-', label=kind)
        ax.set_title(problem)
        ax.set_xlabel('Finite difference step')
        ax.set_ylabel('Maximum asymmetry before symmetrizing')
        ax.grid(alpha=.25)
        ax.legend()
    fig.tight_layout()
    fig.savefig(s.HERE/'curvature-comparison.png', dpi=180)
    plt.close(fig)
    s.write(s.HERE/'summary.json', dict(cases=len(results), inner_tol_1e_minus_8_pass=sum(r['gradient_pass'] for r in results),
        inner_tol_1e_minus_6_pass=sum(r['inner_sufficient'] for r in results),
        one_update_common_pass=sum(max(r['one_update_kkt']['common_kkt'].values()) <= 1e-6 for r in results),
        total_solver_seconds=sum(r['seconds'] for r in results),
        total_logged_evaluations=sum(r['observed_evaluations'] for r in results),
        paper_reproduction=False, main_source_changed=False))


if __name__ == '__main__':
    main()
