"""Tables comparing B (saved R2a/R1 results) with S, G and T from saved files only. Standard library."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
R2A = HERE.parent/'2026-11-15-r2-cases'
R1 = HERE.parent/'2026-11-15-original-init'
ALL = ['fig1']+[f'tau{t}-seed{s}' for t in (1, 3, 5, 7) for s in (0, 1, 2)]
load = lambda p: json.loads(Path(p).read_text())


def case(folder, restoration=None):
    if not (folder/'result.json').exists():
        return None
    result = load(folder/'result.json')
    stages = [load(p) for p in sorted((folder/'stages').glob('stage*/result.json'))]
    audit = result['selection']['audit']
    if restoration is None and (folder/'restored/result.json').exists():
        restoration = load(folder/'restored/result.json')
    accepted = bool(restoration and restoration.get('accepted', restoration.get('accepted_under_R2a_rule')))
    row = dict(last_stage=result['stage'], stop=result['stop'], final_common=result['final_common_pass'],
        final_both=result['final_both_scales_pass'], objective=result['objective'],
        charging=result['selection']['charging_segments'],
        charging_by_stage=[s['selection']['charging_segments'] for s in stages],
        stage_pass=[bool(s['stage_pass']) for s in stages], stage_outer=[s['completed_outer'] for s in stages],
        stage_seconds=[round(s['seconds'], 1) for s in stages],
        original_violation=audit['original_residuals']['viol'], pure_min_energy=audit.get('pure_mode_min_energy'),
        total_outer=result['total_outer'], seconds=result['elapsed'], restored=accepted,
        restored_objective=restoration['objective'] if accepted else None,
        restored_residual=restoration['original_residuals']['viol'] if accepted else None,
        restoration_reason=restoration.get('reason') if restoration else None)
    row['restored_strict'] = bool(accepted and row['restored_residual'] < 1e-10)
    return row


def main():
    table = {name: dict(B=case(R1, load(R2A/'r1-rejudged.json')) if name == 'fig1' else case(R2A/'cases'/name),
                        **{c: case(HERE/'cases'/c/name) for c in 'SGT'}) for name in ALL}
    (HERE/'summary.json').write_text(json.dumps(table, indent=2)+'\n')
    out = ['| 判定 | B（R2a・R1） | G（外側10回で進む） | T（許容値1e-3×eps） |', '|---|---:|---:|---:|']
    count = lambda c, f: f"{sum(bool(r[c] and f(r[c])) for r in table.values())}/{sum(r[c] is not None for r in table.values())}"
    for label, f in [('第13段階まで進んだ', lambda r: r['last_stage'] == 13),
                     ('第13段階の共通KKT', lambda r: r['final_common']),
                     ('共通KKTと物理変数KKTの両方', lambda r: r['final_both']),
                     ('復元が受理された（残差<=1e-6）', lambda r: r['restored']),
                     ('復元が厳しい条件も満たす（<1e-10）', lambda r: r['restored_strict'])]:
        out.append(f'| {label} | '+' | '.join(count(c, f) for c in 'BGT')+' |')
    cell = lambda r: '—' if r is None else (f"{r['restored_objective']:.6f}" if r['restored'] else
        (f"不受理（段階13）" if r['last_stage'] == 13 and r['final_common'] else f"段階{r['last_stage']}で停止（{r['stop']}）"))
    out += ['', '| 例 | B 復元後 h | S（単独） | G 復元後 h | T 復元後 h | G−B 秒 | T−B 秒 | 充電区間 B/G/T | 計算秒 B/G/T | 外側 B/G/T |',
            '|---|---:|---:|---:|---:|---:|---:|---|---|---|']
    for name, r in table.items():
        diff = lambda c: (f"{(r[c]['restored_objective']-r['B']['restored_objective'])*3600:+.2f}"
                          if r[c] and r[c]['restored'] and r['B']['restored'] else '—')
        triple = lambda key, fmt: '/'.join('—' if r[c] is None else fmt(r[c][key]) for c in 'BGT')
        out.append(f"| {name} | {cell(r['B'])} | {cell(r['S'])} | {cell(r['G'])} | {cell(r['T'])} | {diff('G')} | {diff('T')} "
                   f"| {triple('charging', str)} | {triple('seconds', lambda v: f'{v:.0f}')} | {triple('total_outer', str)} |")
    out += ['', '| 例 | G：段階ごとの到達（o=許容値に到達、x=未達のまま次へ／停止） | G：段階ごとの充電区間 | T：段階ごとの充電区間 |', '|---|---|---|---|']
    for name, r in table.items():
        g, t = r['G'], r['T']
        out.append(f"| {name} | {''.join('o' if p else 'x' for p in g['stage_pass']) if g else '—'} "
                   f"| {' '.join(map(str, g['charging_by_stage'])) if g else '—'} | {' '.join(map(str, t['charging_by_stage'])) if t else '—'} |")
    (HERE/'summary.md').write_text('\n'.join(out)+'\n')
    print('\n'.join(out))


if __name__ == '__main__':
    main()
