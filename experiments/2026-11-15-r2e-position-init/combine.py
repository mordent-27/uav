"""Keep the prespecified phase-1 summary intact; append the separately planned follow-up."""
import json
from pathlib import Path
import analyze

HERE=Path(__file__).resolve().parent
FOLLOW=HERE.parent/'2026-11-15-r2e-feasible-start'


def main():
    original=json.loads((HERE/'summary.json').read_text())
    follow_init=json.loads((FOLLOW/'initializations/tau7-seed3/result.json').read_text())
    follow=analyze.direct(FOLLOW/'cases/repaired/tau7-seed3') if follow_init['accepted'] else None
    rows=[]
    for row in original['cases']:
        selected=row['repaired']
        label='R2e-1'
        if row['case']=='tau7-seed3':selected=follow;label='R2e-2（追加対照）'
        rows.append(dict(case=row['case'],baseline=row['baseline'],phase1_initialization=row['initialization'],
            repaired=selected,phase=label,posthoc_design=row['case']=='tau7-seed3'))
    summary=dict(phase1_summary_unchanged=True,phase1_accepted=original['repaired_restored_accepted'],
        phase2_initialization=follow_init,phase2_direct=follow,cases=rows,
        new_outer=original['new_outer']+(follow['outer'] if follow else 0),
        new_inner=original['new_inner']+(follow['inner'] if follow else 0),
        new_interrupted=original['new_interrupted']+(follow['interrupted'] if follow else 0),
        new_direct_phases=original['new_phases']+(1 if follow else 0),
        total_driver_seconds=original['execution']['seconds']+json.loads((FOLLOW/'execution.json').read_text())['seconds'],
        tau7_full_attempt_wall_seconds=next(j['seconds'] for j in original['execution']['jobs'] if j['case']=='tau7-seed3')+
            json.loads((FOLLOW/'execution.json').read_text())['seconds'],
        independent_seed_families=1,paper_reproduction=False)
    (HERE/'combined-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    lines=['| 入力 | 元初期点の直接開始 h | 原制約初期化 h | 修復後の直接開始＋復元 h | 試行 |','|---|---:|---:|---:|---|']
    for row in rows:
        baseline='未受理' if row['baseline']['hours'] is None else f"{row['baseline']['hours']:.9f}"
        repaired=row['repaired'];init=follow_init if row['posthoc_design'] else row['phase1_initialization']
        a='未受理' if repaired is None or not repaired['restored_accepted'] else f"{repaired['hours']:.9f}"
        b='未受理' if not init['accepted'] else f"{init['objective']:.9f}"
        lines.append(f"| {row['case']} | {baseline} | {b} | {a} | {row['phase']} |")
    (HERE/'comparison.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k not in ['cases','phase2_initialization','phase2_direct']}))


if __name__=='__main__':main()
