"""Read saved results only: paired comparison and independent-check accounting."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASELINE = HERE.parent/'2026-11-15-r2b-coarse/cases/G'
CASES = ['tau1-seed2', 'tau5-seed0', 'tau7-seed0', 'tau7-seed1', 'tau1-seed0', 'fig1']


def read(path):
    return json.loads(path.read_text())


def main():
    rows = []
    for name in CASES:
        path = HERE/'cases'/name
        source, result, checked, preflight = [read(path/f) for f in
            ['source.json', 'result.json', 'verification.json', 'preflight.json']]
        baseline = read(BASELINE/name/'result.json')
        restore = checked['restoration']
        old_restore_path = BASELINE/name/'restored/result.json'
        old_restore = read(old_restore_path) if old_restore_path.exists() else {}
        old_time = old_restore.get('objective') if old_restore.get('accepted') else None
        initial_modes = [x['winner'] for x in source['selection']['modes']]
        final_modes = [x['winner'] for x in result['selection']['modes']]
        initial_tasks = [x['stamp'] for x in source['selection']['tasks']]
        final_tasks = [x['stamp'] for x in result['selection']['tasks']]
        assert read(path/'steps.json') == dict(run='ok', restore='ok', verify='ok')
        assert preflight['same_original_initial_state']
        assert preflight['independent_Jacobian_gradient_verified']
        assert result['final_common_pass'] and result['final_both_scales_pass']
        assert checked['original_jacobian_stationarity_verified']
        assert restore['accepted'] and all(restore['checks'].values())
        assert restore['original_residuals']['viol'] <= 1e-10
        rows.append(dict(case=name, baseline_common_pass=baseline['final_common_pass'],
            baseline_restored_hours=old_time, direct_hours=result['objective'],
            restored_hours=restore['objective'],
            change_seconds=None if old_time is None else 3600*(restore['objective']-old_time),
            common_kkt=result['common_kkt'], physical_kkt=result['paper_units_kkt'],
            baseline_charges=baseline['selection']['charging_segments'],
            initial_charges=source['selection']['charging_segments'],
            direct_charges=result['selection']['charging_segments'],
            mode_region_assignment_preserved=initial_modes == final_modes,
            task_stamp_assignment_preserved=initial_tasks == final_tasks,
            initial_modes=initial_modes, final_modes=final_modes,
            original_residual_before=result['selection']['audit']['original_residuals']['viol'],
            pure_mode_min_energy_before=result['selection']['audit']['pure_mode_min_energy'],
            original_residual_after=restore['original_residuals']['viol'],
            min_energy_after=restore['min_energy'], restoration_seconds=restore['seconds'],
            restoration_kkt=restore['final_kkt'], restoration_iterations=restore['iterations'],
            outer=checked['completed_outer'], inner=checked['accepted_inner_points'],
            interrupted_inner=checked['interrupted_accepted_points'], al_seconds=result['elapsed']))
    log = (HERE/'rust-validation.log').read_text().splitlines()
    assert len(log) == 18 and all('original_violation' in line for line in log)
    summary = dict(cases=rows, count=len(rows), accepted=6, rescued_previous_failures=4,
        controls_with_longer_mission=2, outer=sum(r['outer'] for r in rows),
        accepted_inner=sum(r['inner'] for r in rows),
        interrupted_inner=sum(r['interrupted_inner'] for r in rows),
        rust_outputs=len(log), execution=read(HERE/'execution.json'),
        main_source_changed=False, paper_reproduction=False)
    (HERE/'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    lines = ['| 入力 | 条件Gの復元時間 h | 直接開始の復元時間 h | 対照との差 秒 | 充電区間 G→直接 | 外側 |',
             '|---|---:|---:|---:|---:|---:|']
    for r in rows:
        old = '未受理' if r['baseline_restored_hours'] is None else f"{r['baseline_restored_hours']:.9f}"
        delta = '—' if r['change_seconds'] is None else f"+{r['change_seconds']:.2f}"
        lines.append(f"| {r['case']} | {old} | {r['restored_hours']:.9f} | {delta} | {r['baseline_charges']}→{r['direct_charges']} | {r['outer']} |")
    (HERE/'comparison.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k not in ['cases', 'execution']}))


if __name__ == '__main__':
    main()
