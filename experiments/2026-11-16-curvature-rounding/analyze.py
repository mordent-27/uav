import json
from pathlib import Path

BASE=Path(__file__).resolve().parent


def read(p):return json.loads(p.read_text())
def e(x):return f'{x:.3e}'


def main():
    targets=read(BASE/'targets.json');execution=read(BASE/'execution.json');states=[];lines=['# 低曲率方向と点の丸め','']
    lines += ['## A. 旧Hessianの固有方向でのDecimal曲率（事前判定）','',
        '| 入力 | 方向 | 旧Hの固有値 | q（100桁, 幅1e-24） | 判定 | 見かけの負曲率 | q（80桁, 幅1e-8） | 幅1e-8の活性切替 | ‖Hv−H·v‖₂（幅1e-10） |',
        '|---|---|---:|---:|---|---|---:|---:|---:|']
    for row in targets['contexts']:
        case=row['case'];r=read(BASE/'states'/case/'result.json');v=read(BASE/'reverification'/f'{case}.json')
        p=read(BASE/'posthoc'/f'{case}.json');states.append(dict(case=case,result=r,reverification=v,posthoc=p))
        for d in r['directions']:
            wide=next(x for x in d['values'] if x['width']=='1e-8')
            lines.append(f"| {case} | {d['name']} | {d['native_eigenvalue']:+.3e} | {d['q100_float']:+.3e} | {d['classification']} | "
                f"{'はい' if d['apparent_negative'] else '—'} | {wide['q_float']:+.3e} | {wide['active_switches']} | {e(d['hv_minus_native_norm'])} |")
    lines += ['','## B. 点の丸め（事前判定と記述値）','',
        '| 入力 | 丸め下限: 最悪 | 一様rms | 単一座標 | 除いた固有対 | x0 勾配∞ | x1 | x2 | x3 | x1r（binary64） | x3r（binary64） | 判定 x1 / x3 |',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|']
    for s in states:
        R=s['result']['rounding'];f=R['floors'];g=[row['gradient_inf'] for row in R['rows']]
        lines.append(f"| {s['case']} | {e(f['worst_half_ulp'])} | {e(f['uniform_rms'])} | {e(f['single_half_ulp'])} | {R['dropped']}/{R['kept']+R['dropped']} | "
            + ' | '.join(e(x) for x in g)+f" | {e(R['rounded']['x1']['gradient_inf'])} | {e(R['rounded']['x3']['gradient_inf'])} | "
            f"{R['rounded']['x1']['verdict']} / {R['rounded']['x3']['verdict']} |")
    lines += ['','## 計画外の事後診断：PHRの活性切替','',
        '| 入力 | x0で切替に最も近い不等式 | μ+ρg | μ | Newton点列での切替 | step3/step2の反転 ‖d₂+d₃‖/‖d₂‖ |','|---|---|---:|---:|---|---:|']
    for s in states:
        p=s['posthoc'];n=p['nearest_to_switch_at_x0'][0];path=p['newton_path']
        moves=', '.join(f"{k}:{len(path[k]['switched_from_x0'])}" for k in ['x1','x2','x3'])
        lines.append(f"| {s['case']} | {n['kind']} | {n['shifted']:+.3e} | {n['mu']:.3e} | x0からの切替数 {moves} | {p['step2_plus_step3_over_step2']:.3e} |")
    summary=dict(plan_commit='eb840ce',targets=targets,execution=execution,optimizer_launched=False,outer_solver_launched=False,
        unit_tests=10,monte_carlo_changed=False,
        states=[dict(case=s['case'],variables=s['result']['variables'],rho=s['result']['rho'],status=s['result']['status'],
            scalar_evaluations=s['result']['scalar_evaluations'],seconds=s['result']['seconds'],
            hessian_rebuild_max_difference=s['result']['hessian_rebuild_max_difference'],native_gradient_inf=s['result']['native_gradient_inf'],
            curvature=[{k:d[k] for k in ['name','native_eigenvalue','q100_float','classification','apparent_negative','valid','active_switches_100',
                'native_minus_q100','hv_minus_native_norm','hv_eigen_residual','hv_rayleigh']}|dict(widths={x['width']:dict(q=x['q_float'],switches=x['active_switches']) for x in d['values']})
                for d in s['result']['directions']],
            rounding={k:s['result']['rounding'][k] for k in ['kept','dropped','cut','eigen_min','eigen_max','dropped_eigenvalues','floors','rows','prior_gradient_max_difference']}
                |dict(rounded={n:{k:v for k,v in x.items() if k not in ('point','gradient')} for n,x in s['result']['rounding']['rounded'].items()}),
            reverification={k:s['reverification'][k] for k in ['gradient_checks','all_gradients_agree','verdicts_100','floors_reproduced','rounded_points_reproduced','state_outputs_unchanged','scalar_evaluations']},
            posthoc_not_planned={k:s['posthoc'][k] for k in ['nearest_to_switch_at_x0','newton_path','step2_plus_step3_over_step2','low_direction_switches','scalar_evaluations']})
            for s in states])
    (BASE/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');(BASE/'comparison.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps(dict(states=len(states),seconds=execution['seconds'],evaluations=[s['result']['scalar_evaluations'] for s in states])))


if __name__=='__main__':main()
