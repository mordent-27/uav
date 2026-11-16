"""precise-inner's TR loop with two switchable factors: acceptance (A legacy / B exact decrease) and stop (0 legacy / 1 floor)."""
from dataclasses import dataclass
from decimal import localcontext
from pathlib import Path
import sys
from time import monotonic
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts'))
from trust_region import tr_step  # noqa: E402  unchanged
from tr_acceptance import assess  # noqa: E402  unchanged


@dataclass(frozen=True)
class Exact:
    accepted:bool
    radius:float
    ratio:float


def assess_exact(prediction,decrease,radius,step_norm,boundary):
    """Ratio test on an exactly measured decrease; no gradient fallback. Radius rules as tr_acceptance.assess."""
    ratio=decrease/prediction if prediction>0 else 0.
    updated=radius
    if ratio<.25:updated=.25*step_norm
    elif ratio>.75 and boundary:updated=min(2*radius,1e3)
    return Exact(ratio>1e-4,updated,ratio)


def floor_estimate(H,y):
    u=np.spacing(np.abs(np.asarray(y,dtype=float)))
    return float(max(np.sqrt(((H*u[None,:])**2).sum(axis=1)/12)))


def floor_threshold(H,y,tol=1e-8,factor=2.):return max(tol,factor*floor_estimate(H,y))


def solve(evaluate,hessian,y,deadline,record=lambda row:None,exact_value=None,floor_stop=False,tol=1e-8,factor=2.):
    """evaluate(point,deadline)->(f,g); exact_value(point)->Decimal or None for acceptance A."""
    start=monotonic();counts=dict(gradient_calls=0,jacobian_calls=0)
    f,g=evaluate(y,deadline);accepted=0;scalar_calls=1;trials=0;delta=1.;status='max_iter';iterations=0;decimal_calls=0
    exact=None
    if exact_value is not None:exact=exact_value(y);decimal_calls+=1
    stop_info={}
    def entry(kind,**more):
        return dict(kind=kind,y=y.tolist(),value=float(f),value_decimal=None if exact is None else str(exact),gradient_inf=float(max(abs(g))),**more)
    record(entry('input'))
    try:
        for it in range(300):
            iterations=it
            if monotonic()>=deadline:raise TimeoutError()
            if max(abs(g))<=tol:
                status='converged';break
            H=hessian(y,counts)
            if floor_stop:
                threshold=floor_threshold(H,y,tol,factor)
                if max(abs(g))<=threshold:
                    status='converged_floor';stop_info=dict(floor=floor_estimate(H,y),threshold=threshold);break
            w,V=np.linalg.eigh(H);took_step=False
            for _ in range(60):
                step,boundary=tr_step(w,V,g,delta);trials+=1
                assert np.linalg.norm(step)<=delta*(1+1e-12)+1e-30
                prediction=-float(g@step+.5*step@H@step)
                fn,gn=evaluate(y+step,deadline);scalar_calls+=1
                if exact_value is None:
                    d=assess(f,fn,prediction,float(np.linalg.norm(g)),float(np.linalg.norm(gn)),delta,float(np.linalg.norm(step)),bool(boundary))
                    more=dict(gradient_fallback=d.gradient_fallback);exact_n=None
                else:
                    if monotonic()>=deadline:raise TimeoutError()
                    exact_n=exact_value(y+step);decimal_calls+=1
                    with localcontext() as ctx:
                        ctx.prec=80;decrease=float(exact-exact_n)
                    d=assess_exact(prediction,decrease,delta,float(np.linalg.norm(step)),bool(boundary));more=dict(decimal_decrease=decrease)
                delta=d.radius
                if d.accepted:
                    y,f,g,exact=y+step,fn,gn,exact_n;accepted+=1;took_step=True
                    record(entry('accepted',iteration=accepted,delta=float(delta),ratio=d.ratio,prediction=prediction,seconds=monotonic()-start,**more))
                    break
                if delta<1e-14:break
            if not took_step:
                status='stuck';break
        else:iterations=300
    except TimeoutError:status='timeout'
    return dict(y=y.tolist(),gradient=g.tolist(),value=float(f),value_decimal=None if exact is None else str(exact),
        gradient_inf=float(max(abs(g))),status=status,iterations=iterations,accepted=accepted,scalar_calls=scalar_calls,trials=trials,
        seconds=monotonic()-start,hessian_gradient_calls=counts['gradient_calls'],jacobian_calls=counts['jacobian_calls'],
        decimal_calls=decimal_calls,stop=stop_info)
