"""Markdown tables for the 13 fixed cases of PLAN.md (conditions N, L, L0). Standard library only."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASES = ['fig1'] + [f'tau{t}-seed{s}' for t in (1, 3, 5, 7) for s in (0, 1, 2)]
rows = {c: {n: json.loads((HERE / 'cases' / c / f'{n}.json').read_text()) for n in CASES} for c in ('N', 'L', 'L0')}

print('| 判定 | N: ニュートン法 | L: 自作L-BFGS | L0: 自作L-BFGS・元の速度表現 |')
print('|---|---:|---:|---:|')
count = lambda c, f: f'{sum(bool(f(d)) for d in rows[c].values())}/13'
for label, f in [
    ('最終段階まで到達（600秒以内）', lambda d: d['reached_final_stage'] and not d['timed_out']),
    ('KKT（3残差とも1e-6以下）', lambda d: d['kkt_converged']),
    ('停留性 1e-6以下', lambda d: d['reached_final_stage'] and d['stat'] <= 1e-6),
    ('実行可能性 1e-6以下', lambda d: d['reached_final_stage'] and d['feas'] <= 1e-6),
    ('実行可能性 1e-5以下', lambda d: d['reached_final_stage'] and d['feas'] <= 1e-5),
    ('元の制約の違反 1e-3以下', lambda d: d['metrics']['viol'] <= 1e-3),
    ('元の制約の違反 1e-4以下', lambda d: d['metrics']['viol'] <= 1e-4),
]:
    print(f'| {label} | ' + ' | '.join(count(c, f) for c in ('N', 'L', 'L0')) + ' |')
print()
print('| 例 | N 停留性 | N 実行可能性 | N 違反 | N 目的[h] | N 秒 | L 停留性 | L 実行可能性 | L 違反 | L 目的[h] | L0 停留性 | L0 違反 | L0 目的[h] |')
print('|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|')
for n in CASES:
    a, b, c = (rows[k][n] for k in ('N', 'L', 'L0'))
    mark = '' if a['reached_final_stage'] and not a['timed_out'] else '*'
    print(f'| {n} | {a["stat"]:.1e}{mark} | {a["feas"]:.1e}{mark} | {a["metrics"]["viol"]:.1e} | {a["metrics"]["objective"]:.4f} | {a["seconds"]:.0f} '
          f'| {b["stat"]:.1e} | {b["feas"]:.1e} | {b["metrics"]["viol"]:.1e} | {b["metrics"]["objective"]:.4f} '
          f'| {c["stat"]:.1e} | {c["metrics"]["viol"]:.1e} | {c["metrics"]["objective"]:.4f} |')
print('\n*は600秒の上限で打ち切った例（その時点の段階の値）。')
