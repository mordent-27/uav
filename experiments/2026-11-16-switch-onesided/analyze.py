import json
from pathlib import Path

BASE=Path(__file__).resolve().parent


def read(p):return json.loads(p.read_text())


def verdict(old,new,control_identical):
    if control_identical:return 'same'
    tol=1e-8;o,n=old['gradient_inf'],new['gradient_inf']
    if n<=tol<o:return 'candidate_better'
    if o<=tol<n:return 'candidate_worse'
    if n>tol and o>tol:
        if n<=o/2 and new['al_decrease']>=old['al_decrease']:return 'candidate_better'
        if o<=n/2 and old['al_decrease']>=new['al_decrease']:return 'candidate_worse'
    return 'mixed'


def main():
    targets=read(BASE/'targets.json');controls=read(BASE/'reverification'/'controls.json');execution=read(BASE/'execution.json');rows=[]
    lines=['# 片側差分Hessianの一因子内側比較','','| 入力 | 役割 | 方式 | 停止 | 受理 | 試行 | 最終勾配∞ | 最終勾配2ノルム | AL減少 | 秒 | H作成/規則発動 | 判定 |',
        '|---|---|---|---|---:|---:|---:|---:|---:|---:|---|---|']
    for r in targets['states']:
        res={m:read(BASE/'inner'/f"{r['case']}-{m}"/'result.json') for m in targets['methods']}
        v=verdict(res['old'],res['onesided'],controls[r['case']]['traces_identical'])
        for m in targets['methods']:
            x=res[m];s=x['hessian_stats']
            lines.append(f"| {r['case']} | {r['role']} | {m} | {x['status']} | {x['accepted']} | {x['trials']} | {x['gradient_inf']:.4e} | {x['final_gradient_norm']:.4e} | "
                f"{x['al_decrease']:.10g} | {x['seconds']:.3f} | {s['builds']}/{s['triggered'] if m=='onesided' else '—'} | {v if m=='onesided' else ''} |")
        rows.append(dict(case=r['case'],role=r['role'],verdict=v,trace_identical=controls[r['case']]['traces_identical'],
            **{m:{k:res[m][k] for k in ['status','accepted','iterations','trials','gradient_inf','final_gradient_norm','al_decrease','seconds','hessian_stats',
                'hessian_gradient_calls','rule_at_start','rule_at_end','initial_gradient_inf']} for m in targets['methods']}))
    summary=dict(plan_commit='9d63cf5',targets=targets,execution=execution,rows=rows,unit_tests=4,inner_solves=6,outer_solver_launched=False,monte_carlo_changed=False)
    (BASE/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');(BASE/'comparison.md').write_text('\n'.join(lines)+'\n')
    print('\n'.join(lines))


if __name__=='__main__':main()
