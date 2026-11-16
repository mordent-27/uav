"""Report every frozen fresh input, including failures; standard library only, no solve."""
import hashlib
import json
from pathlib import Path
import sys

BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import repair_initialization as repair

INDICATORS=['final_common_kkt','final_both_scales_kkt','last_restoration_solver_accepted',
    'physical_point_available','selected_same_final_branch_kkt']


def read(path):return json.loads(path.read_text())
def optional(path):return read(path) if path.exists() else None
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def count(rows):return {key:sum(bool(row.get(key)) for row in rows) for key in INDICATORS}


def phase(folder):
    raw=optional(folder/'result.json')
    if raw is None:return None
    verification=optional(folder/'verification.json')
    restoration=optional(folder/'restored/result.json')
    return dict(folder=str(folder.relative_to(ROOT)),stage=raw['stage'],stop=raw['stop'],
        common=raw['final_common_pass'],both_scales=raw['final_both_scales_pass'],
        common_kkt=raw['common_kkt'],physical_kkt=raw['paper_units_kkt'],
        AL_seconds=raw['elapsed'],AL_outer=raw['total_outer'],
        accepted_inner=verification['accepted_inner_points'] if verification else None,
        interrupted_inner=verification['interrupted_accepted_points'] if verification else None,
        verification_available=verification is not None,
        restoration_attempted=restoration is not None,
        restoration_accepted=bool(restoration and restoration['accepted']),
        restoration_seconds=restoration.get('seconds',0.) if restoration else 0.,
        restoration_status=restoration.get('solver_status') if restoration else None,
        restoration_reason=restoration.get('reason') if restoration else None,
        final_AL_objective_hours=raw['objective'])


def main():
    targets=read(BASE/'targets.json');execution=read(BASE/'execution.json')
    assert execution['completed']==len(targets['cases'])==8 and execution['cached_solves']==0
    rows=[]
    for case in targets['cases']:
        folder=BASE/'runs'/case;result=read(folder/'result.json');outcome=result.get('outcome') or {}
        original=read(BASE/'inputs'/case/'input.json');audit=repair.audit(original)
        g=phase(BASE/'cases/G'/case);f=phase(BASE/'cases/fallback'/case)
        guard=optional(BASE/'initializations'/case/'guard.json')
        initialization=optional(BASE/'initializations'/case/'result.json')
        if result['error'] is None:
            assert not result['g_reused'] and not result['fallback_cache_used']
            assert result['fallback_called']==(result['route']=='fallback')
            assert result['fallback_called']==(not g['restoration_accepted'])
            if result['route']=='G':assert guard is None and f is None
            if outcome['physical_point_available']:
                selected=folder/'selected.json'
                assert sha(selected)==outcome['selected_sha256']
                assert selected.read_bytes()==(BASE/'evaluations'/result['route']/case/'selected.json').read_bytes()
                if outcome['selected']=='restoration':
                    assert selected.read_bytes()==(ROOT/outcome['solver_source']/'restored/solution.json').read_bytes()
        row=dict(case=case,route=result.get('route'),error=result['error'],
            **{key:outcome.get(key,False) for key in INDICATORS},selected=outcome.get('selected'),
            selected_hours=outcome.get('selected_hours'),selected_sha256=outcome.get('selected_sha256'),
            original_audit=audit,G=g,fallback=f,guard=guard,initialization=initialization,
            initialization_seconds=initialization.get('seconds',0.) if initialization else 0.,
            guard_seconds=guard.get('seconds',0.) if guard else 0.,driver_seconds=result['seconds'],
            step_seconds={step['phase']+'/'+step['script']:step['seconds'] for step in result['steps']})
        if initialization and initialization['accepted'] and row['selected_hours'] is not None:
            row['selected_minus_initialization_seconds']=3600*(row['selected_hours']-initialization['objective'])
        rows.append(row)
    phases=[p for row in rows for p in [row['G'],row['fallback']] if p]
    costs={kind:sum(row[kind][key] for row in rows if row[kind])
        for kind,key in [('G','AL_seconds'),('fallback','AL_seconds')]}
    summary=dict(date='2026-11-16',targets=targets['cases'],inputs=8,cached_solves=0,
        all_targets_preserved=True,counts=count(rows),
        software_errors=[r['case'] for r in rows if r['error']],
        routes={route:sum(r['route']==route for r in rows) for route in ['G','fallback']},
        original_feasible=sum(r['original_audit']['accepted'] for r in rows),
        original_negative_battery=sum(r['original_audit']['min_energy']<0 for r in rows),
        guards_run=sum(r['guard'] is not None for r in rows),
        repairs_attempted=sum(bool(r['guard'] and r['guard']['action']=='repair') for r in rows),
        repairs_accepted=sum(bool(r['guard'] and r['guard']['action']=='repair' and r['guard']['accepted']) for r in rows),
        initialization_attempted=sum(r['initialization'] is not None for r in rows),
        initialization_accepted=sum(bool(r['initialization'] and r['initialization']['accepted']) for r in rows),
        AL_phases=len(phases),G_phases=sum(r['G'] is not None for r in rows),
        fallback_phases=sum(r['fallback'] is not None for r in rows),
        completed_outer=sum(p['AL_outer'] for p in phases),
        accepted_inner=sum(p['accepted_inner'] or 0 for p in phases),
        interrupted_inner=sum(p['interrupted_inner'] or 0 for p in phases),
        G_physical_precision_not_passed_but_kept=[r['case'] for r in rows if r['route']=='G' and not r['final_both_scales_kkt']],
        returned_by_saved_certificate=[r['case'] for r in rows if r['selected']=='certificate'],
        returned_by_physical_point_only=[r['case'] for r in rows if r['selected'] in ['original','constructed','initialization']],
        execution_wall_seconds=execution['seconds'],
        costs=dict(G_AL_seconds=costs['G'],fallback_AL_seconds=costs['fallback'],
            restoration_seconds=sum(p['restoration_seconds'] for p in phases),
            guard_seconds=sum(r['guard_seconds'] for r in rows),
            initialization_seconds=sum(r['initialization_seconds'] for r in rows),
            sum_case_wall_seconds=sum(r['driver_seconds'] for r in rows),
            note='All solves fresh; elapsed walltime includes startup/verification. Sum of per-case walltimes is neither CPU time nor sequential runtime.'),
        by_tau={str(tau):dict(inputs=2,counts=count([r for r in rows if r['case'].startswith(f'tau{tau}-')])) for tau in [1,3,5,7]},
        fixed_entry_executed_on_new_seeds=True,small_prospective_sample=True,
        population_success_rate_precision_claimed=False,paper_reproduction=False,monte_carlo_rerun=False,
        main_Rust_changed=False,point_semantics='smoothing KKT at final AL point; original feasibility/fixed-branch KKT at a separate returned point',cases=rows)
    (BASE/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    lines=['# R2i：未使用seedの固定入口の結果','',
        '8入力は初期点監査前に固定し、全件キャッシュなしで実行。失敗を見た差替えなし。小規模な前向き確認である。',
        '共通/追加物理KKTはAL終点、原実行可能性/固定分岐KKTは別の返却点の判定。','',
        '| 入力 | 原初期電池最小 | G停止 | 採用 | 共通KKT | 追加物理KKT | 最後の復元 | 返却点 | 固定分岐KKT | 時間 h | 壁時計 秒 |',
        '|---|---:|---|---|---|---|---|---|---|---:|---:|']
    for row in rows:
        flags=['○' if row[key] else '×' for key in INDICATORS]
        hours='—' if row['selected_hours'] is None else f"{row['selected_hours']:.9f}"
        stop='—' if row['G'] is None else f"{row['G']['stage']}:{row['G']['stop']}"
        lines.append(f"| {row['case']} | {row['original_audit']['min_energy']:+.6f} | {stop} | {row['route']} | "+' | '.join(flags)+f" | {hours} | {row['driver_seconds']:.3f} |")
    lines+=['',f"全体壁時計 {execution['seconds']:.3f} 秒。今回はG、必要な補助経路、初期化を全て新規に求解した。",'']
    (BASE/'comparison.md').write_text('\n'.join(lines))
    print(json.dumps({key:summary[key] for key in ['routes','counts','original_feasible','original_negative_battery',
        'repairs_attempted','initialization_accepted','AL_phases','completed_outer','accepted_inner',
        'interrupted_inner','execution_wall_seconds','costs','software_errors']},indent=2))


if __name__=='__main__':main()
