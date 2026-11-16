import json
from collections import defaultdict
from pathlib import Path

BASE=Path(__file__).resolve().parent


def read(p):return json.loads(p.read_text())
def e(x):return f'{x:.3e}'


def main():
    targets=read(BASE/'targets.json');side=read(BASE/'side'/'result.json');verify=read(BASE/'reverification'/'side.json')
    post=read(BASE/'posthoc-battery.json');execution=read(BASE/'execution.json')
    floors=sorted((read(BASE/'floors'/f"{r['case']}.json") for r in targets['floors']['states']),key=lambda r:(r['rho'],r['case']))
    lines=['# 折れ目の両側と丸め下限','','## 1. c30>=0の片側問題（事前判定）','',
        '| 片側 | 点 | 片側の勾配∞ | 元のALの勾配∞ | s=μ+ρg | 他の切替 | step長 | 半ulp未満 |','|---|---:|---:|---:|---:|---:|---:|---:|']
    for mode,p in side['pieces'].items():
        for r in p['rows']:
            lines.append(f"| {mode} | x{r['index']} | {r['piece_gradient_inf']:.6e} | {r['true_gradient_inf']:.6e} | {r['s_float']:+.3e} | {r['other_switches']} | "
                f"{e(r['step_norm']) if 'step_norm' in r else '—'} | {r.get('below_half_ulp','—')} |")
        lines.append(f"| {mode} | 判定 | {p['verdict']} {','.join(p['reasons'])} | | | | | |")
    by=defaultdict(lambda:dict(states=0,exceeds=0,ratio=[]))
    for r in floors:
        b=by[r['rho']];b['states']+=1;b['exceeds']+=int(r['uniform_rms_exceeds']);b['ratio'].append(r['uniform_rms_over_threshold'])
    lines += ['','## 2. 実行済み24状態の丸め下限（一様丸めの目安/1e-8）','','| rho | 状態数 | 1e-8を超えた数 | 比の範囲 |','|---:|---:|---:|---|']
    for rho,b in sorted(by.items()):lines.append(f"| {rho:.0e} | {b['states']} | {b['exceeds']} | {min(b['ratio']):.3g}〜{max(b['ratio']):.3g} |")
    lines += ['','| 入力 | 段階 | rho | 変数 | 停止 | λ_max | 一様rms | 比 |','|---|---|---:|---:|---|---:|---:|---:|']
    for r in floors:
        lines.append(f"| {r['case']} | {r['stage']} | {r['rho']:.0e} | {r['variables']} | {r['stop']} | {e(r['eigen_max'])} | {e(r['floors']['uniform_rms'])} | {r['uniform_rms_over_threshold']:.3g} |")
    c=post['curvature_along_step']
    lines += ['','## 計画外の事後診断：区間17のCC/CV切替と旧Hの曲率','',
        f"- 区間17の充電量と切替点の差：x0で{post['points']['x0']['nearest_cc_cv'][0]['float']:.3e}、不活性側x5で{post['points']['inactive_x5']['nearest_cc_cv'][0]['float']:.3e}。",
        f"- κ−span/σ = {float(post['cc_slope_minus_cv_slope']):.3e}、切替をまたいだときのc17方向の勾配の跳びの予測 {post['predicted_c17_jump']:.3e}。",
        '','| 方向 | Decimal曲率（100桁, t=1e-24） | 旧Hの曲率 | 比 |','|---|---:|---:|---:|']
    for name in ['newton_direction','c17','e16']:
        lines.append(f"| {name} | {c[name]['decimal_curvature']:.6e} | {c[name]['old_hessian_curvature']:.6e} | {c[name]['ratio']:.6f} |")
    rows=side['pieces']['inactive']['rows'];observed=rows[-1]['piece_gradient_inf']/rows[-2]['piece_gradient_inf']
    predicted=abs(1-c['newton_direction']['ratio'])
    lines.append(f"\n観測した1回あたりの勾配∞の比 {observed:.6f}、Newton方向の曲率比rからの予測 |1−r| = {predicted:.6f}。")
    summary=dict(plan_commit='6f72c61',targets=targets,execution=execution,optimizer_launched=False,unit_tests=7,monte_carlo_changed=False,
        side={k:v for k,v in side.items() if k!='pieces'}|dict(pieces={m:{k:v for k,v in p.items() if k!='point'} for m,p in side['pieces'].items()}),
        side_reverification=verify,floors=floors,floors_by_rho={f'{k:.0e}':dict(states=v['states'],exceeds=v['exceeds'],min_ratio=min(v['ratio']),max_ratio=max(v['ratio'])) for k,v in sorted(by.items())},
        posthoc_not_planned=post,observed_per_step_ratio=observed,predicted_per_step_ratio=predicted)
    (BASE/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');(BASE/'comparison.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps(dict(floors_by_rho=summary['floors_by_rho'],observed=observed,predicted=summary['predicted_per_step_ratio'],seconds=execution['seconds'])))


if __name__=='__main__':main()
