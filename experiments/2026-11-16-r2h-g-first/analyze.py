"""Aggregate frozen G-first decisions after execution, without altering their outputs."""
import hashlib
import json
from pathlib import Path

BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[1]
INDICATORS=['final_common_kkt','final_both_scales_kkt','last_restoration_solver_accepted',
    'physical_point_available','selected_same_final_branch_kkt','both_scales_kkt_and_final_certificate']


def read(path):return json.loads(path.read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def count(rows):return {key:sum(bool(r[key]) for r in rows) for key in INDICATORS}


def numerical_cost(outcome):
    source=ROOT/outcome['solver_source'] if outcome['solver_source'] else None
    raw=read(source/'result.json') if source else {}
    restored=read(source/'restored/result.json') if source and (source/'restored/result.json').exists() else {}
    init=ROOT/outcome['initialization_source']
    guard=read(init/'guard.json') if (init/'guard.json').exists() else {}
    initialization=read(init/'result.json') if (init/'result.json').exists() else {}
    return dict(AL_seconds=raw.get('elapsed',0.),AL_outer=raw.get('total_outer',0),
        restoration_seconds=restored.get('seconds',0.),guard_seconds=guard.get('seconds',0.),
        initialization_seconds=initialization.get('seconds',0.),
        note='saved numerical-phase times; excludes Python startup, verification and shared scheduling; cached values are historical')


def main():
    catalog=read(BASE/'catalog.json');execution=read(BASE/'execution.json')
    assert execution['completed']==25 and execution['errors']==0
    rows=[];g_all=[];f_used=[];baseline=[]
    for case,entry in catalog['cases'].items():
        result=read(BASE/'runs'/case/'result.json');g=read(BASE/'evaluations/G'/case/'result.json')
        assert result['error'] is None
        outcome=result['outcome'];g_all.append(g)
        fallback=result['route']=='fallback'
        assert fallback==result['fallback_called']==(not g['last_restoration_solver_accepted'])
        fallback_dir=BASE/'evaluations/fallback'/case
        assert fallback_dir.exists()==fallback
        if fallback:f_used.append(outcome)
        else:assert outcome==g and not result['fallback_cache_used']
        selected=BASE/'runs'/case/'selected.json'
        if outcome['physical_point_available']:
            assert sha(selected)==outcome['selected_sha256']
            assert selected.read_bytes()==(BASE/'evaluations'/result['route']/case/'selected.json').read_bytes()
        if not fallback:
            assert selected.read_bytes()==(ROOT/result['g_source']/'restored/solution.json').read_bytes()
        # Objective comparisons below are reporting only, after the route is irrevocably fixed.
        old_folder=ROOT/entry['fallback_evaluation'];old=read(old_folder/'result.json');baseline.append(old)
        if fallback:assert selected.read_bytes()==(old_folder/'selected.json').read_bytes()
        raw=read(ROOT/result['g_source']/'result.json')
        verification=read(ROOT/result['g_source']/'verification.json')
        row=dict(case=case,route=result['route'],G_reused=result['g_reused'],
            fallback_called=result['fallback_called'],**{key:outcome[key] for key in INDICATORS},
            selected=outcome['selected'],selected_hours=outcome['selected_hours'],
            selected_sha256=outcome['selected_sha256'],
            G_common=g['final_common_kkt'],G_both_scales=g['final_both_scales_kkt'],
            G_restoration=g['last_restoration_solver_accepted'],G_stage=raw['stage'],G_stop=raw['stop'],
            G_common_kkt_max=max(raw['common_kkt'].values()),G_physical_kkt_max=max(raw['paper_units_kkt'].values()),
            G_accepted_inner=verification['accepted_inner_points'],
            G_interrupted_inner=verification['interrupted_accepted_points'],
            G_cost=numerical_cost(g),fallback_cost=numerical_cost(outcome) if fallback else None,
            baseline_fallback_hours=old['selected_hours'],
            selected_minus_baseline_seconds=3600*(outcome['selected_hours']-old['selected_hours']),
            driver_case_seconds=result['seconds'],all_returned_checks_passed=True)
        rows.append(row)
    cohorts=dict(
        existing_regression17=[r['case'] for r in rows if r['case']=='fig1' or int(r['case'].split('seed')[1])<=3],
        previously_healthy4=['tau1-seed101','tau3-seed103','tau5-seed105','tau7-seed107'],
        previously_negative4=['tau5-seed203','tau5-seed205','tau7-seed400','tau7-seed401'])
    strata={key:dict(cases=names,counts=count([r for r in rows if r['case'] in names]),
        routes={route:sum(r['route']==route for r in rows if r['case'] in names) for route in ['G','fallback']})
        for key,names in cohorts.items()}
    new=[r for r in rows if not r['G_reused']]
    totals=dict(G_AL_seconds=sum(r['G_cost']['AL_seconds'] for r in rows),
        G_restoration_seconds=sum(r['G_cost']['restoration_seconds'] for r in rows),
        fallback_AL_seconds=sum(r['fallback_cost']['AL_seconds'] for r in rows if r['fallback_called']),
        fallback_restoration_seconds=sum(r['fallback_cost']['restoration_seconds'] for r in rows if r['fallback_called']),
        fallback_guard_seconds=sum(r['fallback_cost']['guard_seconds'] for r in rows if r['fallback_called']),
        fallback_initialization_seconds=sum(r['fallback_cost']['initialization_seconds'] for r in rows if r['fallback_called']))
    summary=dict(date='2026-11-16',all_seen_design_and_regression=True,independent_success_rate_estimated=False,
        paper_reproduction=False,monte_carlo_rerun=False,main_Rust_changed=False,
        inputs=25,new_G=len(new),cached_G=17,counts=count(rows),G_counts=count(g_all),
        fallback_used_counts=count(f_used),baseline_fallback_counts=count(baseline),
        routes={route:sum(r['route']==route for r in rows) for route in ['G','fallback']},
        accepted_G_outputs_preserved_exactly=sum(r['route']=='G' for r in rows),
        fallback_outputs_preserved_exactly=len(f_used),returned_hashes_checked=25,
        G_gate_does_not_require_physical_KKT=[r['case'] for r in rows if r['route']=='G' and not r['final_both_scales_kkt']],
        new_G_counts=count([g for g in g_all if g['case'] in catalog['new_G_cases']]),
        new_G_stages=sum(len(read(BASE/'cases/G'/r['case']/'verification.json')['stages']) for r in new),
        new_G_outer=sum(r['G_cost']['AL_outer'] for r in new),
        new_G_accepted_inner=sum(r['G_accepted_inner'] for r in new),
        new_G_interrupted_inner=sum(r['G_interrupted_inner'] for r in new),
        new_G_stop=[dict(case=r['case'],stage=r['G_stage'],stop=r['G_stop'],restored=r['G_restoration']) for r in new],
        execution_wall_seconds=execution['seconds'],
        cost_proxy_saved_phase_seconds=totals,
        proxy_sequential_seconds=sum(totals.values()),
        cost_note='17 G phases and every used fallback were computed previously. Current walltime excludes those solves. Sum of recorded phase times is a rough sequential cost proxy, not a fresh 25-input runtime.',
        objective_lower_than_fallback=sum(r['selected_minus_baseline_seconds'] < -1e-5 for r in rows),
        objective_higher_than_fallback=sum(r['selected_minus_baseline_seconds'] > 1e-5 for r in rows),
        strata=strata,cases=rows,
        point_semantics='smoothing KKT is evaluated at final AL point; physical feasibility/fixed-branch KKT at a separate returned point; no smoothing KKT inferred at returned point')
    (BASE/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    lines=['# R2h：G優先の事後集計','',
        '全25入力は既見の設計/回帰例。経路はGの受理だけで固定し、以下の目的値比較は採用後の報告。',
        '共通/両尺度KKTは最終AL点、原実行可能性/固定分岐KKTは別の返却点の判定。','',
        '| 入力 | 採用 | 共通KKT | 両尺度KKT | 最後の復元 | 固定分岐証明 | 返却時間 h | 補助経路単独との差 秒 |',
        '|---|---|---|---|---|---|---:|---:|']
    for r in rows:
        flags=['○' if r[key] else '×' for key in ['final_common_kkt','final_both_scales_kkt',
            'last_restoration_solver_accepted','selected_same_final_branch_kkt']]
        lines.append(f"| {r['case']} | {r['route']} | "+' | '.join(flags)+
            f" | {r['selected_hours']:.9f} | {r['selected_minus_baseline_seconds']:+.3f} |")
    lines+=['','## 今回新たに解いたG','',
        '| 入力 | 最終段階 | 停止 | 共通KKT最大 | 物理KKT最大 | AL 秒 | 復元受理 |',
        '|---|---:|---|---:|---:|---:|---|']
    for r in new:
        lines.append(f"| {r['case']} | {r['G_stage']} | {r['G_stop']} | {r['G_common_kkt_max']:.3e} | {r['G_physical_kkt_max']:.3e} | {r['G_cost']['AL_seconds']:.2f} | {'○' if r['G_restoration'] else '×'} |")
    lines+=['',f"今回ドライバー壁時計 {execution['seconds']:.3f} 秒。G17例と採用された補助経路の求解時間は含まない。",
        f"保存された数値フェーズ時間の直列合計目安 {sum(totals.values()):.3f} 秒（検証/起動/スケジューリング等を除く）。",'']
    (BASE/'comparison.md').write_text('\n'.join(lines))
    print(json.dumps({key:summary[key] for key in ['routes','counts','G_counts','new_G_counts',
        'execution_wall_seconds','proxy_sequential_seconds','objective_lower_than_fallback','objective_higher_than_fallback']},indent=2))


if __name__=='__main__':main()
