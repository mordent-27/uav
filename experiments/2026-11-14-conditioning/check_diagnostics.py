"""Check trust-region quadratic optimality and Hessian finite-difference sensitivity."""
import json
from pathlib import Path

import numpy as np
from scipy.optimize import minimize
import newton_al as na

HERE=Path(__file__).resolve().parent


def main():
    rng=np.random.default_rng(407)
    maximum=0.
    for index in range(24):
        n=6;V=np.linalg.qr(rng.normal(size=(n,n)))[0]
        w=np.sort(rng.uniform(-3.,5.,n))
        if index%3==0:w=np.sort(rng.uniform(.1,5.,n))
        g=rng.normal(size=n)
        if index%5==0:g=np.zeros(n)  # hard case with a negative eigenvalue
        delta=.2+index/10
        step,boundary=na.tr_step(w,V,g,delta);H=(V*w)@V.T
        assert np.linalg.norm(step)<=delta*(1+1e-9)
        shift=max(0.,-float(step@(H@step+g))/max(float(step@step),1e-300))
        error=np.max(np.abs((H+shift*np.eye(n))@step+g));maximum=max(maximum,float(error))
        assert error<1e-7 and w[0]+shift>=-1e-7
        assert shift*abs(np.linalg.norm(step)-delta)<1e-7
    results=[]
    for variant,library in [('squared','/tmp/uav-reproduction-bridge.so'),('normalized','/tmp/uav-reproduction-speed.so')]:
        m=na.Model(1,0,library);m.stage(.2,2.)
        lam,mu=np.zeros(m.me),np.zeros(m.mi)
        fg=lambda q:m.eval(q,lam,mu,10.)
        result=minimize(fg,m.y.copy(),jac=True,method='BFGS',options=dict(gtol=1e-9,maxiter=20000))
        eigen=[]
        for h in [1e-4,1e-5,1e-6,1e-7,1e-8]:
            values=np.linalg.eigvalsh(na.fd_hessian(lambda q:fg(q)[1],result.x,step=h))
            eigen.append(dict(step=h,minimum=float(values[0]),maximum=float(values[-1]),
                              condition_2=float(max(abs(values))/min(abs(values))),negative=int(sum(values<0))))
        results.append(dict(variant=variant,iterations=result.nit,gradient=float(max(abs(result.jac))),
                            solver_status=result.message,spectra=eigen))
        m.close()
    output=dict(quadratic_cases=24,maximum_trust_region_stationarity_error=maximum,
                spectra=results,note='Finite difference Hessians, not an exact-Hessian proof of local minimality')
    (HERE/'diagnostic-checks.json').write_text(json.dumps(output,indent=2)+'\n')
    print(json.dumps(output,indent=2))


if __name__=='__main__':main()
