"""Replay the stall rule (primary and grid) on the fixed outer logs. Reads saved files only."""
import gzip
import hashlib
import json
from pathlib import Path
import sys
import stall

BASE=Path(__file__).resolve().parent;ROOT=BASE.parents[1]


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def compute():
    t=json.loads((BASE/'targets.json').read_text());out=dict(primary=[],grid={})
    for l in t['logs']:
        assert sha(ROOT/l['outer'])==l['outer_sha256'] and sha(ROOT/l['result'])==l['result_sha256'],l['name']
    data=[]
    for l in t['logs']:
        rows=[json.loads(s) for s in gzip.open(ROOT/l['outer'],'rt').read().splitlines()];res=json.loads((ROOT/l['result']).read_text())
        data.append((l,rows,bool(res['stage_pass']),res['stop'],res['seconds']))
    P=t['primary']
    for l,rows,passed,stop,seconds in data:
        c=stall.classify(rows,passed,P['K'],P['delta'],t['tolerance'],t['rho_cap'])
        cap=next((r['outer'] for r in rows if r['rho']>=t['rho_cap']),None)
        out['primary'].append(dict(name=l['name'],source=l['source'],case=l['case'],stop=stop,stage_seconds=seconds,first_cap_row=cap,**c))
    for K in t['grid']['K']:
        for d in t['grid']['delta']:
            res=[stall.classify(rows,passed,K,d,t['tolerance'],t['rho_cap']) for l,rows,passed,stop,seconds in data]
            out['grid'][f'K{K}-d{d}']=dict(verdict=stall.verdict(res),false_stops=sum(r['kind']=='false_stop' for r in res),
                stopped_failures=sum(r['kind']=='stopped_failure' for r in res),saved_seconds=sum(r.get('saved_seconds',0.) for r in res))
    out['primary_verdict']=stall.verdict(out['primary'])
    return out


def main():
    out=compute();target=BASE/('replay.json' if '--check' not in sys.argv else 'replay-check.json');assert not target.exists()
    target.write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(dict(primary=out['primary_verdict'],grid={k:v['verdict'] for k,v in out['grid'].items()})))


if __name__=='__main__':main()
