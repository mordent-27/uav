"""Restart both inner solvers from exactly the same failed final-stage AL state."""
import json
from pathlib import Path
from scipy.optimize import minimize
from independent_al import Model,np

HERE=Path(__file__).resolve().parent
d=json.loads((HERE/'diagnostics/tau1-speed-rust-full.json').read_text())
state=d['experiment']['stage_states'][-1]
m=Model(1,0,library='/tmp/uav-reproduction-speed.so');m.stage(.0005,12)
y=np.array(state['y']);lam=np.array(state['lam']);mu=np.array(state['mu']);rho=state['rho']
f0,g0=m.eval(y,lam,mu,rho)
rust_y=y.copy();res=np.empty(5)
m.lib.uav_rust_inner(m.ctx,m.ptr(rust_y),m.ptr(lam),m.ptr(mu),rho,2000,m.ptr(res))
result=minimize(lambda p:m.eval(p,lam,mu,rho),y.copy(),jac=True,method='BFGS',
                options=dict(gtol=1e-6,maxiter=2000))
out=dict(source='diagnostics/tau1-speed-rust-full.json',rho=rho,initial_value=f0,
         initial_grad=float(max(abs(g0))),
         rust=dict(value=float(res[0]),grad=float(res[1]),iterations=int(res[2]),evals=int(res[3]),status=int(res[4])),
         bfgs=dict(value=float(result.fun),grad=float(max(abs(result.jac))),iterations=result.nit,
                   evals=result.nfev,status=str(result.message)),
         note='same y, multipliers, rho, objective and gradient; inner AL only, not full NLP KKT')
(HERE/'inner-comparison.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2));m.close()
