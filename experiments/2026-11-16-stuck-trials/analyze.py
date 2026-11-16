import json
from pathlib import Path

BASE=Path(__file__).resolve().parent


def read(p):return json.loads(p.read_text())


def main():
    targets=read(BASE/'targets.json');lines=['# 止まった内側TRの試行の再生','']
    rows=[]
    for t in targets['targets']:
        a=read(BASE/'replays'/f"{t['name']}.json");b=read(BASE/'replays-decimal'/f"{t['name']}.json")
        ratios=[r['precise_ratio'] for r in b['rows']]
        rows.append(dict(name=t['name'],value=b['value'],value_ulp=b['value_ulp'],fallback_threshold=b['fallback_threshold'],gradient_inf=b['gradient_inf'],
            start_radius=b['start_radius'],trials=b['trials'],fallback_trials=b['fallback_trials'],prediction_max=max(r['prediction'] for r in b['rows']),
            prediction_min=min(r['prediction'] for r in b['rows']),decimal_ratio_min=min(ratios),decimal_ratio_max=max(ratios),
            first_run=dict(decimal_available=a['decimal_available'],decimal_value_gap=a['decimal_value_gap'],verdict=a['verdict'],
                stable_ratio_min=min(r['precise_ratio'] for r in a['rows']),stable_ratio_max=max(r['precise_ratio'] for r in a['rows'])),
            addendum=dict(decimal_available=b['decimal_available'],decimal_value_gap=b['decimal_value_gap'],verdict=b['verdict'],precise_accepting_trials=b['precise_accepting_trials']),
            gradient_norm_increase=[r['trial_gradient_norm']-r['gradient_norm'] for r in b['rows']]))
    lines += ['| 点 | AL値 | ulp | fallback閾値 | 開始半径 | 試行 | うちfallback | 予測減少 | Decimal減少/予測 | 第1回（安定な差）の比 | 判定（追加計画） |','|---|---:|---:|---:|---:|---:|---:|---|---|---|---|']
    for r in rows:
        lines.append(f"| {r['name']} | {r['value']:.6e} | {r['value_ulp']:.2e} | {r['fallback_threshold']:.2e} | {r['start_radius']:.2e} | {r['trials']} | {r['fallback_trials']} | "
            f"{r['prediction_min']:.2e}〜{r['prediction_max']:.2e} | {r['decimal_ratio_min']:.4f}〜{r['decimal_ratio_max']:.4f} | "
            f"{r['first_run']['stable_ratio_min']:+.1e}〜{r['first_run']['stable_ratio_max']:+.1e} | {r['addendum']['verdict']} |")
    summary=dict(plan_commit='990ccde',addendum_commit='1f3eeca',targets=targets,execution=read(BASE/'execution.json'),execution_decimal=read(BASE/'execution-decimal.json'),
        rows=rows,reverification=read(BASE/'reverification'/'replays.json'),optimizer_launched=False,unit_tests=4)
    (BASE/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');(BASE/'comparison.md').write_text('\n'.join(lines)+'\n');print('\n'.join(lines))


if __name__=='__main__':main()
