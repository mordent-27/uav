import json
from pathlib import Path

BASE=Path(__file__).resolve().parent;ROOT=BASE.parents[1]


def read(p):return json.loads(p.read_text())


def compare(x,y):
    """PLAN: X better than Y if only X passes, or neither passes and X's max common KKT <= half of Y's and X's max physical KKT <= Y's."""
    if x['stage_pass'] and not y['stage_pass']:return 'better'
    if y['stage_pass'] and not x['stage_pass']:return 'worse'
    if x['stage_pass'] and y['stage_pass']:return 'both_pass'
    if x['max_common_kkt']<=y['max_common_kkt']/2 and x['max_paper_kkt']<=y['max_paper_kkt']:return 'better'
    if y['max_common_kkt']<=x['max_common_kkt']/2 and y['max_paper_kkt']<=x['max_paper_kkt']:return 'worse'
    return 'mixed'


def main():
    targets=read(BASE/'targets.json');rows=[];lines=['# 外側ALの内側を替えたstage13','',
        '| 入力 | 方式 | 停止 | 外側 | 合格 | 共通KKT最大 | 物理KKT最大 | 目的値 | 最終rho | 秒 | 内側の停止 | Decimal評価 |','|---|---|---|---:|---|---:|---:|---:|---:|---:|---|---:|']
    for s in targets['states']:
        r3=read(ROOT/s['r3_result']);r3m=dict(stop=r3['stop'],completed_outer=r3['completed_outer'],stage_pass=r3['stage_pass'],
            max_common_kkt=max(r3['common_kkt'].values()),max_paper_kkt=max(r3['paper_units_kkt'].values()),objective=r3['objective'],rho=r3['rho'],seconds=r3['seconds'])
        lines.append(f"| {s['case']} | R3記録 | {r3m['stop']} | {r3m['completed_outer']} | {r3m['stage_pass']} | {r3m['max_common_kkt']:.3e} | {r3m['max_paper_kkt']:.3e} | {r3m['objective']:.9f} | {r3m['rho']:.0e} | {r3m['seconds']:.1f} | — | — |")
        res={a:read(BASE/'stages'/f"{s['case']}-{a}"/'result.json') for a in targets['arms']}
        for a in targets['arms']:
            x=res[a];lines.append(f"| {s['case']} | {a} | {x['stop']} | {x['completed_outer']} | {x['stage_pass']} | {x['max_common_kkt']:.3e} | {x['max_paper_kkt']:.3e} | "
                f"{x['objective']:.9f} | {x['rho']:.0e} | {x['seconds']:.1f} | {x['inner_statuses']} | {x['decimal_calls']} |")
        rows.append(dict(case=s['case'],r3=r3m,rules_B1_vs_A0=compare(res['B1'],res['A0']),tr_A0_vs_L=compare(res['A0'],res['L']),
            arms={a:{k:res[a][k] for k in ['stop','completed_outer','stage_pass','common_pass','physical_pass','max_common_kkt','max_paper_kkt','common_kkt','paper_units_kkt',
                'objective','rho','seconds','wall_seconds','inner_statuses','decimal_calls','decimal_value_gap_at_start']} for a in targets['arms']}))
    lines += ['','| 入力 | 規則（B1対A0） | TR修正（A0対L） |','|---|---|---|']
    for r in rows:lines.append(f"| {r['case']} | {r['rules_B1_vs_A0']} | {r['tr_A0_vs_L']} |")
    summary=dict(plan_commit='95ff302',targets=targets,execution=read(BASE/'execution.json'),rows=rows,unit_tests=3,stages=6,monte_carlo_changed=False)
    (BASE/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');(BASE/'comparison.md').write_text('\n'.join(lines)+'\n');print('\n'.join(lines))


if __name__=='__main__':main()
