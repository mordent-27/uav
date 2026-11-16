"""Separate-process recheck: stall triggers recomputed from the stall-arm stage-13 logs, selected hashes re-read, G verify steps ok."""
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path

BASE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('outer_stall_rule',BASE.parent/'2026-11-16-outer-stall/stall.py');stall=importlib.util.module_from_spec(spec);spec.loader.exec_module(stall)


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None


def main():
    t=json.loads((BASE/'targets.json').read_text());summary=json.loads((BASE/'summary.json').read_text());out={}
    for r in summary['rows']:
        case=r['case'];row={}
        for arm in ['control','stall']:
            st13=BASE/arm/'cases'/'G'/case/'stages'/'stage13'
            assert sha(BASE/arm/'runs'/case/'selected.json')==r[arm]['selected_sha256']
            steps=json.loads((BASE/arm/'cases'/'G'/case/'steps.json').read_text())
            assert all(v=='ok' for v in steps.values()),(arm,case,steps)
            if (st13/'outer.jsonl.gz').exists():
                rows=[json.loads(s) for s in gzip.open(st13/'outer.jsonl.gz','rt').read().splitlines()]
                k=stall.first_trigger(rows,20,.1,1e-6,1e8);res=json.loads((st13/'result.json').read_text())
                if arm=='stall':
                    if res['stop']=='stalled':
                        s=json.loads((st13/'stall.json').read_text());assert k==s['trigger']==len(rows)
                    else:assert k is None,(case,k)
                row[arm]=dict(rows=len(rows),stop=res['stop'],rule_trigger=k)
        out[case]=row
    (BASE/'reverification.json').write_text(json.dumps(dict(cases=out,selected_hashes_reread=True,g_steps_ok=True,stall_triggers_reproduced=True),indent=2)+'\n')
    print(json.dumps(out))


if __name__=='__main__':main()
