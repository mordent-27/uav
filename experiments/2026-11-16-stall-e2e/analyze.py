"""Per-case comparison of the control and stall-rule entries (PLAN.md verdicts)."""
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path

BASE=Path(__file__).resolve().parent;ROOT=BASE.parents[1]
spec=importlib.util.spec_from_file_location('outer_stall_rule',BASE.parent/'2026-11-16-outer-stall/stall.py');stall=importlib.util.module_from_spec(spec);spec.loader.exec_module(stall)


def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None


def arm_summary(arm,case):
    out=BASE/arm;run=read(out/'runs'/case/'result.json');st13=out/'cases'/'G'/case/'stages'/'stage13'
    g13=read(st13/'result.json') if (st13/'result.json').exists() else None
    stall_info=read(st13/'stall.json') if (st13/'stall.json').exists() else None
    rows=[json.loads(s) for s in gzip.open(st13/'outer.jsonl.gz','rt').read().splitlines()] if (st13/'outer.jsonl.gz').exists() else []
    gsteps=read(out/'cases'/'G'/case/'steps.json') if (out/'cases'/'G'/case/'steps.json').exists() else {}
    seconds={s['script']+'-'+s['phase']:s['seconds'] for s in run.get('steps',[])}
    return dict(error=run['error'],route=run.get('route'),outcome=run.get('outcome'),seconds=run['seconds'],step_seconds=seconds,
        g_case_seconds=seconds.get('g_case-G'),selected_sha256=sha(out/'runs'/case/'selected.json'),
        g_stage13=None if g13 is None else dict(stop=g13['stop'],completed_outer=g13['completed_outer'],stage_pass=g13['stage_pass'],seconds=g13['seconds']),
        stall=stall_info,rule_on_log=stall.first_trigger(rows,20,.1,1e-6,1e8) if rows else None,g_steps=gsteps)


def verdict(c,s,passing):
    if passing and s['stall'] is not None:return 'false_stop'
    same=c['selected_sha256']==s['selected_sha256'] and c['route']==s['route']
    if not same:return 'result_changed'
    return 'same_result_faster' if s['seconds']<c['seconds'] else 'same_result_not_faster'


def main():
    t=read(BASE/'targets.json');rows=[]
    lines=['# 打ち切り規則の端から端までの比較','','| 入力 | G | 入口 | 経路 | stage13停止 | 外側 | g_case秒 | 総秒 | 返却点sha一致 | R3と一致 | 判定 |','|---|---|---|---|---|---:|---:|---:|---|---|---|']
    for case in t['cases']:
        c,s=arm_summary('control',case),arm_summary('stall',case);passing=case in t['g_passing']
        v=verdict(c,s,passing);r3=t['r3_records'][case]['selected_sha256']
        rows.append(dict(case=case,g_passing_in_r3=passing,verdict=v,control=c,stall=s,
            control_matches_r3=c['selected_sha256']==r3,stall_matches_r3=s['selected_sha256']==r3,saved_seconds=c['seconds']-s['seconds']))
        for arm,x in [('対照',c),('規則',s)]:
            g=x['g_stage13'] or {}
            lines.append(f"| {case} | {'合格' if passing else '不合格'} | {arm} | {x['route']} | {g.get('stop')} | {g.get('completed_outer')} | {x['g_case_seconds'] or float('nan'):.1f} | {x['seconds']:.1f} | "
                f"{c['selected_sha256']==s['selected_sha256']} | {x['selected_sha256']==r3} | {v if arm=='規則' else ''} |")
    summary=dict(plan_commit='e8d5781',targets=t,execution=read(BASE/'execution.json'),rows=rows,
        verdicts={k:sum(r['verdict']==k for r in rows) for k in ['same_result_faster','same_result_not_faster','result_changed','false_stop']},
        total_seconds=dict(control=sum(r['control']['seconds'] for r in rows),stall=sum(r['stall']['seconds'] for r in rows)))
    (BASE/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');(BASE/'comparison.md').write_text('\n'.join(lines)+'\n');print('\n'.join(lines));print(summary['verdicts'],summary['total_seconds'])


if __name__=='__main__':main()
