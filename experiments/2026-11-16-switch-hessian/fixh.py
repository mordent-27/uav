"""Pure helpers: CC/CV switch margins, the set of straddling coordinates, and the column replacement. No optimizer."""
from decimal import localcontext
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


kink=_load('kink',HERE.parent/'2026-11-16-kink-sides/kink.py')
lowcurv=kink.lowcurv;binary=kink.binary


def layout(ns):
    offset=2*(ns-1);return dict(e=lambda k:offset+k,s=lambda k:offset+ns+k,c=lambda k:offset+2*ns+k)


def margins(y,scale,phys,ns,digits=80):
    """CC/CV switch margin m_k=c_k-(e_th-e_in)/kappa in physical units, for segments with c_k>=0 and e_in<e_th."""
    L=layout(ns);out=[]
    with localcontext() as ctx:
        ctx.prec=digits;p={k:binary(v) for k,v in phys.items()}
        x=lambda i:binary(y[i])*binary(scale[i])
        for k in range(ns):
            e_in=p['e_max'] if k==0 else x(L['e'](k-1));c=x(L['c'](k))
            if c>=0 and e_in<p['e_th']:out.append(dict(segment=k,margin=c-(p['e_th']-e_in)/p['kappa']))
    return out


def straddling(rows,scale,phys,ns,t=1e-7):
    """Coordinates whose central difference of width t (scaled) can cross the CC/CV switch."""
    L=layout(ns);J=[];reasons=[]
    kappa=binary(phys['kappa']);t=binary(t)
    for r in rows:
        k=r['segment'];m=abs(r['margin'])
        ic=L['c'](k)
        if m<=t*binary(scale[ic]):J.append(ic);reasons.append(dict(index=ic,coordinate=f'c{k}',segment=k))
        if k>=1:
            ie=L['e'](k-1)
            if m<=t*binary(scale[ie])/kappa:J.append(ie);reasons.append(dict(index=ie,coordinate=f'e{k-1}',segment=k))
    order=sorted(set(J));return order,[next(r for r in reasons if r['index']==j) for j in order]


def replace_columns(H,J,columns):
    """H with rows/columns J replaced by the given columns; J-by-J entries are averaged to stay symmetric."""
    F=np.array(H,dtype=float).copy();C={j:np.asarray(c,dtype=float) for j,c in zip(J,columns)}
    for j in J:F[:,j]=C[j];F[j,:]=C[j]
    for i in J:
        for j in J:F[i,j]=(C[j][i]+C[i][j])/2
    return F


def gate(ratios,low=.999,high=1.001):return all(low<=r<=high for r in ratios)
