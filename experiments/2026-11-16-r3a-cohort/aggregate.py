"""Provisional cohort counts: pending inputs never become successes or failures."""
import importlib.util
import json
from pathlib import Path
import statistics
import driver

BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[1]
spec=importlib.util.spec_from_file_location('r3a_readback_helpers',BASE.parent/'2026-11-16-r2i-fresh-entry/analyze.py')
prior=importlib.util.module_from_spec(spec);spec.loader.exec_module(prior)
INDICATORS=prior.INDICATORS


def read(path):return json.loads(path.read_text())


def case_row(case,status):
    row=dict(case=case,state=status['state'])
    if status['state'] not in ['finished','software_error']:return row
    raw=status['result'];outcome=raw.get('outcome') or {}
    row.update(route=raw.get('route'),error=raw['error'],
        **{key:outcome.get(key,False) for key in INDICATORS},selected=outcome.get('selected'),
        selected_hours=outcome.get('selected_hours'),driver_seconds=raw['seconds'],
        G=prior.phase(BASE/'cases/G'/case),fallback=prior.phase(BASE/'cases/fallback'/case),
        guard=prior.optional(BASE/'initializations'/case/'guard.json'),
        initialization=prior.optional(BASE/'initializations'/case/'result.json'))
    input_path=BASE/'inputs'/case/'input.json'
    row['original_audit']=prior.repair.audit(read(input_path)) if input_path.exists() else None
    if raw['error'] is None:
        assert not raw['g_reused'] and not raw['fallback_cache_used']
        assert raw['fallback_called']==(row['route']=='fallback')==(not row['G']['restoration_accepted'])
        if row['route']=='G':assert row['guard'] is None and row['fallback'] is None
        if outcome['physical_point_available']:
            selected=BASE/'runs'/case/'selected.json'
            assert prior.sha(selected)==outcome['selected_sha256']
            assert selected.read_bytes()==(BASE/'evaluations'/row['route']/case/'selected.json').read_bytes()
            if row['selected']=='restoration':assert selected.read_bytes()==(ROOT/outcome['solver_source']/'restored/solution.json').read_bytes()
        for key in ['solver_source','initialization_source']:
            if outcome[key]:(ROOT/outcome[key]).relative_to(BASE)
    if row['initialization'] and row['initialization']['accepted'] and row['selected_hours'] is not None:
        row['selected_minus_initialization_seconds']=3600*(row['selected_hours']-row['initialization']['objective'])
    return row


def counts(rows):return {key:sum(bool(r.get(key)) for r in rows) for key in INDICATORS}


def cohort_summary(names,states,rows):
    hours=[r['selected_hours'] for r in rows if r.get('physical_point_available') and r.get('selected_hours') is not None]
    return dict(planned=len(names),started=sum(states[n]['state']!='pending' for n in names),
        terminal=sum(states[n]['state'] in ['finished','software_error','unreadable_result','interrupted_recorded'] for n in names),
        finished=sum(states[n]['state']=='finished' for n in names),
        pending=sum(states[n]['state']=='pending' for n in names),
        software_errors=sum(states[n]['state']=='software_error' for n in names),
        unreadable_results=sum(states[n]['state']=='unreadable_result' for n in names),
        interrupted=sum(states[n]['state']=='interrupted_recorded' for n in names),
        partial_unresolved=sum(states[n]['state']=='partial_unresolved' for n in names),
        indicators=counts(rows),routes={route:sum(r.get('route')==route for r in rows) for route in ['G','fallback']},
        feasible_objective_hours=dict(observations=len(hours),median=statistics.median(hours) if hours else None,
            min=min(hours) if hours else None,max=max(hours) if hours else None),
        final_distribution_complete=all(states[n]['state'] in ['finished','software_error','unreadable_result','interrupted_recorded'] for n in names))


def main():
    with driver.protocol_lock():
        targets=read(BASE/'targets.json');names=targets['cases'];states=driver.case_states(BASE,names)
        rows=[case_row(n,states[n]) for n in names if states[n]['state']!='pending']
        total=cohort_summary(names,states,rows)
        by_tau={str(t):cohort_summary([r['case'] for r in targets['rows'] if r['tau']==t],states,
            [r for r in rows if r['case'].startswith(f'tau{t}-')]) for t in range(1,10)}
        batches={}
        for folder in sorted((BASE/'batches').glob('[0-9][0-9][0-9]')):
            attempts=[read(p) for p in sorted(folder.glob('attempt*.json'))]
            cases=list(dict.fromkeys(n for attempt in attempts for n in attempt['cases']))
            br=[r for r in rows if r['case'] in cases];phases=[p for r in br for p in [r.get('G'),r.get('fallback')] if p]
            data=dict(batch=folder.name,cases=cases,attempts=attempts,**cohort_summary(cases,states,br),
                rows=br,AL_phases=len(phases),completed_outer=sum(p['AL_outer'] for p in phases),
                accepted_inner=sum(p['accepted_inner'] or 0 for p in phases),interrupted_inner=sum(p['interrupted_inner'] or 0 for p in phases),
                original_negative_battery=sum(bool(r.get('original_audit') and r['original_audit']['min_energy']<0) for r in br),
                repairs_attempted=sum(bool(r.get('guard') and r['guard']['action']=='repair') for r in br),
                repairs_accepted=sum(bool(r.get('guard') and r['guard']['action']=='repair' and r['guard']['accepted']) for r in br),
                initializations_attempted=sum(r.get('initialization') is not None for r in br),
                initializations_accepted=sum(bool(r.get('initialization') and r['initialization']['accepted']) for r in br),
                costs=dict(G_AL_seconds=sum(r['G']['AL_seconds'] for r in br if r.get('G')),
                    fallback_AL_seconds=sum(r['fallback']['AL_seconds'] for r in br if r.get('fallback')),
                    restoration_seconds=sum(p['restoration_seconds'] for p in phases),
                    initialization_seconds=sum(r['initialization'].get('seconds',0.) for r in br if r.get('initialization')),
                    guard_seconds=sum(r['guard'].get('seconds',0.) for r in br if r.get('guard')),
                    driver_wall_seconds=sum(a.get('seconds',0.) for a in attempts),
                    walltime_complete=all(a['status']=='complete' for a in attempts)))
            driver.write(folder/'summary.json',data);batches[folder.name]=data
        partial=[n for n in names if states[n]['state']=='partial_unresolved']
        next_batch,next_cases=(None,[]) if partial else driver.choose_batch(names,states)
        summary=dict(date='2026-11-16',**total,by_tau=by_tau,batches=list(batches),cases=rows,
            next_batch=next_batch,next_cases=next_cases,paper_reproduction=False,
            population_success_rate_not_yet_estimated=not total['final_distribution_complete'],partial_summary=not total['final_distribution_complete'],
            failed_or_interrupted_removed=False,cached_solves=0,main_Rust_changed=False,
            point_semantics='smoothing KKT at final AL point; original constraints/fixed-branch KKT at a separate returned point')
        driver.write(BASE/'summary.json',summary)
        lines=['# R3の途中集計','',f"計画 {total['planned']}、着手 {total['started']}、終端記録 {total['terminal']}、未実行 {total['pending']}。各100本の最終分布ではない。",'',
            '| tau | 計画 | 着手 | 未実行 | 共通KKT | 追加物理KKT | 最後の復元 | 原実行可能点 | 固定分岐KKT |','|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
        for tau,data in by_tau.items():
            lines.append(f"| {tau} | {data['planned']} | {data['started']} | {data['pending']} | "+' | '.join(str(data['indicators'][k]) for k in INDICATORS)+' |')
        lines+=['','共通/追加物理KKTはAL終点、原実行可能点/固定分岐KKTは別の返却点。未実行を成功/失敗へ数えない。','',
            '| 入力 | 状態 | 採用 | 返却時間 h | 原実行可能点 | 固定分岐KKT |','|---|---|---|---:|---|---|']
        for row in rows:
            hours='—' if row.get('selected_hours') is None else f"{row['selected_hours']:.9f}"
            lines.append(f"| {row['case']} | {row['state']} | {row.get('route','—')} | {hours} | {'○' if row.get('physical_point_available') else '×'} | {'○' if row.get('selected_same_final_branch_kkt') else '×'} |")
        (BASE/'comparison.md').write_text('\n'.join(lines)+'\n')
        print(json.dumps({k:summary[k] for k in ['planned','started','terminal','pending','indicators','routes','next_batch','next_cases']},indent=2))


if __name__=='__main__':main()
