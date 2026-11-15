"""Tables of the 12 cases (plus the R1 Figure-1 run) from saved files only. Standard library."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OLD = HERE.parent/'2026-11-14-conditioning/cases'
R1 = HERE.parent/'2026-11-15-original-init'
CASES = [f'tau{t}-seed{s}' for t in (1, 3, 5, 7) for s in (0, 1, 2)]
load = lambda p: json.loads(Path(p).read_text())


def case(folder, name, restoration=None):
    pre = load(folder/'preflight.json')
    result = load(folder/'result.json')
    stages = [load(p) for p in sorted((folder/'stages').glob('stage*/result.json'))]
    audit = result['selection']['audit']
    restoration = restoration or (load(folder/'restored/result.json') if (folder/'restored/result.json').exists() else None)
    first = folder/'stages/stage13/first-common-kkt.json'
    row = dict(case=name, start_objective=pre['start_objective_hours'], start_charging=pre['start_charging_segments'],
        last_stage=result['stage'], stop=result['stop'], reached_final=result['reached_final'],
        final_common=result['final_common_pass'], final_both=result['final_both_scales_pass'],
        objective=result['objective'], charging=result['selection']['charging_segments'],
        charging_by_stage=[s['selection']['charging_segments'] for s in stages],
        original_violation=audit['original_residuals']['viol'], pure_min_energy=audit.get('pure_mode_min_energy'),
        common_kkt=result['common_kkt'], physical_stat=result['paper_units_kkt']['stat'],
        total_outer=result['total_outer'], seconds=result['elapsed'],
        stage_seconds=[round(s['seconds'], 1) for s in stages], max_rho=max(s['rho'] for s in stages),
        first_common_seconds=load(first)['elapsed'] if first.exists() else None,
        restored=None if restoration is None else bool(restoration.get('accepted', restoration.get('accepted_under_R2a_rule'))),
        restored_objective=None, restoration_reason=None)
    if restoration is not None:
        row['restoration_reason'] = restoration.get('reason')
        if row['restored']:
            row['restored_objective'] = restoration['objective']
            row['restored_residual'] = restoration['original_residuals']['viol']
            row['restored_min_energy'] = restoration['min_energy']
    return row


def main():
    rows = [case(HERE/'cases'/name, name) for name in CASES if (HERE/'cases'/name/'result.json').exists()]
    missing = [name for name in CASES if not (HERE/'cases'/name/'result.json').exists()]
    fig1 = case(R1, 'fig1 (R1)', load(HERE/'r1-rejudged.json'))
    for row in rows:
        row['earlier'] = {c: dict(objective=d['metrics']['objective'], violation=d['metrics']['viol'])
                          for c in ('L0', 'L', 'N') for d in [load(OLD/c/f"{row['case']}.json")]}
    (HERE/'summary.json').write_text(json.dumps(dict(cases=rows, figure1_R1=fig1, missing=missing), indent=2)+'\n')
    n = len(rows)
    count = lambda f: f'{sum(bool(f(r)) for r in rows)}/{n}'
    out = ['| 判定 | 12例 |', '|---|---:|',
        f"| 第13段階まで進んだ | {count(lambda r: r['reached_final'])} |",
        f"| 第13段階の共通KKT | {count(lambda r: r['final_common'])} |",
        f"| 共通KKTと物理変数KKTの両方 | {count(lambda r: r['final_both'])} |",
        f"| 最終平滑化点の元の違反<=1e-3 | {count(lambda r: r['original_violation'] <= 1e-3)} |",
        f"| 最終平滑化点の純モード電池が非負 | {count(lambda r: r['pure_min_energy'] is not None and r['pure_min_energy'] >= 0)} |",
        f"| 復元が受理された | {count(lambda r: r['restored'])} |", '',
        '| 例 | 初期 h（充電） | 最終段階 | 共通KKT | 物理stat | 平滑化点 h | 充電 | 元の違反 | 純モード最低電池 | 復元 h | 外側 | 秒 | 段階ごとの充電区間 |',
        '|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|']
    for r in rows+[fig1]:
        restored = f"{r['restored_objective']:.6f}" if r['restored'] else ('不受理' if r['restored'] is False else '—')
        energy = '—' if r['pure_min_energy'] is None else f"{r['pure_min_energy']:.2e}"
        out.append(f"| {r['case']} | {r['start_objective']:.4f}（{r['start_charging']}） | {r['last_stage']}（{r['stop']}） "
            f"| {'到達' if r['final_common'] else '未達'} | {r['physical_stat']:.1e} | {r['objective']:.6f} | {r['charging']} "
            f"| {r['original_violation']:.1e} | {energy} | {restored} | {r['total_outer']} | {r['seconds']:.0f} "
            f"| {' '.join(map(str, r['charging_by_stage']))} |")
    out += ['', '| 例 | 今回の復元 h | 既存L0（平滑化点・違反） | 既存L | 既存N |', '|---|---:|---:|---:|---:|']
    for r in rows:
        e = r['earlier']
        cell = lambda c: f"{e[c]['objective']:.4f}・{e[c]['violation']:.0e}"
        out.append(f"| {r['case']} | {r['restored_objective']:.4f} | {cell('L0')} | {cell('L')} | {cell('N')} |" if r['restored']
                   else f"| {r['case']} | — | {cell('L0')} | {cell('L')} | {cell('N')} |")
    if missing:
        out += ['', '出力の無い例: '+', '.join(missing)]
    (HERE/'summary.md').write_text('\n'.join(out)+'\n')
    print('\n'.join(out))


if __name__ == '__main__':
    main()
