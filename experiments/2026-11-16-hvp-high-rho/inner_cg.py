"""Steihaug CG and the existing diagnostic acceptance loop, with directional HVP."""
from time import monotonic
import numpy as np
from curvature_operator import DirectionalCurvature


def cg_step(matvec, g, delta, eta=None):
    p=np.zeros_like(g);r=g.copy();norm=float(np.linalg.norm(g))
    if norm==0:return p,False,0,'zero_gradient'
    eta=min(.5,np.sqrt(norm)) if eta is None else eta
    d=-r;rr=float(r@r)
    def boundary():
        pd=float(p@d);dd=float(d@d)
        t=(-pd+np.sqrt(max(0.,pd*pd+dd*(delta*delta-float(p@p)))))/dd
        return p+t*d
    for k in range(len(g)):
        hd=matvec(d);curvature=float(d@hd)
        if curvature<=1e-12*float(d@d):
            return boundary(),True,k+1,'nonpositive_curvature'
        alpha=rr/curvature;trial=p+alpha*d
        if np.linalg.norm(trial)>=delta:
            return boundary(),True,k+1,'boundary'
        p=trial;r=r+alpha*hd;next_rr=float(r@r)
        if np.sqrt(next_rr)<=eta*norm:return p,False,k+1,'residual'
        d=-r+(next_rr/rr)*d;rr=next_rr
    return p,False,len(g),'iteration_limit'


def solve(frozen,y,deadline,record=lambda row:None):
    start=monotonic();scalar_calls=1;setups=0;queries=0;trials=0;cg_iterations=0
    f,g=frozen.eval(y);status='max_iter';accepted_total=0;delta=1.;iterations=0
    reasons={}
    record(dict(kind='input',y=y.tolist(),value=float(f),gradient_inf=float(max(abs(g)))))
    def guarded_matvec(v):
        nonlocal queries
        if monotonic()>=deadline:raise TimeoutError()
        queries+=1
        return op.matvec(v)
    try:
        for it in range(300):
            iterations=it
            if monotonic()>=deadline:raise TimeoutError()
            if max(abs(g))<=1e-8:
                status='converged';break
            op=DirectionalCurvature(frozen,y);setups+=1;accepted=False
            for _ in range(60):
                step,boundary,steps,reason=cg_step(guarded_matvec,g,delta)
                cg_iterations+=steps;reasons[reason]=reasons.get(reason,0)+1
                pred=-float(g@step+.5*step@guarded_matvec(step))
                if monotonic()>=deadline:raise TimeoutError()
                fn,gn=frozen.eval(y+step);scalar_calls+=1;trials+=1
                fallback=pred<=1e-13*max(1.,abs(f))
                ratio=(1. if np.linalg.norm(gn)<np.linalg.norm(g) else 0.) if fallback else (f-fn)/pred
                if ratio<.25:delta=.25*np.linalg.norm(step)
                elif ratio>.75 and boundary:delta=min(2*delta,1e3)
                if ratio>1e-4:
                    y,f,g,accepted=y+step,fn,gn,True;accepted_total+=1
                    record(dict(kind='accepted',iteration=accepted_total,y=y.tolist(),value=float(f),
                        gradient_inf=float(max(abs(g))),delta=float(delta),ratio=float(ratio),
                        prediction=float(pred),gradient_fallback=bool(fallback),cg_iterations=steps,
                        cg_reason=reason,seconds=monotonic()-start))
                    break
                if delta<1e-14:break
            if not accepted:
                status='stuck';break
        else:iterations=300
    except TimeoutError:status='timeout'
    return dict(y=y,value=float(f),gradient=g,gradient_inf=float(max(abs(g))),status=status,
        iterations=iterations,accepted=accepted_total,scalar_calls=scalar_calls,
        hessian_gradient_calls=setups+2*queries,jacobian_calls=setups,
        seconds=monotonic()-start,eig=None,hvp_queries=queries,setups=setups,
        cg_iterations=cg_iterations,cg_reasons=reasons,trial_evaluations=trials)


def analytic_checks():
    cases=[('spd',np.diag([1.,2.]),np.array([1.,1.]),10.,[-1.,-.5]),
        ('negative',np.diag([-1.,2.]),np.array([1.,0.]),1.,[-1.,0.]),
        ('boundary',np.eye(2),np.array([2.,0.]),.5,[-.5,0.]),
        ('zero',np.eye(2),np.zeros(2),1.,[0.,0.])]
    rows=[]
    for name,H,g,delta,expected in cases:
        p,b,n,reason=cg_step(lambda v:H@v,g,delta,eta=1e-12)
        np.testing.assert_allclose(p,expected,atol=1e-12,rtol=1e-12)
        assert np.linalg.norm(p)<=delta+1e-12
        rows.append(dict(case=name,step=p.tolist(),boundary=b,iterations=n,reason=reason))
    return rows
