"""Compare the prespecified pilot/expansion with saved condition G; no solves."""
import gzip
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent/'2026-11-15-r2b-coarse/cases/G'
ALL = ['fig1']+[f'tau{t}-seed{s}' for t in (1, 3, 5, 7) for s in (0, 1, 2)]


def outcome(folder):
    if not (folder/'result.json').exists():
        return dict(run=False, restored=False)
    # A root result is also written between stages; it is not yet a completed run.
    if (folder.parent == HERE/'cases') and not (folder/'steps.json').exists():
        return dict(run=False, restored=False, in_progress=True)
    result = json.loads((folder/'result.json').read_text())
    restored = json.loads((folder/'restored/result.json').read_text()) if (folder/'restored/result.json').exists() else None
    stage_path = sorted((folder/'stages').glob('stage*/result.json'))
    stages = [json.loads(p.read_text()) for p in stage_path]
    return dict(run=True, stage=result['stage'], common=result['final_common_pass'], physical=result['final_both_scales_pass'],
        raw_objective=result['objective'], seconds=result['elapsed'], outer=result['total_outer'],
        restored=bool(restored and restored['accepted']), objective=restored.get('objective') if restored else None,
        stop=result['stop'], charging=[r['selection']['charging_segments'] for r in stages],
        final_common_kkt=result['common_kkt'])


def main():
    rows = []
    for name in ALL:
        init = json.loads((HERE/'initializations'/name/'result.json').read_text())
        before, after = outcome(BASE/name), outcome(HERE/'cases'/name)
        rows.append(dict(name=name, initialization=init, baseline=before, changed=after))
    lines = ['| 例 | 初期化 時間 h：元→変更 | G受理 | 変更後受理 | 復元後 h：G→変更 | 判定 |',
             '|---|---|---|---|---|---|']
    for row in rows:
        a, b, init = row['baseline'], row['changed'], row['initialization']
        before = f"{a['objective']:.9f}" if a['restored'] else '—'
        after = f"{b['objective']:.9f}" if b['restored'] else '—'
        status = b['stop'] if b['run'] else '未求解'
        initial = f"{init['initial_objective']:.6f}→{init.get('objective', float('nan')):.6f}"
        lines.append(f"| {row['name']} | {initial} | {a['restored']} | {b['restored'] if b['run'] else '—'} | {before}→{after} | {status} |")
    (HERE/'comparison.md').write_text('\n'.join(lines)+'\n')
    summary = dict(initializations_accepted=sum(r['initialization']['accepted'] for r in rows),
        solved_cases=sum(r['changed']['run'] for r in rows),
        restored_cases=sum(r['changed']['restored'] for r in rows),
        newly_accepted=[r['name'] for r in rows if r['changed']['restored'] and not r['baseline']['restored']],
        lost_acceptance=[r['name'] for r in rows if r['changed']['run'] and r['baseline']['restored'] and not r['changed']['restored']],
        rows=rows)
    if (HERE/'decision.json').exists():
        summary['decision'] = json.loads((HERE/'decision.json').read_text())
    (HERE/'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    print(json.dumps({k: summary[k] for k in ['initializations_accepted', 'solved_cases', 'restored_cases', 'newly_accepted', 'lost_acceptance']}))


if __name__ == '__main__':
    main()
