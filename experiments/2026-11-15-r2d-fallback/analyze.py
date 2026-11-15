"""Aggregate the fixed G-then-direct rule; never pick by objective value."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OLD_G = HERE.parent/'2026-11-15-r2b-coarse/cases/G'
OLD_DIRECT = HERE.parent/'2026-11-15-r2c-direct-final/cases'


def read(path):
    return json.loads(path.read_text())


def brief(folder):
    result = read(folder/'result.json')
    verification = read(folder/'verification.json')
    assert read(folder/'steps.json') == dict(run='ok', restore='ok', verify='ok')
    assert verification['original_jacobian_stationarity_verified']
    restore_path = folder/'restored/result.json'
    initial_audit = read(folder/'source.json')['selection']['audit']
    restore = read(restore_path) if restore_path.exists() else dict(accepted=False)
    accepted = restore['accepted']
    if accepted:
        assert result['final_common_pass'] and all(restore['checks'].values())
        assert restore['original_residuals']['viol'] <= 1e-6
    return dict(path=str(folder.relative_to(ROOT)), reused=not folder.is_relative_to(HERE),
        common_pass=result['final_common_pass'], physical_pass=result['final_both_scales_pass'],
        reached_final=result['reached_final'], last_stage=result['stage'], stop=result['stop'],
        common_kkt=result['common_kkt'], physical_kkt=result['paper_units_kkt'],
        initial_audit=initial_audit,
        raw_hours=result['objective'], accepted=accepted,
        restored_hours=restore.get('objective') if accepted else None,
        original_residual=restore.get('original_residuals', {}).get('viol'),
        min_energy=restore.get('min_energy'), restoration_checks=restore.get('checks'),
        strict_original_pass=bool(accepted and restore['original_residuals']['viol'] < 1e-10),
        charges=result['selection']['charging_segments'],
        solver_seconds=result['elapsed']+restore.get('seconds', 0.),
        al_seconds=result['elapsed'], restoration_seconds=restore.get('seconds', 0.),
        verified_outer=verification['completed_outer'], verified_inner=verification['accepted_inner_points'],
        interrupted_inner=verification['interrupted_accepted_points'])


def aggregate(case, group, gfolder, dfolder=None, job=None):
    g = brief(gfolder)
    direct = None if g['accepted'] else brief(dfolder)
    if direct:
        assert read(gfolder/'source.json')['y'] == read(dfolder/'source.json')['y']
    selected = g if g['accepted'] else (direct if direct['accepted'] else None)
    phase = 'G' if g['accepted'] else ('direct' if selected else None)
    adopted = None
    if selected:
        source = ROOT/selected['path']/'restored/solution.json'
        adopted = dict(path=str(source.relative_to(ROOT)), sha256=hashlib.sha256(source.read_bytes()).hexdigest())
    if job:
        assert job['error'] is None and job['accepted'] == (selected is not None)
        assert job['selected'] == (None if selected is None else dict(phase=phase, path=selected['path']))
    return dict(case=case, group=group, G=g, direct=direct, selected_phase=phase,
        accepted=selected is not None, selected_hours=None if selected is None else selected['restored_hours'],
        selected_physical_kkt_pass=False if selected is None else selected['physical_pass'],
        selected_strict_original_pass=False if selected is None else selected['strict_original_pass'],
        adopted=adopted, solver_seconds_sum=g['solver_seconds']+(direct['solver_seconds'] if direct else 0.),
        new_wall_seconds=job['seconds'] if job else None,
        new_wall_includes_G=group == 'diagnostic_holdout')


def group_summary(rows):
    return dict(cases=len(rows), G_accepted=sum(r['G']['accepted'] for r in rows),
        fallback_attempts=sum(r['direct'] is not None for r in rows),
        fallback_accepted=sum(r['selected_phase'] == 'direct' for r in rows),
        accepted=sum(r['accepted'] for r in rows),
        selected_both_scales_kkt=sum(r['selected_physical_kkt_pass'] for r in rows),
        selected_strict_original=sum(r['selected_strict_original_pass'] for r in rows),
        selected_G_outputs_unchanged=all(r['selected_phase'] == 'G' for r in rows if r['G']['accepted']))


def main():
    regression = []
    for gfolder in sorted(OLD_G.iterdir()):
        name = gfolder.name
        dfolder = (HERE/'cases/direct'/name) if name == 'tau5-seed1' else OLD_DIRECT/name
        job = read(HERE/'jobs'/f'{name}.json') if name == 'tau5-seed1' else None
        regression.append(aggregate(name, 'regression', gfolder, dfolder, job))
    holdout = []
    for tau in [1, 3, 5, 7]:
        name = f'tau{tau}-seed3'
        holdout.append(aggregate(name, 'diagnostic_holdout', HERE/'cases/G'/name,
            HERE/'cases/direct'/name, read(HERE/'jobs'/f'{name}.json')))
    phases = [brief(folder) for phase in ['G', 'direct'] for folder in sorted((HERE/'cases'/phase).glob('*'))]
    new_checks = dict(phases=len(phases), outer=sum(p['verified_outer'] for p in phases),
        accepted_inner=sum(p['verified_inner'] for p in phases),
        interrupted_inner=sum(p['interrupted_inner'] for p in phases),
        original_jacobian_stationarity_verified=True)
    summary = dict(regression=group_summary(regression), diagnostic_holdout=group_summary(holdout),
        regression_cases=regression, diagnostic_holdout_cases=holdout, new_verification=new_checks,
        diagnostic_holdout_seed_families=1, diagnostic_holdout_tasks_are_nested=True,
        execution=read(HERE/'execution.json'), main_source_changed=False, monte_carlo_rerun=False,
        paper_reproduction=False)
    (HERE/'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    lines = []
    for label, rows in [('既存13例（規則の設計に使用済み）', regression), ('診断規則の設計に使わなかった4例', holdout)]:
        lines += [f'## {label}', '', '| 入力 | G復元 h | 追加直接開始 h | 採用経路 | 計測AL＋復元 秒 |',
                  '|---|---:|---:|---|---:|']
        for r in rows:
            g, d = r['G'], r['direct']
            gt = f"{g['restored_hours']:.9f}" if g['accepted'] else '未受理'
            dt = '実行せず' if d is None else (f"{d['restored_hours']:.9f}" if d['accepted'] else '未受理')
            lines.append(f"| {r['case']} | {gt} | {dt} | {r['selected_phase'] or '失敗'} | {r['solver_seconds_sum']:.2f} |")
        lines.append('')
    (HERE/'comparison.md').write_text('\n'.join(lines))
    print(json.dumps({k:v for k,v in summary.items() if k not in ['regression_cases', 'diagnostic_holdout_cases', 'execution']}))


if __name__ == '__main__':
    main()
