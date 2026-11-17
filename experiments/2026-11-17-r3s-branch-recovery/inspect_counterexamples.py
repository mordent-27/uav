import gzip
import hashlib
import json
from pathlib import Path
import sys
from run import BASE,ROOT,COHORT,branch,measure,read,write,recoveries


def main():
    summary=read(BASE/'summary.json');selected=[r for r in summary['cohort'] if r['entry_impossible']]
    paths=[BASE/'summary.json']+[ROOT/'experiments'/r['origin']/'cases/G'/r['case']/'stages/stage13/outer.jsonl.gz' for r in selected]
    sources={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    if '--freeze' in sys.argv:
        assert not (BASE/'counterexample-source-index.json').exists();write(BASE/'counterexample-source-index.json',sources);print(len(selected));return
    assert sources==read(BASE/'counterexample-source-index.json') and not (BASE/'counterexamples.json').exists()
    results=[]
    for r in selected:
        base=ROOT/'experiments'/r['origin'];folder=base/'cases/G'/r['case'];template=read(base/'inputs'/r['case']/'input.json')
        entry=read(folder/'stages/stage13/initial.json');end=read(folder/'result.json');initial_branch=branch(template,entry);end_branch=branch(template,end)
        entry_row=dict(measure(r['case'],'entry',initial_branch),outer=0,rho=entry['rho'])
        points=[entry_row]
        with gzip.open(folder/'stages/stage13/outer.jsonl.gz','rt') as stream:
            for line in stream:
                state=json.loads(line);data=branch(template,state)
                points.append(dict(measure(r['case'],'outer'+str(state['outer']),data),outer=state['outer'],rho=state['rho'],common_pass=state['common_pass']))
        restored=read(base/'runs'/r['case']/'selected.json')
        changed_modes=[dict(segment=i,before=a,after=b) for i,(a,b) in enumerate(zip(initial_branch['modes'],end_branch['modes'])) if a!=b]
        changed_tasks=[dict(task=i,before=a,after=b) for i,(a,b) in enumerate(zip(initial_branch['task_stamp'],end_branch['task_stamp'])) if a!=b]
        results.append(dict(case=r['case'],points=points,recovery_indices=recoveries([p['infeasible_branch_proven'] for p in points]),
            changed_modes=changed_modes,changed_tasks=changed_tasks,returned_h=sum(restored['solution']['s']),
            entry_charges=sum(m>=0 for m in initial_branch['modes']),final_charges=sum(m>=0 for m in end_branch['modes'])))
    write(BASE/'counterexamples.json',results)
    print(json.dumps([dict(case=r['case'],recoveries=[(r['points'][i]['outer'],r['points'][i]['rho']) for i in r['recovery_indices']],
        changed_modes=r['changed_modes'],changed_tasks=r['changed_tasks'],returned_h=r['returned_h']) for r in results]))


if __name__=='__main__':main()
