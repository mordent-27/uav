"""Post-hoc (not in PLAN.md): is the stalled tau6 point on a CC/CV switch of the battery model? Evaluation only."""
from decimal import Decimal as D,localcontext
import json
from pathlib import Path
import numpy as np
import helpers as h
import kink

BASE=Path(__file__).resolve().parent


def main():
    targets=json.loads((BASE/'targets.json').read_text());S=targets['side'];ctx=S['context']
    metadata=json.loads((h.ROOT/ctx['metadata_source']).read_text())['metadata'];side=json.loads((BASE/'side'/'result.json').read_text())
    ns=metadata['n_segments'];offset=2*(ns-1);b=kink.binary;digits=100
    data=np.load(h.ROOT/ctx['samples']);y0=data['y'].copy();data.close()
    out=dict(planned=False,optimizer_launched=False,points={})
    with localcontext() as c:
        c.prec=digits;p={k:b(v) for k,v in metadata['phys'].items()}
        out['cc_slope_minus_cv_slope']=str(p['kappa']-p['span']/p['sigma'])
        out['cc_cv_value_gap_at_switch']=str((p['e_th'])-(p['e_max']-p['span']))
    def scalar(q):return kink.piece_al(kink.reference.evaluate(q,metadata,digits),metadata,digits)
    for name,point in [('x0',kink.lowcurv.to_decimal(y0)),('inactive_x5',[D(v) for v in side['pieces']['inactive']['point']])]:
        with localcontext() as c:
            c.prec=digits;x=[v*b(s) for v,s in zip(point,metadata['scale'])]
            energy=[p['e_max'],*x[offset:offset+ns]];charges=x[offset+2*ns:offset+3*ns]
            margins=[]
            for k in range(ns):
                e,q=energy[k],charges[k]
                if q>=0 and e<p['e_th']:margins.append((k,q-(p['e_th']-e)/p['kappa']))
        nearest=sorted(margins,key=lambda m:abs(m[1]))[:3]
        row=dict(nearest_cc_cv=[dict(segment=k,charge_minus_switch=str(m),float=float(m)) for k,m in nearest],one_sided={})
        base=scalar(point)
        for label,index in [('c17',offset+2*ns+17),('e16',offset+16)]:
            for t in ['1e-24','1e-30']:
                with localcontext() as c:
                    c.prec=digits;tt=D(t);plus=point.copy();plus[index]+=tt;minus=point.copy();minus[index]-=tt
                    forward=(scalar(plus)-base)/tt;backward=(base-scalar(minus))/tt
                    row['one_sided'][f'{label}@{t}']=dict(forward=float(forward),backward=float(backward),jump=float(forward-backward))
        out['points'][name]=row
    with localcontext() as c:
        c.prec=digits;k=17;w=b(metadata['lam'][k]);hk=kink.reference.evaluate([D(v) for v in side['pieces']['inactive']['point']],metadata,digits)[1][k]
        factor=(w+b(metadata['rho'])*hk)*p['range']*b(metadata['wh'][k])*b(metadata['scale'][offset+2*ns+k])
        out['predicted_c17_jump']=float(factor*(p['kappa']-p['span']/p['sigma']))
        out['battery17_effective_multiplier']=float(w+b(metadata['rho'])*hk)
    (BASE/'posthoc-battery.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=1))


if __name__=='__main__':main()


def curvature_along_newton_step():
    """Second post-hoc check: Decimal curvature along the next fixed-H Newton direction at the inactive x5, vs the old H."""
    targets=json.loads((BASE/'targets.json').read_text());ctx=targets['side']['context']
    metadata=json.loads((h.ROOT/ctx['metadata_source']).read_text())['metadata'];side=json.loads((BASE/'side'/'result.json').read_text())
    data=np.load(h.ROOT/ctx['samples']);H=data['H'].copy();data.close();g=np.load(BASE/'side'/'arrays.npz')['inactive_piece_gradient']
    cv=kink.lowcurv;w,V,keep,_=cv.spectral_split(H,targets['side']['pinv_rcond']);d,_=cv.newton_step(w,V,keep,g)
    x=[D(v) for v in side['pieces']['inactive']['point']];ns=metadata['n_segments'];offset=2*(ns-1);out={}
    def scalar(q):return kink.piece_al(kink.reference.evaluate(q,metadata,100),metadata,100,targets['side']['index'],'inactive')
    base=scalar(x)
    for name,v in [('newton_direction',d/np.linalg.norm(d)),('c17',np.eye(len(g))[offset+2*ns+17]),('e16',np.eye(len(g))[offset+16])]:
        plus,minus=cv.shifted(x,v,'1e-24',100);q=cv.second_quotient(scalar(plus),base,scalar(minus),'1e-24',100)
        out[name]=dict(decimal_curvature=float(q),old_hessian_curvature=float(v@H@v),ratio=float(q)/float(v@H@v))
    out['newton_step_norm']=float(np.linalg.norm(d));out['predicted_gradient_change_norm']=float(np.linalg.norm(H@d))
    path=BASE/'posthoc-battery.json';data=json.loads(path.read_text());data['curvature_along_step']=out
    path.write_text(json.dumps(data,indent=2)+'\n');print(json.dumps(out,indent=1))
