"""One fixed final point: Decimal curvature along low eigenvectors and the binary64 point-rounding test."""
from decimal import Decimal as D,localcontext
import json
import os
from pathlib import Path
from time import monotonic
import numpy as np
import helpers as h
import lowcurv as cv

evaluate=cv.reference.evaluate          # unchanged precise-inner modules, loaded by file path
absolute_al=cv.precision.absolute_al;central_gradient=cv.precision.central_gradient;binary=cv.binary

BASE=Path(__file__).resolve().parent


def floats(v):return np.array([float(a) for a in v])
def inf(v):return float(max(abs(np.asarray(v,dtype=float))))


def load(case):
    targets=json.loads((BASE/'targets.json').read_text())
    target=next(t for t in targets['contexts'] if t['case']==case)
    metadata=json.loads((h.ROOT/target['metadata_source']).read_text())['metadata']
    prior=json.loads((h.ROOT/target['result']).read_text());data=np.load(h.ROOT/target['samples'])
    y=data['y'].copy();H=data['H'].copy();data.close()
    frozen=h.stage4.Frozen(dict(json.loads((h.ROOT/prior['source']).read_text()),y=y.tolist()))
    return targets,target,metadata,frozen,y,H


class Kernel:
    """Decimal AL value/gradient with a shared deadline and call counter."""
    def __init__(self,metadata,deadline):
        self.metadata=metadata;self.deadline=deadline;self.calls=0
        self.rho=binary(metadata['rho']);self.mu=[binary(v) for v in metadata['mu']]

    def primal(self,point,digits):
        if monotonic()>=self.deadline:raise TimeoutError()
        self.calls+=1;return evaluate(point,self.metadata,digits)

    def value(self,primal,digits):return absolute_al(primal,self.metadata,digits)
    def scalar(self,point,digits):return self.value(self.primal(point,digits),digits)

    def active(self,primal,digits):
        with localcontext() as ctx:
            ctx.prec=digits;return [w+self.rho*v>0 for w,v in zip(self.mu,primal[2])]

    def gradient(self,point,digits,step):
        return central_gradient(lambda p:self.scalar(p,digits),point,digits,step,self.deadline)


def curvature_part(kernel,x0,H,C,record):
    w,V=np.linalg.eigh(H);order=list(range(C['low_eigenvectors']))+[len(w)-1]
    bases={}
    for digits in [C['digits'],C['reference_digits']]:
        primal=kernel.primal(x0,digits);bases[digits]=(kernel.value(primal,digits),kernel.active(primal,digits))
    def quotient(v,t,digits):
        plus,minus=cv.shifted(x0,v,t,digits);pp,pm=kernel.primal(plus,digits),kernel.primal(minus,digits)
        value,active=bases[digits]
        q=cv.second_quotient(kernel.value(pp,digits),value,kernel.value(pm,digits),t,digits)
        switches=sum(a!=b for a,b in zip(kernel.active(pp,digits),active))+sum(a!=b for a,b in zip(kernel.active(pm,digits),active))
        return q,int(switches)
    vectors=[];hvs=[]
    for rank,index in enumerate(order):
        v=V[:,index]/np.linalg.norm(V[:,index]);name=f'low{rank}' if rank<C['low_eigenvectors'] else 'max'
        values=[]
        for t in C['value_widths']:
            q,switches=quotient(v,t,C['digits']);values.append(dict(width=t,digits=C['digits'],q=str(q),q_float=float(q),active_switches=switches))
        q100,switches100=quotient(v,C['reference_width'],C['reference_digits'])
        with localcontext() as ctx:
            ctx.prec=C['reference_digits'];gap=abs(D(values[-1]['q'])-q100)
            valid=gap<=D(C['agreement_relative'])*max(D(1),abs(q100))
        hv=floats(cv.hessian_action(lambda p:kernel.gradient(p,C['digits'],C['gradient_step']),x0,v,C['hv_width'],C['digits']))
        q=float(q100);klass=cv.curvature_class(q,C['near_zero']) if valid else 'undetermined'
        record(dict(name=name,eigen_index=int(index),native_eigenvalue=float(w[index]),values=values,
            q100=str(q100),q100_float=q,active_switches_100=switches100,q80_q100_gap=str(gap),valid=bool(valid),
            classification=klass,apparent_negative=bool(w[index]<0 and klass=='positive'),
            native_minus_q100=float(w[index])-q,hv_rayleigh=float(v@hv),hv_norm=float(np.linalg.norm(hv)),
            native_hv_norm=float(np.linalg.norm(H@v)),hv_minus_native_norm=float(np.linalg.norm(hv-H@v)),
            hv_eigen_residual=float(np.linalg.norm(hv-q*v))))
        vectors.append(v);hvs.append(hv)
    return w,np.array(vectors),np.array(hvs)


def rounding_part(kernel,frozen,x0,y,H,R,prior_gradient,record):
    w,V,keep,cut=cv.spectral_split(H,R['pinv_rcond'])
    grad=lambda p:kernel.gradient(p,R['digits'],R['gradient_step'])
    points=[x0];gradients=[];rows=[]
    g=grad(x0);gf=floats(g)
    consistency=float(max(abs(gf-np.asarray(prior_gradient))))
    for k in range(R['newton_steps']+1):
        gf=floats(g);gradients.append(gf);c=V.T@gf;low=V[:,~keep]@c[~keep]
        row=dict(index=k,gradient_inf=inf(gf),gradient_norm=float(np.linalg.norm(gf)),
            low_projection_inf=inf(low) if len(low) else 0.,low_projection_norm=float(np.linalg.norm(low)),
            value_80=str(kernel.scalar(points[-1],R['digits'])))
        if k<R['newton_steps']:
            d,_=cv.newton_step(w,V,keep,gf);row.update(step_norm=float(np.linalg.norm(d)),**cv.step_in_ulps(d,points[-1]))
            with localcontext() as ctx:
                ctx.prec=R['digits'];nxt=[a+binary(float(s)) for a,s in zip(points[-1],d)]
            points.append(nxt)
        rows.append(row);record(row)
        if k<R['newton_steps']:g=grad(points[-1])
    rounded={}
    for name in R['rounded_points']:
        index=int(name[1:]);r=cv.nearest_binary(points[index]);gr=floats(grad(cv.to_decimal(r)))
        _,native=frozen.eval(r);native=native.copy()
        rounded[name]=dict(point=r.tolist(),gradient=gr.tolist(),gradient_inf=inf(gr),gradient_norm=float(np.linalg.norm(gr)),
            native_gradient_inf=inf(native),native_minus_decimal_inf=inf(native-gr),
            changed_from_x0=int(np.count_nonzero(r!=y)),high_precision_gradient_inf=rows[index]['gradient_inf'],
            verdict=cv.rounding_verdict(rows[index]['gradient_inf'],inf(gr),R['gradient_inf_target']))
        record(dict(rounded=name,**{k:v for k,v in rounded[name].items() if k not in ('point','gradient')}))
    return dict(kept=int(keep.sum()),dropped=int((~keep).sum()),cut=cut,eigen_min=float(w[0]),eigen_max=float(w[-1]),
        dropped_eigenvalues=w[~keep].tolist(),floors=cv.rounding_floors(H,y),prior_gradient_max_difference=consistency,
        rows=rows,rounded=rounded,points=[[str(a) for a in p] for p in points]),np.array(gradients)


def main():
    case=os.environ['UAV_R2_CASE'];start=monotonic()
    targets,target,metadata,frozen,y,H=load(case);deadline=start+targets['seconds_per_state']
    kernel=Kernel(metadata,deadline);x0=cv.to_decimal(y)
    _,native=frozen.eval(y);native=native.copy()
    rebuilt,_=h.decomposition.hessian_of_al(frozen,y,targets['hessian_step'])
    prior=json.loads((h.ROOT/target['precise_inner_gradient_check']).read_text())
    log=lambda row:print(json.dumps(row),flush=True)
    result=dict(case=case,variables=len(y),rho=metadata['rho'],status='complete',optimizer_launched=False,
        native_gradient_inf=inf(native),hessian_rebuild_max_difference=float(abs(rebuilt-H).max()),
        hessian_asymmetry=float(abs(H-H.T).max()))
    folder=BASE/'states'/case;folder.mkdir(exist_ok=False);directions=[];arrays={}
    try:
        w,vectors,hvs=curvature_part(kernel,x0,H,targets['curvature'],lambda r:(directions.append(r),log(r)))
        arrays.update(eigenvalues=w,directions=vectors,hv=hvs)
        rounding,gradients=rounding_part(kernel,frozen,x0,y,H,targets['rounding'],prior['gradient_80'],log)
        arrays.update(gradients=gradients);result.update(rounding=rounding)
    except TimeoutError:result['status']='timeout'
    result.update(directions=directions,scalar_evaluations=kernel.calls,seconds=monotonic()-start)
    frozen.close();np.savez_compressed(folder/'arrays.npz',y=y,H=H,native_gradient=native,**arrays)
    (folder/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ['case','status','scalar_evaluations','seconds','hessian_rebuild_max_difference']}),flush=True)


if __name__=='__main__':main()
