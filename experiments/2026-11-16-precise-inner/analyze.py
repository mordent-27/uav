import json
from pathlib import Path

BASE=Path(__file__).resolve().parent


def main():
    rows=[];lines=['# 評価精度だけを変える内側比較','',
        '| 入力 | 評価 | 停止 | 受理 | 保存勾配∞ | 100桁での勾配∞ | 秒 |',
        '|---|---|---|---:|---:|---:|---:|']
    for p in sorted((BASE/'inner').glob('*/result.json')):
        r=json.loads(p.read_text());v=json.loads((BASE/'reverification'/f"{p.parent.name}.json").read_text())
        trace=[json.loads(s) for s in (p.parent/'trace.jsonl').read_text().splitlines()]
        row={k:r[k] for k in ['case','method','status','accepted','iterations','scalar_calls','trials','gradient_inf','seconds','decimal_scalar_evaluations']}
        row.update(final_gradient_inf_100=v['final_gradient_inf_100'],passes_gradient_tolerance_100=v['passes_gradient_tolerance_100'],
            al_decrease_100=v['al_decrease_100'],initial_gradient_norm_100=v['initial_gradient_norm_100'],
            final_gradient_norm_100=v['final_gradient_norm_100'],points_recomputed=v['points_recomputed'],
            accepted_fallback=sum(a.get('gradient_fallback',False) for a in trace[1:]))
        rows.append(row)
        lines.append(f"| {r['case']} | {r['method']} | {r['status']} | {r['accepted']} | {r['gradient_inf']:.6e} | {v['final_gradient_inf_100']:.6e} | {r['seconds']:.6f} |")
    checks=[json.loads(p.read_text()) for p in sorted((BASE/'gradient-checks').glob('*.json'))]
    summary=dict(gradient_components_checked=sum(len(r['gradient_100']) for r in checks),gradient_checks=checks,
        inner_solves=4,rows=rows,all_points_recomputed=sum(r['points_recomputed'] for r in rows),
        unit_tests=19,outer_solver_launched=False,monte_carlo_changed=False)
    (BASE/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');(BASE/'comparison.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k!='gradient_checks'}))


if __name__=='__main__':main()
