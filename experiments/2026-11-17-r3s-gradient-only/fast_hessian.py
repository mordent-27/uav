"""R-only gradient path for finite differences with fixed multipliers, rho=0."""
import numpy as np


def gradient_only(m,y,lam,mu):
    assert m.kind=='R'
    q=np.ascontiguousarray(y*m.ratio)
    _,gradient=m.native.eval(q,np.ascontiguousarray(m.wh*lam),np.ascontiguousarray(m.wg*mu),0.)
    m.h=(m.native.h*m.wh).copy();m.g=(m.native.g*m.wg).copy()
    return gradient*m.ratio


def hessian_of_al(frozen,y,step=1e-7,counters=None):
    m=frozen.m
    assert m.kind=='R' and np.isfinite(y).all() and np.isfinite(frozen.lam).all() and np.isfinite(frozen.mu).all()
    m.eval(y,frozen.lam,frozen.mu,frozen.rho)
    h,g=m.h.copy(),m.g.copy()
    le=frozen.lam+frozen.rho*h
    shifted=frozen.mu+frozen.rho*g
    active=shifted>0
    mi=np.maximum(0.,shifted)
    jac=m.jacobian(y)
    raw=np.empty((len(y),len(y)))
    for j in range(len(y)):
        a,b=y.copy(),y.copy();a[j]+=step;b[j]-=step
        raw[:,j]=(gradient_only(m,a,le,mi)-gradient_only(m,b,le,mi))/(2*step)
    if counters is not None:
        # Same logical Hessian counters as the reference, not native call counts.
        counters['gradient_calls']+=1+2*len(y);counters['jacobian_calls']+=1
    J=jac[:m.me];G=jac[m.me:][active]
    H=(raw+raw.T)/2+frozen.rho*(J.T@J+G.T@G)
    return H,float(np.max(abs(raw-raw.T)))
