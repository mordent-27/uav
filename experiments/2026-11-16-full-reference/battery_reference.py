"""Independent Decimal reference for battery and affine bound constraints only."""
from decimal import Decimal as D,localcontext


def binary(x):return x if isinstance(x,D) else D.from_float(float(x))


def charge(p,e,c):
    maximum,threshold,kappa=p['e_max'],p['e_th'],p['kappa']
    sigma=p['sigma'];span=p['span']
    def cv():return maximum-(maximum-e)*min(-c/sigma,D(60)).exp()
    if c>=0:
        if e>=threshold:return cv()
        tau=(threshold-e)/kappa
        return e+kappa*c if c<=tau else maximum-span*(-(c-tau)/sigma).exp()
    if e<=threshold:return e+kappa*c
    back=sigma*(span/(maximum-e)).ln() if e<maximum else D('Infinity')
    return cv() if -c<=back else threshold+kappa*(c+back)


def constraints(point,metadata,digits):
    with localcontext() as ctx:
        ctx.prec=digits
        p={k:binary(v) for k,v in metadata['phys'].items()}
        x=[binary(v)*binary(s) for v,s in zip(point,metadata['scale'])]
        ns=metadata['n_segments'];offset=2*(ns-1)
        energy=[p['e_max'],*x[offset:offset+ns]]
        durations=x[offset+ns:offset+2*ns];charges=x[offset+2*ns:offset+3*ns]
        wh=[binary(v) for v in metadata['wh']];wg=[binary(v) for v in metadata['wg']]
        battery=[p['range']*(energy[k+1]-charge(p,energy[k],charges[k])+
            p['zeta']*(durations[k]-charges[k]))*wh[k] for k in range(ns)]
        blocks=[[p['range']*(p['e_min']-e) for e in energy[1:]],
            [p['range']*(e-p['e_max']) for e in energy[1:]],
            [p['v_d']*(p['s_min']-s) for s in durations],
            [p['v_d']*(s-p['s_max']) for s in durations],[-p['v_d']*c for c in charges]]
        bounds=[v*wg[ns+i] for i,v in enumerate(v for block in blocks for v in block)]
        return battery,bounds


def delta(battery0,bounds0,battery1,bounds1,metadata,digits):
    with localcontext() as ctx:
        ctx.prec=digits;rho=binary(metadata['rho']);ns=metadata['n_segments']
        lam=[binary(v) for v in metadata['lam'][:ns]]
        mu=[binary(v) for v in metadata['mu'][ns:]]
        equalities=sum(((b-a)*(w+rho*(a+b)/2) for a,b,w in zip(battery0,battery1,lam)),D(0))
        inequalities=sum(((max(D(0),w+rho*b)**2-max(D(0),w+rho*a)**2)/(2*rho)
            for a,b,w in zip(bounds0,bounds1,mu)),D(0))
        return equalities,inequalities
