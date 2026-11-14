"""Conditional second figure-1 continuation; only Hessian FD step changes to 1e-7."""
import json
from pathlib import Path
from time import monotonic

import numpy as np
from continue_final import na,canonical,audit

HERE=Path(__file__).resolve().parent
gate=json.loads((HERE/'hessian-step-check.json').read_text())
assert gate['continuation_allowed']
source=HERE/'cases/fig1';directory=HERE/'fig1-refined';directory.mkdir(exist_ok=True)
assert not (directory/'result.json').exists(),'do not overwrite an existing run'
saved=json.loads((source/'state.json').read_text());prior=json.loads((source/'result.json').read_text())
m=na.Model(0,0,library='/tmp/uav-reproduction-speed.so');m.stage(.0005,12.)
original=na.Model(0,0);original.stage(.0005,12.)
y,lam,mu=(np.array(saved[k]) for k in ['y','lam','mu']);rho=saved['rho']
assert rho==1e4
start=monotonic();rows=[];stop='outer_limit'
with (directory/'outer.jsonl').open('w') as log:
    for outer in range(600):
        def fg(point):
            if monotonic()-start>300:raise TimeoutError()
            return m.eval(point,lam,mu,rho)
        try:res=na.tr_newton(fg,y,gtol=1e-6,max_iter=300,hessian_step=1e-7)
        except TimeoutError:stop='timeout';break
        y=np.ascontiguousarray(res['y'])
        m.eval(y,lam,mu,0.);lam+=rho*m.h;mu=np.maximum(0.,mu+rho*m.g)
        k=canonical(original,m,y,lam,mu)
        row=dict(extra_outer=outer+1,original_kkt=k,inner_status=res['status'],inner_iters=res['iters'],
                 elapsed=monotonic()-start)
        rows.append(row);log.write(json.dumps(row)+'\n');log.flush()
        (directory/'state.json').write_text(json.dumps(dict(y=y.tolist(),lam=lam.tolist(),mu=mu.tolist(),rho=rho))+'\n')
        if all(v<=1e-6 for v in k.values()):stop='kkt';break
doc=m.solution(y)
result=dict(case='fig1',source='cases/fig1/state.json',hessian_step=1e-7,rho=rho,stop=stop,
    kkt_converged=stop=='kkt',extra_outer=len(rows),extra_seconds=monotonic()-start,
    total_outer=prior['total_outer']+len(rows),total_seconds=prior['total_seconds']+monotonic()-start,
    original_kkt=canonical(original,m,y,lam,mu),objective=doc['metrics']['objective'],
    original_violation=doc['metrics']['viol'],physical_audit=audit.inspect(doc))
doc['experiment']=dict(result=result,y_full_precision=y.tolist(),lam=lam.tolist(),mu=mu.tolist())
doc['metrics']['converged']=result['kkt_converged']
(directory/'raw.json').write_text(json.dumps(doc,indent=2,allow_nan=False)+'\n')
(directory/'result.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='physical_audit'},indent=2),flush=True)
m.close();original.close()
