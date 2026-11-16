"""Pure helpers for low-curvature and point-rounding diagnostics. No optimizer is called here."""
from decimal import Decimal as D,localcontext
import importlib.util
from pathlib import Path
import sys
import numpy as np

PRECISE=Path(__file__).resolve().parent.parent/'2026-11-16-precise-inner'


def _load(name):
    """Load an unchanged precise-inner module by file path (other experiment folders reuse these names)."""
    if name in sys.modules:
        assert Path(sys.modules[name].__file__).resolve()==PRECISE/f'{name}.py',name
        return sys.modules[name]
    spec=importlib.util.spec_from_file_location(name,PRECISE/f'{name}.py');module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module;spec.loader.exec_module(module);return module


battery_reference=_load('battery_reference');reference=_load('reference');precision=_load('precision')
binary=battery_reference.binary


def to_decimal(point):
    """Exact Decimal copy of binary64 coordinates; Decimal entries pass through unchanged."""
    return [binary(v) for v in point]


def nearest_binary(point):
    """Round each Decimal coordinate to the nearest binary64 (CPython float(Decimal) is correctly rounded)."""
    return np.array([float(v) for v in point])


def shifted(x,v,t,digits):
    """Points x+t*v and x-t*v kept in Decimal, never rounded to binary64."""
    with localcontext() as ctx:
        ctx.prec=digits;t=D(t);v=[binary(a) for a in v]
        return [a+t*b for a,b in zip(x,v)],[a-t*b for a,b in zip(x,v)]


def second_quotient(plus,base,minus,t,digits):
    with localcontext() as ctx:
        ctx.prec=digits;t=D(t)
        return (plus-2*base+minus)/(t*t)


def hessian_action(gradient,x,v,t,digits):
    """Central difference of a Decimal gradient along v: [g(x+tv)-g(x-tv)]/(2t)."""
    plus,minus=shifted(x,v,t,digits);gp=gradient(plus);gm=gradient(minus)
    with localcontext() as ctx:
        ctx.prec=digits;t=D(t)
        return [(a-b)/(2*t) for a,b in zip(gp,gm)]


def spectral_split(H,rcond):
    """Eigenpairs kept by a pseudo-inverse with numpy's pinv rule |lambda|>rcond*max|lambda|."""
    w,V=np.linalg.eigh(H);cut=rcond*float(max(abs(w)));keep=abs(w)>cut
    return w,V,keep,cut


def newton_step(w,V,keep,g):
    """Pseudo-inverse Newton step and the gradient part left in the dropped subspace."""
    c=V.T@g
    return -(V[:,keep]@(c[keep]/w[keep])),V[:,~keep]@c[~keep]


def rounding_floors(H,y):
    """Linearised gradient changes caused by rounding the point to the binary64 grid."""
    u=np.spacing(np.abs(np.asarray(y,dtype=float)));A=np.abs(H)*u[None,:]
    return dict(worst_half_ulp=float(max(A.sum(axis=1)/2)),
        uniform_rms=float(max(np.sqrt(((H*u[None,:])**2).sum(axis=1)/12))),
        single_half_ulp=float(A.max()/2))


def step_in_ulps(d,point):
    u=np.spacing(np.abs(nearest_binary(point)));ratio=np.abs(d)/u
    return dict(max_ulps=float(ratio.max()),below_half_ulp=int(np.count_nonzero(ratio<.5)),coordinates=len(d))


def curvature_class(q,threshold):
    if q<-threshold:return 'negative'
    return 'near_zero' if q<=threshold else 'positive'


def rounding_verdict(high_precision_inf,rounded_inf,target):
    if high_precision_inf>target:return 'high_precision_point_not_reached'
    return 'rounding_blocks_target' if rounded_inf>target else 'binary64_point_reaches_target'
