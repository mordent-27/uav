"""Common TR loop; only evaluator arithmetic differs between the two arms."""
from decimal import localcontext
from pathlib import Path
import sys
from time import monotonic
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts'))
from trust_region import tr_step
from tr_acceptance import assess


def solve(evaluate,hessian,y,deadline,record=lambda row:None):
    start=monotonic();counts=dict(gradient_calls=0,jacobian_calls=0)
    f,g,exact=evaluate(y,deadline);accepted=0;scalar_calls=1;trials=0;delta=1.;status='max_iter';iterations=0
    def entry(kind,**more):
        return dict(kind=kind,y=y.tolist(),value=float(f),value_decimal=None if exact is None else str(exact),
            gradient_inf=float(max(abs(g))),**more)
    record(entry('input'))
    try:
        for it in range(300):
            iterations=it
            if monotonic()>=deadline:raise TimeoutError()
            if max(abs(g))<=1e-8:
                status='converged';break
            H=hessian(y,counts);w,V=np.linalg.eigh(H);took_step=False
            for _ in range(60):
                step,boundary=tr_step(w,V,g,delta);trials+=1
                assert np.linalg.norm(step)<=delta*(1+1e-12)+1e-30
                prediction=-float(g@step+.5*step@H@step)
                fn,gn,exact_n=evaluate(y+step,deadline);scalar_calls+=1
                reduction=None
                if exact is not None:
                    with localcontext() as ctx:
                        ctx.prec=80;reduction=float(exact-exact_n)
                decision=assess(f,fn,prediction,float(np.linalg.norm(g)),float(np.linalg.norm(gn)),
                    delta,float(np.linalg.norm(step)),bool(boundary),actual_decrease=reduction)
                delta=decision.radius
                if decision.accepted:
                    y,f,g,exact=y+step,fn,gn,exact_n;accepted+=1;took_step=True
                    record(entry('accepted',iteration=accepted,delta=float(delta),ratio=decision.ratio,
                        prediction=prediction,gradient_fallback=decision.gradient_fallback,seconds=monotonic()-start))
                    break
                if delta<1e-14:break
            if not took_step:
                status='stuck';break
        else:iterations=300
    except TimeoutError:status='timeout'
    return dict(y=y.tolist(),gradient=g.tolist(),value=float(f),value_decimal=None if exact is None else str(exact),
        gradient_inf=float(max(abs(g))),status=status,iterations=iterations,accepted=accepted,
        scalar_calls=scalar_calls,trials=trials,seconds=monotonic()-start,
        hessian_gradient_calls=counts['gradient_calls'],jacobian_calls=counts['jacobian_calls'])
