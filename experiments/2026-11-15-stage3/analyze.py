"""Create readable tables and static figures from the saved controls."""
import gzip
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent


def main():
    results = json.loads((HERE/'matrix.json').read_text())
    lines = ['| dual | rho初期値 | 内側精度条件 | 外側回数 | 共通停留性 | 共通実行可能性 | 物理変数の停留性 | 最終rho | 秒 | 共通KKT |',
             '|---|---:|---|---:|---:|---:|---:|---:|---:|---|']
    fig, axes = plt.subplots(2, 4, figsize=(14, 6), sharex='col')
    pairs = {}
    for result in results:
        name = result['name']
        dual, rho, gate = name.split('_')
        lines.append(f"| {'reset' if dual.endswith('reset') else 'carry'} | {'1e4' if rho.endswith('reset') else '1e6'} | {'あり' if gate == 'gated' else 'なし'} | {result['additional_outer']} | {result['common_kkt']['stat']:.3e} | {result['common_kkt']['feas']:.3e} | {result['paper_units_kkt']['stat']:.3e} | {result['rho']:.0e} | {result['seconds']:.2f} | {'到達' if result['target_kkt_pass'] else result['stop']} |")
        with gzip.open(HERE/'cases'/name/'outer.jsonl.gz', 'rt') as handle:
            rows = [json.loads(line) for line in handle]
        key = (dual, rho)
        if key not in pairs:
            pairs[key] = len(pairs)
        col = pairs[key]
        x = [r['outer'] for r in rows]
        style = '-' if gate == 'plain' else '--'
        color = 'tab:red' if gate == 'plain' else 'tab:blue'
        axes[0, col].semilogy(x, [max(r['common_kkt'].values()) for r in rows], style, color=color, label=gate)
        axes[1, col].semilogy(x, [r['rho'] for r in rows], style, color=color, label=gate)
        axes[0, col].set_title(dual+' / '+rho)
    for col in range(4):
        axes[0, col].axhline(1e-6, color='black', lw=.8, alpha=.5)
        axes[0, col].set_ylabel('Max common KKT residual')
        axes[1, col].set_ylabel('Penalty used')
        axes[1, col].set_xlabel('Outer iteration')
        for ax in axes[:, col]:
            ax.grid(alpha=.25)
            ax.legend()
    fig.tight_layout()
    fig.savefig(HERE/'matrix.png', dpi=180)
    plt.close(fig)
    (HERE/'matrix.md').write_text('\n'.join(lines)+'\n\n共通KKTは既定の変数尺度・元の二乗速度で各成分<=1e-6。物理変数で同じ1e-6を要求すると全8条件が未達。著者の許容値を特定したものではない。\n')
    if (HERE/'follow.json').exists():
        results = json.loads((HERE/'follow.json').read_text())
        lines = ['| 段階 | eps | p | 外側回数 | 停留性 | 実行可能性 | 最終rho | 秒 | KKT |',
                 '|---:|---:|---:|---:|---:|---:|---:|---:|---|']
        for result in results:
            lines.append(f"| {result['stage']} | {result['eps']:.7f} | {result['p']:.5f} | {result['additional_outer']} | {result['common_kkt']['stat']:.3e} | {result['common_kkt']['feas']:.3e} | {result['rho']:.0e} | {result['seconds']:.2f} | {'到達' if result['target_kkt_pass'] else result['stop']} |")
        (HERE/'follow.md').write_text('\n'.join(lines)+'\n')


if __name__ == '__main__':
    main()
