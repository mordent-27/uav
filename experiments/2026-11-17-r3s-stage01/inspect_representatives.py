"""Freeze and read first/last inner traces of the three prespecified representatives."""
import csv
import gzip
import hashlib
import json
from pathlib import Path
import sys

BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[1]


def read(p):return json.loads(p.read_text())
def write(p,v):p.write_text(json.dumps(v,indent=2)+'\n')


def main():
    if '--freeze' in sys.argv:
        assert not (BASE/'representative-source-index.json').exists()
        cases={r['case']:r for r in read(ROOT/'experiments/2026-11-16-r3s-cohort/summary.json')['cases']}
        index={};selection=[]
        for representative in read(BASE/'representatives.json'):
            case=representative['case'];folder=ROOT/cases[case]['G']['folder']/'stages/stage01'
            logs=sorted(folder.glob('inner*.jsonl.gz'))
            for source in dict.fromkeys([logs[0],logs[-1]]):
                data=source.read_bytes();saved=BASE/'representative-logs'/case/source.name
                saved.parent.mkdir(parents=True,exist_ok=True);assert not saved.exists();saved.write_bytes(data)
                name=str(saved.relative_to(ROOT));index[name]=hashlib.sha256(data).hexdigest()
                selection.append(dict(case=case,source=str(source.relative_to(ROOT)),saved=name))
        write(BASE/'representative-source-index.json',index);write(BASE/'representative-selection.json',selection)
        print(json.dumps(dict(saved_traces=len(selection),bytes=sum((ROOT/k).stat().st_size for k in index))))
        return
    assert not (BASE/'representative-traces.csv').exists()
    index=read(BASE/'representative-source-index.json');rows=[]
    for chosen in read(BASE/'representative-selection.json'):
        saved=ROOT/chosen['saved'];assert hashlib.sha256(saved.read_bytes()).hexdigest()==index[chosen['saved']]
        with gzip.open(saved,'rt') as stream:trace=[json.loads(line) for line in stream]
        context=trace[0];initial=trace[1];accepted=trace[2:]
        assert context['kind']=='context' and initial['kind']=='input'
        assert all(t['kind']=='accepted' for t in accepted)
        source=ROOT/chosen['source'];folder=source.parent;outer=int(source.name[5:9])
        with gzip.open(folder/'outer.jsonl.gz','rt') as stream:completed=[json.loads(line) for line in stream]
        interrupted=outer>len(completed)
        if interrupted:
            last=read(folder/'interrupted-inner.json');expected=last['last_accepted_y'];info=last['inner']
        else:
            last=completed[outer-1];expected=last['y'];info=last['inner']
        endpoint=accepted[-1] if accepted else initial
        assert endpoint['y']==expected and len(accepted)==info['accepted']
        assert endpoint['gradient_inf']==info['gradient_inf']
        previous=[initial]+accepted[:-1]
        rows.append(dict(case=chosen['case'],outer=outer,interrupted=interrupted,source_copy=chosen['saved'],
            status=info['status'],accepted=len(accepted),initial_AL=initial['value'],last_AL=endpoint['value'],
            initial_gradient_inf=initial['gradient_inf'],last_gradient_inf=endpoint['gradient_inf'],
            gradient_fallback_steps=sum(p['gradient_fallback'] for p in accepted),
            AL_increase_steps=sum(b['value']>a['value'] for a,b in zip(previous,accepted)),
            negative_eigen_steps=sum(p['eigen_min']<0 for p in accepted),
            seconds=info['seconds'],hessian_builds=info['jacobian_calls']))
    with (BASE/'representative-traces.csv').open('w') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]),lineterminator='\n');writer.writeheader();writer.writerows(rows)
    print(json.dumps(rows))


if __name__=='__main__':main()
