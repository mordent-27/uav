"""Post-hoc (not in PLAN.md): PHR activity along the saved Newton points and low directions. Evaluation only."""
from decimal import Decimal as D,localcontext
import json
import os
from pathlib import Path
import subprocess
import sys
from time import monotonic
import numpy as np

BASE=Path(__file__).resolve().parent


def kinds(ns):
    names=['speed','e_min','e_max','s_min','s_max','charge_nonnegative']
    return [f'{n}[{k}]' for n in names for k in range(ns)]


def worker():
    import worker as w
    import lowcurv as cv
    case=os.environ['UAV_R2_CASE'];targets,target,metadata,frozen,y,H=w.load(case);frozen.close()
    result=json.loads((BASE/'states'/case/'result.json').read_text());arrays=np.load(BASE/'states'/case/'arrays.npz')
    kernel=w.Kernel(metadata,monotonic()+300);label=kinds(metadata['n_segments']);digits=80
    rounding=result['rounding'];points={f'x{k}':[D(s) for s in p] for k,p in enumerate(rounding['points'])}
    points.update({n+'r':cv.to_decimal(rounding['rounded'][n]['point']) for n in ['x1','x3']})
    def shifted_values(point):
        primal=kernel.primal(point,digits)
        with localcontext() as ctx:
            ctx.prec=digits;return [m+kernel.rho*g for m,g in zip(kernel.mu,primal[2])]
    base=shifted_values(cv.to_decimal(y));active0=[s>0 for s in base]
    order=sorted(range(len(base)),key=lambda i:abs(base[i]))[:3]
    nearest=[dict(index=i,kind=label[i],shifted=float(base[i]),mu=metadata['mu'][i],active=active0[i]) for i in order]
    path={}
    previous=active0
    for name in ['x1','x2','x3','x1r','x3r']:
        act=[s>0 for s in shifted_values(points[name])]
        path[name]=dict(switched_from_x0=[label[i] for i in range(len(act)) if act[i]!=active0[i]])
        if name in ('x2','x3'):path[name]['switched_from_previous']=[label[i] for i in range(len(act)) if act[i]!=previous[i]]
        if name in ('x1','x2','x3'):previous=act
    with localcontext() as ctx:
        ctx.prec=digits
        d1=[b-a for a,b in zip(points['x1'],points['x2'])];d2=[b-a for a,b in zip(points['x2'],points['x3'])]
        reversal=float(sum((a+b)**2 for a,b in zip(d1,d2)).sqrt()/sum(a*a for a in d1).sqrt())
    directions=[]
    for row,v in zip(result['directions'],arrays['directions']):
        plus,minus=cv.shifted(cv.to_decimal(y),v,'1e-10',digits)
        switched=sorted({label[i] for p in (plus,minus) for i,s in enumerate(shifted_values(p)) if (s>0)!=active0[i]})
        directions.append(dict(name=row['name'],switched_at_1e_10=switched))
    arrays.close()
    out=dict(case=case,planned=False,optimizer_launched=False,nearest_to_switch_at_x0=nearest,newton_path=path,
        step2_plus_step3_over_step2=reversal,low_direction_switches=directions,scalar_evaluations=kernel.calls)
    (BASE/'posthoc'/f'{case}.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out),flush=True)


def main():
    import driver
    with driver.guard.protocol_lock():
        (BASE/'posthoc').mkdir(exist_ok=False)
        for row in json.loads((BASE/'targets.json').read_text())['contexts']:
            env=dict(os.environ,UAV_R2_CASE=row['case'],OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
            subprocess.run([sys.executable,str(Path(__file__).resolve()),'--worker'],env=env,check=True)


if __name__=='__main__':worker() if '--worker' in sys.argv else main()
