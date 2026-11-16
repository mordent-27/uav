"""Eigenvalue TR subproblem used by new diagnostics; old experiments stay frozen.

The inputs w, V are an ordered eigendecomposition of a symmetric matrix.
The spectral shift search follows the earlier diagnostic implementation. Only
the hard-case boundary arithmetic and input checks are changed here.
"""
import numpy as np


def tr_step(w, V, g, delta):
    """Return (step, on_boundary) for g.T*p + p.T*H*p/2, ||p|| <= delta."""
    w,V,g=np.asarray(w),np.asarray(V),np.asarray(g)
    if w.ndim!=1 or g.shape!=w.shape or V.shape!=(len(w),len(w)) or not len(w):
        raise ValueError('inconsistent eigendecomposition or gradient dimensions')
    if not all(np.all(np.isfinite(a)) for a in (w,V,g)) or not np.isfinite(delta) or delta<0:
        raise ValueError('finite inputs and a nonnegative radius are required')
    if np.any(w[1:]<w[:-1]):
        raise ValueError('eigenvalues must be ordered')
    if delta==0:
        return np.zeros_like(g,dtype=float),True
    gt=V.T@g
    if w[0]>0:
        p=-gt/w
        if np.linalg.norm(p)<=delta:
            return V@p,False
    lo=max(0.,-w[0])+1e-14*max(1.,abs(w[0]))
    hi=max(lo*2,1.)
    norm=lambda sig:np.linalg.norm(gt/(w+sig))
    if norm(lo)<=delta:
        p=-gt/(w+lo)
        # Replace the component: adding sqrt(delta^2-||p||^2) would omit
        # the cross term 2*p[0]*t whenever p[0] is not exactly zero.
        magnitude=np.sqrt(max(delta**2-p[1:]@p[1:],0.))
        p[0]=magnitude if gt[0]<=0 else -magnitude
        return V@p,True
    while norm(hi)>delta:
        hi*=4
    for _ in range(200):
        mid=np.sqrt(lo*hi) if lo>0 else (lo+hi)/2
        if norm(mid)>delta:lo=mid
        else:hi=mid
        if hi-lo<=1e-12*hi:break
    return V@(-gt/(w+hi)),True
