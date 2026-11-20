"""Metadata-normalized evidence copies; frozen raw run outputs stay unchanged."""
import copy
import hashlib
import json
from pathlib import Path
from verify_point import check

BASE=Path(__file__).resolve().parent;ROOT=BASE.parents[1]


def main():
    rows=json.loads((BASE/'comparison.json').read_text())+json.loads((BASE/'reduced-start-results.json').read_text())
    index=[]
    for case in ('tau9-seed9000076','tau9-seed9000001'):
        inputs=[('long-charge',BASE/'construction'/f'{case}.json',None)]
        for method,phase,label in [('R','comparison','R'),('q','R-feasible-start','q-from-R')]:
            row=next(r for r in rows if r['case']==case and r['method']==method and r['phase']==phase and r['rep']==(1 if phase=='comparison' else 0))
            inputs.append((label,ROOT/row['solution_path'],row))
        for label,path,row in inputs:
            original=json.loads(path.read_text());d=copy.deepcopy(original)
            d['metrics'].update(objective=sum(d['solution']['s']),converged=False,seconds=0. if row is None else row['seconds'])
            d['diagnostic'].update(evidence_copy=True,source_path=str(path.relative_to(ROOT)),
                source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                solver_success=None if row is None else row['solver_success'],
                paper_algorithm=False,global_optimality=False)
            assert check(d)['accepted'] and d['solution']==original['solution']
            dest=BASE/'witnesses'/case/f'{label}.json';dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_text(json.dumps(d,indent=1,allow_nan=False)+'\n')
            index.append(dict(case=case,label=label,path=str(dest.relative_to(ROOT)),
                sha256=hashlib.sha256(dest.read_bytes()).hexdigest(),objective_hours=d['metrics']['objective']))
    (BASE/'witness-index.json').write_text(json.dumps(index,indent=2)+'\n')
    print('6 evidence copies validated; no solves; raw points unchanged')


if __name__=='__main__':main()
