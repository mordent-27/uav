import json
from pathlib import Path
import numpy as np

BASE=Path(__file__).resolve().parent


def main():
    rows=[]
    paths=list((BASE/'inner').glob('*/result.json'))
    for target in json.loads((BASE/'targets.json').read_text())['contexts']:
        paths += [BASE.parents[1]/name for name in target['references']]
    for p in sorted(paths):
        r=json.loads(p.read_text());trace=[json.loads(s) for s in (p.parent/'trace.jsonl').read_text().splitlines()]
        accepted=trace[1:];steps=[float(np.linalg.norm(np.array(b['y'])-a['y'])) for a,b in zip(trace,accepted)]
        row={k:r.get(k) for k in ['case','method','status','initial_value','value','al_decrease','initial_gradient_inf',
            'gradient_inf','seconds','accepted','scalar_calls','hessian_gradient_calls','jacobian_calls',
            'hvp_queries','dense_matvec_queries','cg_iterations','cg_reasons']}
        row.update(gradient_fallback_accepted=sum(x['gradient_fallback'] for x in accepted),
            accepted_non_decreasing_al=sum(b['value']>=a['value'] for a,b in zip(trace,accepted)),
            accepted_al_increases=sum(b['value']>a['value'] for a,b in zip(trace,accepted)),
            final_delta=accepted[-1]['delta'] if accepted else None,last_step_norm=steps[-1] if steps else 0.,
            final_common_kkt=r['final_metrics']['common_kkt'])
        rows.append(row)
    summary=dict(solves=6,new_solves=2,saved_references=4,rows=rows,frozen_al_only=True,outer_solver_launched=False,
        per_solve_seconds=30,monte_carlo_changed=False,
        execution_seconds=json.loads((BASE/'execution.json').read_text())['seconds'])
    (BASE/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    lines=['# 同じdense行列を用いたCGの対照','',
        '| 入力 | 方法 | 停止 | AL減少 | 最終勾配∞ | 受理反復 | 秒 |',
        '|---|---|---|---:|---:|---:|---:|']
    for r in rows:lines.append(f"| {r['case']} | {r['method']} | {r['status']} | {r['al_decrease']:.6e} | {r['gradient_inf']:.6e} | {r['accepted']} | {r['seconds']:.6f} |")
    lines+=['','dense/cgは前回の保存結果、dense-cgだけ新規。外側ALや900入力の追加求解ではない。','候補ではTR部分問題の近似解法も異なる。時間は各1回の観測で、反復回数と到達精度を併記。','']
    (BASE/'comparison.md').write_text('\n'.join(lines))
    print(json.dumps(summary))


if __name__=='__main__':main()
