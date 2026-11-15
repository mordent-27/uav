"""Paired outcomes with preservation and repair strata; failures remain in every denominator."""
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]


def read(path):return json.loads(path.read_text())


def brief(folder):
    result=read(folder/'result.json');verified=read(folder/'verification.json')
    assert read(folder/'steps.json')==dict(run='ok',restore='ok',verify='ok')
    assert verified['original_jacobian_stationarity_verified']
    path=folder/'restored/result.json';restored=read(path) if path.exists() else dict(accepted=False)
    return dict(path=str(folder.relative_to(ROOT)),common_pass=result['final_common_pass'],
        physical_pass=result['final_both_scales_pass'],restoration_accepted=restored['accepted'],
        raw_hours=result['objective'],hours=restored.get('objective') if restored['accepted'] else None,
        common_kkt=result['common_kkt'],physical_kkt=result['paper_units_kkt'],
        stop=result['stop'],charges=result['selection']['charging_segments'],
        original_residual=restored.get('original_residuals',{}).get('viol'),min_energy=restored.get('min_energy'),
        restoration_status=restored.get('solver_status'),restoration_reason=restored.get('reason'),
        al_seconds=result['elapsed'],restoration_seconds=restored.get('seconds',0.),
        verified_outer=verified['completed_outer'],verified_inner=verified['accepted_inner_points'],
        interrupted_inner=verified['interrupted_accepted_points'])


def aggregate(rows):
    return dict(cases=len(rows),preserved_inputs=sum(r['action']=='keep_original' for r in rows),
        repair_attempts=sum(r['action']=='repair' for r in rows),
        physical_constructions_accepted=sum(r['guard']['accepted'] and r['action']=='repair' for r in rows),
        fixed_branch_initializations_accepted=sum(bool(r['initialization'] and r['initialization']['accepted']) for r in rows),
        baseline_kkt=sum(r['baseline']['common_pass'] for r in rows),
        candidate_kkt=sum(bool(r['candidate'] and r['candidate']['common_pass']) for r in rows),
        candidate_both_scales_kkt=sum(bool(r['candidate'] and r['candidate']['physical_pass']) for r in rows),
        baseline_restoration_accepted=sum(r['baseline']['restoration_accepted'] for r in rows),
        candidate_restoration_accepted=sum(bool(r['candidate'] and r['candidate']['restoration_accepted']) for r in rows),
        gained_restoration=sum(not r['baseline']['restoration_accepted'] and bool(r['candidate'] and r['candidate']['restoration_accepted']) for r in rows),
        lost_restoration=sum(r['baseline']['restoration_accepted'] and not bool(r['candidate'] and r['candidate']['restoration_accepted']) for r in rows))


def main():
    execution=read(HERE/'execution.json');rows=[]
    for job in execution['jobs']:
        assert job['error'] is None
        case=job['case'];folder=HERE/'initializations'/case
        guard=read(folder/'guard.json');original=read(folder/'original-state.json')
        baseline=brief(ROOT/job['baseline'])
        assert original['y']==read(ROOT/job['baseline']/'source.json')['y']
        candidate=brief(ROOT/job['candidate']) if job['candidate'] else None
        if job['candidate_reuses_baseline']:
            assert job['guard_action']=='keep_original' and guard['same_original_y']
            assert job['candidate']==job['baseline']
        initialization=read(folder/'result.json') if (folder/'result.json').exists() else None
        if initialization:
            assert read(folder/'verification.json')['accepted']==initialization['accepted']
        delta=None if candidate is None or baseline['hours'] is None or candidate['hours'] is None else 3600*(candidate['hours']-baseline['hours'])
        rows.append(dict(case=case,group=job['group'],action=job['guard_action'],guard=guard,
            baseline=baseline,baseline_reused=job['baseline_reused'],candidate=candidate,
            candidate_reuses_baseline=job['candidate_reuses_baseline'],initialization=initialization,
            change_seconds=delta,measured_new_work_seconds=job['seconds'],
            candidate_numerical_seconds=guard['seconds']+(initialization['seconds'] if initialization else 0.)+
                (candidate['al_seconds']+candidate['restoration_seconds'] if candidate else 0.)))
    regression=[r for r in rows if r['group']=='regression'];holdout=[r for r in rows if r['group']=='holdout']
    new=[brief(folder) for folder in sorted((HERE/'cases').glob('*/*'))]
    summary=dict(regression=aggregate(regression),holdout=aggregate(holdout),cases=rows,
        new_phases=len(new),new_outer=sum(p['verified_outer'] for p in new),
        new_inner=sum(p['verified_inner'] for p in new),new_interrupted=sum(p['interrupted_inner'] for p in new),
        execution=execution,main_source_changed=False,paper_reproduction=False)
    (HERE/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    lines=[]
    for label,group in [('回帰17例',regression),('設計未使用4例',holdout)]:
        lines += ['## '+label,'','| 入力 | 初期点の扱い | 元の直接開始＋復元 h | 条件付き修復＋直接開始＋復元 h | 差 秒 |',
                  '|---|---|---:|---:|---:|']
        for row in group:
            before='未受理' if row['baseline']['hours'] is None else f"{row['baseline']['hours']:.9f}"
            candidate=row['candidate'];after='未受理' if candidate is None or candidate['hours'] is None else f"{candidate['hours']:.9f}"
            delta='—' if row['change_seconds'] is None else f"{row['change_seconds']:+.2f}"
            action='そのまま保持' if row['action']=='keep_original' else f"修復（構成時{len(row['guard']['changes'])}点）"
            lines.append(f"| {row['case']} | {action} | {before} | {after} | {delta} |")
        lines.append('')
    (HERE/'comparison.md').write_text('\n'.join(lines))
    print(json.dumps({k:v for k,v in summary.items() if k not in ['cases','execution']}))


if __name__=='__main__':main()
