"""Independent scalar reference for the entire fixed smooth AL, using Decimal."""
from decimal import Decimal as D,localcontext
from battery_reference import binary,constraints as battery_constraints


def number(x):return x if isinstance(x,D) else binary(x)


def norm(v):return sum((a*a for a in v),D(0)).sqrt()
def difference(a,b):return [x-y for x,y in zip(a,b)]


def psi(y,width):
    if y<=-width:return D(0)
    if y<=width:return (y+width)**2/(4*width)
    return y


def smooth_min(z,p):
    minimum=min(z)
    return minimum*sum(((minimum/a)**p for a in z),D(0))**(-D(1)/p)


def evaluate(point,metadata,digits):
    with localcontext() as ctx:
        ctx.prec=digits
        # Battery helper accepts Decimal coordinates without rounding them to float.
        p={k:binary(v) for k,v in metadata['phys'].items()}
        x=[number(v)*binary(s) for v,s in zip(point,metadata['scale'])]
        ns=metadata['n_segments'];offset=2*(ns-1)
        eps,power,width=[binary(metadata[k]) for k in ['eps','p','smoothing_delta']]
        instance=metadata['instance']
        positions=[[binary(a) for a in instance['r0']]]
        positions += [x[2*k:2*k+2] for k in range(ns-1)]
        positions += [[binary(a) for a in instance['rf']]]
        durations=x[offset+ns:offset+2*ns];charges=x[offset+2*ns:offset+3*ns]
        battery,bounds=battery_constraints(point,metadata,digits)
        tasks=[]
        for task in instance['tasks']:
            a=[binary(v) for v in task]
            z=[(sum((v*v for v in difference(r,a)),D(0))+eps*eps).sqrt() for r in positions]
            tasks.append(smooth_min(z,power)-eps)
        modes=[];speed=[]
        for k in range(ns):
            a,b=positions[k:k+2];s,c=durations[k],charges[k]
            distance=norm(difference(a,b));violation=psi(distance-p['v_c']*s,width)
            z=[(c*c+eps*eps).sqrt()]
            for region in instance['regions']:
                center=[binary(v) for v in region['o']];radius=binary(region['rho'])
                first=psi(norm(difference(a,center))-radius,width)
                second=psi(norm(difference(b,center))-radius,width)
                z.append(((c-s)**2+first*first+second*second+violation*violation+eps*eps).sqrt())
            modes.append(smooth_min(z,power)-eps)
            numerator=distance*distance-p['v_d']**2*s*abs(s)
            denominator=(distance*distance+width*width).sqrt()+(p['v_d']**2*s*s+width*width).sqrt()
            speed.append(numerator/denominator*binary(metadata['wg'][k]))
        return sum(durations,D(0)),[*battery,*tasks,*modes],[*speed,*bounds]


def al_difference(base,trial,metadata,digits):
    with localcontext() as ctx:
        ctx.prec=digits;f0,h0,g0=base;f1,h1,g1=trial
        rho=binary(metadata['rho']);lam=[binary(v) for v in metadata['lam']];mu=[binary(v) for v in metadata['mu']]
        eq=[(b-a)*(w+rho*(a+b)/2) for a,b,w in zip(h0,h1,lam)]
        iq=[(max(D(0),w+rho*b)**2-max(D(0),w+rho*a)**2)/(2*rho) for a,b,w in zip(g0,g1,mu)]
        ns=metadata['n_segments'];nt=len(metadata['instance']['tasks'])
        parts=dict(objective=f1-f0,battery=sum(eq[:ns],D(0)),tasks=sum(eq[ns:ns+nt],D(0)),
            modes=sum(eq[ns+nt:],D(0)),speed=sum(iq[:ns],D(0)),bounds=sum(iq[ns:],D(0)))
        return sum(parts.values(),D(0)),parts
