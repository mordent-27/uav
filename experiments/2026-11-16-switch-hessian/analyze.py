import json
from pathlib import Path

BASE=Path(__file__).resolve().parent


def read(p):return json.loads(p.read_text())
def e(x):return f'{x:.3e}'


def main():
    targets=read(BASE/'targets.json');fix=read(BASE/'fix'/'result.json');verify=read(BASE/'reverification'/'fix.json');execution=read(BASE/'execution.json')
    switch=sorted((read(BASE/'switch'/f"{r['case']}.json") for r in targets['switch']['states']),key=lambda r:(r['rho'],r['case']))
    b=fix['binary64'];k=b['lattice']['k'];at_limit=sum(abs(v)==targets['fix']['lattice']['limit'] for v in k)
    lines=['# 切替をまたがないHessian','','## ゲート（x0での曲率の照合）','','| 方向 | Decimal | 旧H | H_fix | Decimal/旧H | Decimal/H_fix |','|---|---:|---:|---:|---:|---:|']
    for g in fix['gate']:lines.append(f"| {g['direction']} | {g['decimal']:.6e} | {g['old']:.6e} | {g['fix']:.6e} | {g['ratio_old']:.6f} | {g['ratio_fix']:.10f} |")
    lines += ['','## 高精度点のNewton（H_fix固定）','','| 点 | 勾配∞ | 区間17の余裕 | c₃₀のs | 他の切替 | step長 | stepの曲率比 |','|---|---:|---:|---:|---:|---:|---:|']
    for r in fix['newton']:
        lines.append(f"| x{r['index']} | {e(r['gradient_inf'])} | {e(r['segment_margin'])} | {r['c30_s']:+.3e} | {r['other_switches']} | "
            f"{e(r['step_norm']) if 'step_norm' in r else '—'} | {r['step_ratio_fix']:.6g} |" if 'step_ratio_fix' in r else
            f"| x{r['index']} | {e(r['gradient_inf'])} | {e(r['segment_margin'])} | {r['c30_s']:+.3e} | {r['other_switches']} | — | — |")
    lines += ['','## binary64の点（x*=x'+str(fix['first_reaching'])+'）','','| 点 | Decimal勾配∞ | native勾配∞ | x0から変わった座標 |','|---|---:|---:|---:|',
        f"| x*（高精度） | {e(fix['newton'][fix['first_reaching']]['gradient_inf'])} | — | — |",
        f"| 最近点x*r | {e(b['rounded']['gradient_inf'])} | {e(b['rounded']['native_gradient_inf'])} | {b['rounded']['changed_from_x0']} |",
        f"| 格子点x*ℓ | {e(b['lattice']['gradient_inf'])} | {e(b['lattice']['native_gradient_inf'])} | {b['lattice']['changed_from_x0']} |",
        '',f"判定：{b['verdict']}。格子探索は{b['lattice']['search']['sweeps']}周、{b['lattice']['search']['moved']}座標を移動、|k|=8の上限に{at_limit}座標。",
        '','## 24状態で切替をまたぐ座標','','| 入力 | 段階 | rho | 対象区間 | またぐ座標 | 最も近い余裕 |','|---|---|---:|---:|---:|---:|']
    for r in switch:
        n=r['nearest_margins'][0]['margin'] if r['nearest_margins'] else None
        lines.append(f"| {r['case']} | {r['stage']} | {r['rho']:.0e} | {r['applicable_segments']} | {r['straddling']}{' '+str(r['straddling_segments']) if r['straddling'] else ''} | {'—' if n is None else f'{n:+.3e}'} |")
    summary=dict(plan_commit='62342e7',targets=targets,execution=execution,optimizer_launched=False,unit_tests=5,monte_carlo_changed=False,
        fix={k_:v for k_,v in fix.items() if k_ not in ('points',)},fix_reverification=verify,lattice_coordinates_at_limit=at_limit,
        switch=switch,states_with_straddling=[r['case'] for r in switch if r['straddling']])
    (BASE/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');(BASE/'comparison.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps(dict(at_limit=at_limit,states_with_straddling=summary['states_with_straddling'],seconds=execution['seconds'])))


if __name__=='__main__':main()
