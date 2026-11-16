"""Pure helpers for the one-sided AL pieces at a weakly active PHR term. No optimizer is called here."""
from decimal import Decimal as D,localcontext
import importlib.util
from pathlib import Path
import sys
from time import monotonic
import numpy as np

HERE=Path(__file__).resolve().parent


def _load(name,path):
    """Load an unchanged module by file path under a fixed name (experiment folders reuse file names)."""
    if name in sys.modules:
        assert Path(sys.modules[name].__file__).resolve()==path.resolve(),name
        return sys.modules[name]
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module;spec.loader.exec_module(module);return module


lowcurv=_load('lowcurv',HERE.parent/'2026-11-16-curvature-rounding/lowcurv.py')
reference=lowcurv.reference;precision=lowcurv.precision;binary=lowcurv.binary


def piece_al(primal,metadata,digits,index=None,mode='true'):
    """precision.absolute_al with one PHR term optionally fixed to its inactive or active branch."""
    assert mode in ('true','inactive','active')
    with localcontext() as ctx:
        ctx.prec=digits;value,eq,ineq=primal;rho=binary(metadata['rho'])
        value+=sum((binary(w)*v+rho*v*v/2 for w,v in zip(metadata['lam'],eq)),D(0))
        def shifted(i,w,v):
            s=binary(w)+rho*v
            if i!=index or mode=='true':return max(D(0),s)
            return D(0) if mode=='inactive' else s
        value+=sum(((shifted(i,w,v)**2-binary(w)**2)/(2*rho) for i,(w,v) in enumerate(zip(metadata['mu'],ineq))),D(0))
        return value


def shifted_values(primal,metadata,digits):
    with localcontext() as ctx:
        ctx.prec=digits;rho=binary(metadata['rho'])
        return [binary(w)+rho*v for w,v in zip(metadata['mu'],primal[2])]


def central_pair(primal,values,point,digits,step,deadline=float('inf')):
    """Central-difference gradients of several value functions sharing the same primal evaluations."""
    with localcontext() as ctx:
        ctx.prec=digits;point=[binary(v) for v in point];step=D(step);out=[[] for _ in values]
        if step<=0:raise ValueError('positive difference step required')
        for i in range(len(point)):
            if monotonic()>=deadline:raise TimeoutError()
            plus=point.copy();plus[i]+=step;minus=point.copy();minus[i]-=step
            pp,pm=primal(plus),primal(minus)
            for gradient,value in zip(out,values):gradient.append((value(pp)-value(pm))/(2*step))
        return out


def side_ok(mode,s):return s<=0 if mode=='inactive' else s>=0


def piece_verdict(gradient_inf,mode,s,other_switches,target):
    reasons=[]
    if gradient_inf>target:reasons.append('gradient')
    if not side_ok(mode,s):reasons.append('side')
    if other_switches:reasons.append('other_switches')
    return 'valid' if not reasons else 'invalid',reasons


def lattice_steps(y,k):
    """Move each coordinate by k_j exact binary64 neighbours (np.nextafter), so binade changes stay exact."""
    out=np.array(y,dtype=float).copy()
    for j,n in enumerate(k):
        for _ in range(abs(int(n))):out[j]=np.nextafter(out[j],np.inf if n>0 else -np.inf)
    return out


def lattice_search(g,H,y,limit=8,sweeps=5):
    """Coordinate sweeps over integer ulp moves minimising the linear model ||g+H*delta||_2."""
    y=np.asarray(y,dtype=float);u=np.spacing(np.abs(y));k=np.zeros(len(y),dtype=int);r=np.array(g,dtype=float).copy()
    used=0
    for _ in range(sweeps):
        used+=1;changed=0
        for j in range(len(y)):
            col=H[:,j]*u[j];cc=float(col@col)
            if cc==0.:continue
            base=r-k[j]*col;best=int(np.clip(np.rint(-(base@col)/cc),-limit,limit))
            if best!=k[j]:r=base+best*col;k[j]=best;changed+=1
        if not changed:break
    point=lattice_steps(y,k);actual=np.array(g,dtype=float)+H@(point-y)  # point-y is exact for neighbouring floats
    return point,k,dict(sweeps=used,moved=int(np.count_nonzero(k)),max_abs_k=int(abs(k).max()) if len(k) else 0,
        model_gradient_norm=float(np.linalg.norm(r)),model_gradient_inf=float(abs(r).max()),start_norm=float(np.linalg.norm(g)),
        actual_step_model_gradient_inf=float(abs(actual).max()),actual_step_model_gradient_norm=float(np.linalg.norm(actual)))
