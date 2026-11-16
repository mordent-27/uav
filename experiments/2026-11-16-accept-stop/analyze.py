import json
from pathlib import Path

BASE=Path(__file__).resolve().parent


def read(p):return json.loads(p.read_text())


def acceptance(a,b):
    t=1e-8;ga,gb=a['decimal_gradient_inf'],b['decimal_gradient_inf']
    if gb<=t<ga:return 'B_better'
    if ga<=t<gb:return 'B_worse'
    if ga>t and gb>t:
        if gb<=ga/2 and b['decimal_al_decrease']>=a['decimal_al_decrease']:return 'B_better'
        if ga<=gb/2 and a['decimal_al_decrease']>=b['decimal_al_decrease']:return 'B_worse'
    return 'mixed'


def stopping(base,floor):
    if floor['status']!='converged_floor':return 'no_change'
    return 'too_early' if base['decimal_gradient_inf']<=floor['decimal_gradient_inf']/2 else 'saved_work'


def main():
    targets=read(BASE/'targets.json');rows=[];lines=['# 受理規則と停止基準の2×2','',
        '| 入力 | 方式 | 停止 | 受理 | native勾配∞ | Decimal勾配∞ | AL減少（Decimal） | 秒 | Decimal評価 | 停止時のF |','|---|---|---|---:|---:|---:|---:|---:|---:|---:|']
    for s in targets['states']:
        r={a:read(BASE/'inner'/f"{s['case']}-{a}"/'result.json') for a in targets['arms']}
        for a in targets['arms']:
            x=r[a];lines.append(f"| {s['case']} | {a} | {x['status']} | {x['accepted']} | {x['gradient_inf']:.4e} | {x['decimal_gradient_inf']:.4e} | {x['decimal_al_decrease']:.12g} | "
                f"{x['seconds']:.3f} | {x['decimal_calls']} | {x['stop'].get('floor',float('nan')):.3e} |")
        control=s['role']=='control';same=max(abs(r[a]['decimal_al_decrease']-r['A0']['decimal_al_decrease'])/abs(r['A0']['decimal_al_decrease']) for a in targets['arms'])
        verdict=dict(acceptance=acceptance(r['A0'],r['B0']),stop_A=stopping(r['A0'],r['A1']),stop_B=stopping(r['B0'],r['B1']))
        if control:verdict['control']='no_effect' if all(r[a]['decimal_gradient_inf']<=1e-8 for a in targets['arms']) and same<=1e-9 else 'effect'
        rows.append(dict(case=s['case'],role=s['role'],verdict=verdict,al_decrease_max_relative_spread=same,
            arms={a:{k:r[a][k] for k in ['status','accepted','iterations','trials','gradient_inf','decimal_gradient_inf','decimal_gradient_norm','decimal_al_decrease','seconds','decimal_calls','stop','final_floor','decimal_value_gap_at_start']} for a in targets['arms']}))
    lines += ['','| 入力 | 受理規則（B0対A0） | 停止基準（A1対A0） | 停止基準（B1対B0） | 対照 |','|---|---|---|---|---|']
    for r in rows:lines.append(f"| {r['case']} | {r['verdict']['acceptance']} | {r['verdict']['stop_A']} | {r['verdict']['stop_B']} | {r['verdict'].get('control','')} |")
    summary=dict(plan_commit='e51ca38',targets=targets,execution=read(BASE/'execution.json'),rows=rows,previous_a0=read(BASE/'reverification'/'previous-a0.json'),
        unit_tests=5,inner_solves=12,outer_solver_launched=False,monte_carlo_changed=False)
    (BASE/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');(BASE/'comparison.md').write_text('\n'.join(lines)+'\n');print('\n'.join(lines))


if __name__=='__main__':main()
