"""Paired comparison of the fixed-penalty cohort with the baseline cohort (same 900 instances).

Standard library only. Writes mc-pair.csv and prints a markdown table.
"""
import csv
import json
from pathlib import Path
from statistics import median

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
read = lambda p: list(csv.DictReader(open(p)))
new = read(HERE / 'mc-rho1e4/results.csv')
old = read(HERE.parent / '2026-11-14-reproduction/mc-original/results.csv')
paper = read(ROOT / 'data/paper_fig3.csv')
assert len(new) == len(old) == 900
key = lambda r: (int(r['tau']), int(r['run']))
old_by = {key(r): r for r in old}
assert all(old_by[key(r)]['seed'] == r['seed'] for r in new)
ok = lambda r: r['original_violation_le_1e_3'] == 'True'
out = []
for tau in range(1, 10):
    a = [r for r in new if int(r['tau']) == tau]
    b = [old_by[key(r)] for r in a]
    ref = {q: [float(v['value']) for v in paper if v['method'] == 'NLP' and int(v['tau']) == tau and v['quantity'] == q]
           for q in ('objective_h', 'violation')}
    done = [r for r in a if r['completed'] == 'True']
    both = [(x, y) for x, y in zip(a, b) if ok(x) and ok(y)]
    out.append(dict(
        tau=tau, completed=len(done), timed_out=sum(r['timed_out'] == 'True' for r in a),
        kkt=sum(r['kkt_converged'] == 'True' for r in a),
        viol_ok=sum(map(ok, a)), viol_ok_baseline=sum(map(ok, b)),
        gained=sum(ok(x) and not ok(y) for x, y in zip(a, b)), lost=sum(ok(y) and not ok(x) for x, y in zip(a, b)),
        viol_le_1e_4=sum(float(r['original_violation']) <= 1e-4 for r in done),
        audit=sum(r['physical_audit_pass'] == 'True' for r in a),
        audit_baseline=sum(r['physical_audit_pass'] == 'True' for r in b),
        median_objective=median(float(r['objective']) for r in done),
        median_objective_ok=median(float(r['objective']) for r in a if ok(r)),
        median_objective_baseline=median(float(r['objective']) for r in b if r['completed'] == 'True'),
        median_objective_paper=median(ref['objective_h']),
        paired_ratio_both_ok=median(float(x['objective']) / float(y['objective']) for x, y in both) if both else None,
        pairs_both_ok=len(both),
        median_stat=median(float(r['stat']) for r in done), median_feas=median(float(r['feas']) for r in done),
        median_violation=median(float(r['original_violation']) for r in done),
        median_seconds=median(float(r['solver_seconds']) for r in done),
        paper_viol_ok=sum(v <= 1e-3 for v in ref['violation'])))
with open(HERE / 'mc-pair.csv', 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(out[0]), lineterminator='\n')
    w.writeheader()
    w.writerows(out)
print('| タスク数 | KKT | 違反<=1e-3: rho固定 | 基準 | 新たに合格 | 不合格に転落 | 図3読取 | 目的の中央値[h]: rho固定（全出力） | 基準 | 図3読取 | 比（rho固定/図3） | 停留性の中央値 | 実行可能性の中央値 | 秒の中央値 |')
print('|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|')
for g in out:
    print(f'| {g["tau"]} | {g["kkt"]}/100 | {g["viol_ok"]}/100 | {g["viol_ok_baseline"]}/100 | {g["gained"]} | {g["lost"]} | {g["paper_viol_ok"]}/100 '
          f'| {g["median_objective"]:.3f} | {g["median_objective_baseline"]:.3f} | {g["median_objective_paper"]:.3f} '
          f'| {g["median_objective"]/g["median_objective_paper"]:.2f} | {g["median_stat"]:.1e} | {g["median_feas"]:.1e} | {g["median_seconds"]:.1f} |')
t = lambda k: sum(g[k] for g in out)
print(f'\n合計: KKT {t("kkt")}/900、違反<=1e-3 {t("viol_ok")}/900（基準 {t("viol_ok_baseline")}/900、新たに合格 {t("gained")}、転落 {t("lost")}）、'
      f'違反<=1e-4 {t("viol_le_1e_4")}/900、純モード電池の監査 {t("audit")}/900（基準 {t("audit_baseline")}/900）、時間切れ {t("timed_out")}')
print('両方が違反<=1e-3の対での目的関数の比（rho固定/基準）の中央値:',
      ', '.join(f'tau{g["tau"]}: {g["paired_ratio_both_ok"]:.3f} (n={g["pairs_both_ok"]})' for g in out if g['pairs_both_ok']))
