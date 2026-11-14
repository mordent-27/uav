"""Same frozen figure-1 AL subproblem; vary only Hessian differentiation accuracy."""
import json
from pathlib import Path
import sys
from time import monotonic

import numpy as np

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'2026-11-14-conditioning'))
import newton_al as na

source=HERE/'cases/fig1/state.json';d=json.loads(source.read_text())
m=na.Model(0,0,library='/tmp/uav-reproduction-speed.so');m.stage(.0005,12.)
y,lam,mu=(np.array(d[k]) for k in ['y','lam','mu']);rho=d['rho']
value,gradient=m.eval(y,lam,mu,rho)
rows=[]
for step in [1e-6,1e-7,1e-8]:
    start=monotonic()
    result=na.tr_newton(lambda q:m.eval(q,lam,mu,rho),y.copy(),gtol=1e-6,max_iter=300,hessian_step=step)
    check,grad=m.eval(result['y'],lam,mu,rho)
    rows.append(dict(hessian_step=step,initial_value=value,initial_gradient=float(max(abs(gradient))),
        final_value=check,final_gradient=float(max(abs(grad))),iterations=result['iters'],
        status=result['status'],seconds=monotonic()-start))
    print(json.dumps(rows[-1]),flush=True)
passed=all(row['final_gradient']<=1e-6 and row['final_value']<=rows[0]['final_value']+1e-12 for row in rows[1:])
out=dict(source=str(source.relative_to(HERE)),comparisons=rows,continuation_allowed=passed)
(HERE/'hessian-step-check.json').write_text(json.dumps(out,indent=2)+'\n');m.close()
