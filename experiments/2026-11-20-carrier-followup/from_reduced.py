"""Post-comparison follow-up: both models from the same accepted R solution."""
import hashlib
import json
from model import HERE, ROOT, load, make_branch, solve
from run import save


def main():
    result=[]
    for rel,digest in json.loads((HERE/'reduced-start-index.json').read_text()).items():
        assert hashlib.sha256((ROOT/rel).read_bytes()).hexdigest()==digest
        path=ROOT/rel;case=path.parent.name;initial=json.loads(path.read_text());reference=load(case)
        for method in ('R','q'):
            d,row,raw=solve(make_branch(initial,method),method,reference)
            dest=HERE/'reduced-start-runs'/case/f'{method}.json';save(dest,d);save(dest.with_name(dest.stem+'-solver.json'),raw)
            row.update(case=case,phase='R-feasible-start',warmup=False,rep=0,
                       solution_path=str(dest.relative_to(ROOT)),point_sha256=hashlib.sha256(dest.read_bytes()).hexdigest())
            result.append(row)
            print(case,method,json.dumps({k:row[k] for k in ('accepted','objective_hours','solver_status','iterations','seconds','kkt')}),flush=True)
    save(HERE/'reduced-start-results.json',result)


if __name__=='__main__':main()
