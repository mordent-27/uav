"""Single-factor variant of hessian_of_al: one-sided columns for coordinates whose stencil can cross a CC/CV switch."""
import importlib.util
from pathlib import Path
import sys
import numpy as np

HERE=Path(__file__).resolve().parent


def _load(name,path):
    if name in sys.modules:
        assert Path(sys.modules[name].__file__).resolve()==path.resolve(),name
        return sys.modules[name]
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module;spec.loader.exec_module(module);return module


fixh=_load('fixh',HERE.parent/'2026-11-16-switch-hessian/fixh.py')
inner=_load('precise_inner_loop',HERE.parent/'2026-11-16-precise-inner/inner.py')


def switch_rule(scale,phys,ns,step):
    """Return y -> {coordinate: side} for coordinates whose central stencil can cross a CC/CV switch."""
    def rule(y):
        rows=fixh.margins(y,scale,phys,ns);J,reasons=fixh.straddling(rows,scale,phys,ns,step)
        margin={r['segment']:r['margin'] for r in rows}
        return {j:(1 if margin[r['segment']]>=0 else -1) for j,r in zip(J,reasons)}
    return rule


def hessian_onesided(hessian_of_al,frozen,y,step,counters,rule,stats):
    """Old Hessian; then replace raw columns of the straddling coordinates by one-sided differences toward the point's side."""
    H,asymmetry=hessian_of_al(frozen,y,step,counters);sides=rule(y)
    stats['builds']+=1
    if not sides:return H,asymmetry
    stats['triggered']+=1;stats['max_coordinates']=max(stats['max_coordinates'],len(sides))
    m=frozen.m;m.eval(y,frozen.lam,frozen.mu,frozen.rho);h,g=m.h.copy(),m.g.copy()
    le=frozen.lam+frozen.rho*h;mi=np.maximum(0.,frozen.mu+frozen.rho*g)
    base=np.array(m.eval(y,le,mi,0.)[1],dtype=float).copy();D=np.zeros_like(H)
    for j,s in sides.items():
        a,b=y.copy(),y.copy();a[j]+=step;b[j]-=step
        central=(np.array(m.eval(a,le,mi,0.)[1],dtype=float).copy()-np.array(m.eval(b,le,mi,0.)[1],dtype=float).copy())/(2*step)
        c=y.copy();c[j]+=s*step;onesided=(np.array(m.eval(c,le,mi,0.)[1],dtype=float).copy()-base)/(s*step)
        D[:,j]=onesided-central
    if counters is not None:counters['gradient_calls']+=1+3*len(sides)
    return H+(D+D.T)/2,asymmetry
