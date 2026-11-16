import json
from pathlib import Path

BASE=Path(__file__).resolve().parent


def main():
    rows=[json.loads(p.read_text()) for p in sorted((BASE/'states').glob('*/result.json'))]
    assert len(rows)==4
    errors=[v['normalized_error'] for r in rows for v in r['rows']]
    for r in rows:
        for b in r['budgets']:b['estimated_ratio_dense_over_directional']=b['dense_seconds']/b['directional_seconds']
    summary=dict(states=4,directions=16,states_passing=sum(r['comparison_passed'] for r in rows),
        max_normalized_product_error=max(errors),max_symmetry_error=max(r['symmetry_error'] for r in rows),
        max_additivity_error=max(r['additivity_error'] for r in rows),
        curvature_sign_mismatches=[dict(case=r['case'],stage=r['stage'],**v) for r in rows for v in r['rows'] if not v['curvature_sign_equal']],
        projected_q10_ratios=[next(b['estimated_ratio_dense_over_directional'] for b in r['budgets'] if b['queries']==10) for r in rows],
        rho_values=sorted(set(r['rho'] for r in rows)),optimizer_launched=False,whole_solver_speedup_measured=False,reference_is_finite_difference=True,
        execution_seconds=json.loads((BASE/'execution.json').read_text())['seconds'],rows=rows)
    (BASE/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    lines=['# 固定状態の方向曲率評価','',
        '| 入力 | 段階 | 変数 | 最大正規化誤差 | 行列構成 ms | setup ms | 1方向 ms | 10方向の費用比 |',
        '|---|---:|---:|---:|---:|---:|---:|---:|']
    for r in rows:
        m=r['medians'];q=next(b for b in r['budgets'] if b['queries']==10)
        lines.append(f"| {r['case']} | {r['stage']} | {r['variables']} | {max(v['normalized_error'] for v in r['rows']):.3e} | {m['dense_construction']*1e3:.3f} | {m['setup']*1e3:.3f} | {m['query']*1e3:.3f} | {q['estimated_ratio_dense_over_directional']:.2f} |")
    lines+=['','費用比は行列構成+10行列積とsetup+10方向評価の換算。反復法/最適化は実行していない。','']
    (BASE/'comparison.md').write_text('\n'.join(lines))
    print(json.dumps({k:v for k,v in summary.items() if k!='rows'}))


if __name__=='__main__':main()
