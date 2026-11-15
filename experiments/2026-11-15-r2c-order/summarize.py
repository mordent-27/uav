"""Compare G (index-order start, saved R2b results) with O (nearest-order start) from saved files only."""
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
G = HERE.parent/'2026-11-15-r2b-coarse/cases/G'
ALL = ['fig1']+[f'tau{t}-seed{s}' for t in (1, 3, 5, 7) for s in (0, 1, 2)]
load = lambda p: json.loads(Path(p).read_text())


def case(folder):
    if not (folder/'result.json').exists():
        return None
    result = load(folder/'result.json')
    stages = [load(p) for p in sorted((folder/'stages').glob('stage*/result.json'))]
    audit = result['selection']['audit']
    restoration = load(folder/'restored/result.json') if (folder/'restored/result.json').exists() else None
    accepted = bool(restoration and restoration.get('accepted'))
    stamps = [t['stamp'] for t in result['selection']['tasks']]
    row = dict(last_stage=result['stage'], stop=result['stop'], final_common=result['final_common_pass'],
        final_both=result['final_both_scales_pass'], objective=result['objective'],
        charging=result['selection']['charging_segments'],
        charging_by_stage=[s['selection']['charging_segments'] for s in stages],
        stage_pass=[bool(s['stage_pass']) for s in stages],
        original_violation=audit['original_residuals']['viol'], pure_min_energy=audit.get('pure_mode_min_energy'),
        common_feas=result['common_kkt']['feas'], max_multiplier=float(max(abs(v) for v in result['lam'])),
        task_stamps=stamps, final_order=[int(i) for i in np.argsort(stamps, kind='stable')],
        total_outer=result['total_outer'], seconds=result['elapsed'], restored=accepted,
        restored_objective=restoration['objective'] if accepted else None,
        restored_residual=restoration['original_residuals']['viol'] if accepted else None)
    row['restored_strict'] = bool(accepted and row['restored_residual'] < 1e-10)
    return row


def main():
    table = {}
    for name in ALL:
        pre = load(HERE/'preflight'/f'{name}.json')
        g = case(G/name)
        o = g if pre['identical_start'] else case(HERE/'cases'/name)
        table[name] = dict(preflight=pre, G=g, O=o, O_reuses_G=pre['identical_start'])
    (HERE/'summary.json').write_text(json.dumps(table, indent=2)+'\n')
    rows = [r for r in table.values() if r['O'] is not None]
    count = lambda c, f, sel=rows: f"{sum(bool(f(r[c])) for r in sel)}/{len(sel)}"
    differ = [r for r in rows if not r['O_reuses_G']]
    out = ['| 判定 | G（番号順） | O（最近傍順） | うち出発点が違う10例 G | 同 O |', '|---|---:|---:|---:|---:|']
    for label, f in [('第13段階の共通KKT', lambda r: r['final_common']), ('復元が受理された（残差<=1e-6）', lambda r: r['restored']),
                     ('復元が厳しい条件も満たす（<1e-10）', lambda r: r['restored_strict'])]:
        out.append(f"| {label} | {count('G', f)} | {count('O', f)} | {count('G', f, differ)} | {count('O', f, differ)} |")
    cell = lambda r: f"{r['restored_objective']:.6f}" if r['restored'] else f"段階{r['last_stage']}で停止（{r['stop']}）"
    out += ['', '| 例 | 直線距離 km 番号順/最近傍/最短 | 初期 h 番号順→最近傍 | G 復元後 h | O 復元後 h | O−G 秒 | 充電区間 G/O | 最終の訪問順 O（初期の最近傍順） | 計算秒 G/O |',
            '|---|---|---|---:|---:|---:|---|---|---|']
    for name, r in table.items():
        if r['O'] is None:
            out.append(f'| {name} | 出力なし |')
            continue
        p, g, o = r['preflight'], r['G'], r['O']
        diff = f"{(o['restored_objective']-g['restored_objective'])*3600:+.1f}" if g['restored'] and o['restored'] else '—'
        km = p['route_km']
        kept = '同じ' if o['final_order'] == p['nearest_order'] else '入れ替わり'
        out.append(f"| {name}{'（Gを使用）' if r['O_reuses_G'] else ''} | {km['index']:.1f}/{km['nearest']:.1f}/{km['best']:.1f} "
            f"| {p['start_hours']['index']:.3f}→{p['start_hours']['nearest']:.3f} | {cell(g)} | {cell(o)} | {diff} "
            f"| {g['charging']}/{o['charging']} | {' '.join(map(str, o['final_order']))}（{' '.join(map(str, p['nearest_order']))}：{kept}） "
            f"| {g['seconds']:.0f}/{o['seconds']:.0f} |")
    out += ['', '| 例 | O：段階ごとの到達（o=1e-6に到達、x=未達） | O：段階ごとの充電区間 | O：最終の共通feas | O：乗数の最大 |', '|---|---|---|---:|---:|']
    for name, r in table.items():
        o = r['O']
        if o is not None and not r['O_reuses_G']:
            out.append(f"| {name} | {''.join('o' if p else 'x' for p in o['stage_pass'])} | {' '.join(map(str, o['charging_by_stage']))} "
                       f"| {o['common_feas']:.1e} | {o['max_multiplier']:.1e} |")
    (HERE/'summary.md').write_text('\n'.join(out)+'\n')
    print('\n'.join(out))


if __name__ == '__main__':
    main()
