"""Post-hoc (not in PLAN.md): compare returned points excluding the wall-clock field metrics.seconds."""
import json
from pathlib import Path

BASE=Path(__file__).resolve().parent;IGNORED='metrics.seconds'


def strip(d):
    d=json.loads(json.dumps(d));m=d.get('metrics')
    if isinstance(m,dict):m.pop('seconds',None)
    return d


def load(p):return strip(json.loads(p.read_text())) if p.exists() else None


def main():
    t=json.loads((BASE/'targets.json').read_text());out={}
    for case in t['cases']:
        c=load(BASE/'control'/'runs'/case/'selected.json');s=load(BASE/'stall'/'runs'/case/'selected.json')
        r=load(BASE.parents[0]/'2026-11-16-r3a-cohort'/'runs'/case/'selected.json')
        rc=json.loads((BASE/'control'/'runs'/case/'result.json').read_text());rs=json.loads((BASE/'stall'/'runs'/case/'result.json').read_text())
        out[case]=dict(control_equals_stall=c==s,control_equals_r3=c==r,same_route=rc['route']==rs['route'],
            verdict=('same_result_faster' if rs['seconds']<rc['seconds'] else 'same_result_not_faster') if c==s and rc['route']==rs['route'] else 'result_changed',
            control_seconds=rc['seconds'],stall_seconds=rs['seconds'])
    res=dict(planned=False,ignored_field=IGNORED,cases=out,verdicts={k:sum(v['verdict']==k for v in out.values()) for k in ['same_result_faster','same_result_not_faster','result_changed']})
    (BASE/'posthoc-content.json').write_text(json.dumps(res,indent=2)+'\n');print(json.dumps(res['verdicts']))
    for k,v in out.items():print(k,v['control_equals_stall'],v['control_equals_r3'],v['verdict'],round(v['control_seconds']-v['stall_seconds'],1))


if __name__=='__main__':main()
