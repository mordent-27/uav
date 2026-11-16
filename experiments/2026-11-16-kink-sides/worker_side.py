"""Part 1: one-sided pieces at the weakly active c30>=0 term of the fixed tau6 point. Evaluation and fixed-H Newton only."""
from decimal import Decimal as D,localcontext
import json
from pathlib import Path
from time import monotonic
import numpy as np
import helpers as h
import kink

BASE=Path(__file__).resolve().parent
cv=kink.lowcurv


def floats(v):return np.array([float(a) for a in v])
def inf(v):return float(max(abs(np.asarray(v,dtype=float))))


def main():
    targets=json.loads((BASE/'targets.json').read_text());S=targets['side'];ctx=S['context'];start=monotonic();deadline=start+S['seconds']
    metadata=json.loads((h.ROOT/ctx['metadata_source']).read_text())['metadata']
    prior=json.loads((h.ROOT/ctx['result']).read_text());data=np.load(h.ROOT/ctx['samples'])
    y=data['y'].copy();H=data['H'].copy();jac=data['jac'].copy();assert len(data['h0'])==S['equalities'];data.close()
    frozen=h.stage4.Frozen(dict(json.loads((h.ROOT/prior['source']).read_text()),y=y.tolist()))
    index=S['index'];a=jac[S['equalities']+index];rho=float(metadata['rho']);digits=S['digits'];step=S['gradient_step']
    calls=dict(primal=0)
    def primal(p,d=digits):
        if monotonic()>=deadline:raise TimeoutError()
        calls['primal']+=1;return kink.reference.evaluate(p,metadata,d)
    def values(mode,d=digits):return [lambda q:kink.piece_al(q,metadata,d,index,mode),lambda q:kink.piece_al(q,metadata,d)]
    def gradients(point,mode,d=digits,s=step):
        piece,true=kink.central_pair(lambda q:primal(q,d),values(mode,d),point,d,s,deadline);return floats(piece),floats(true)
    x0=cv.to_decimal(y);p0=primal(x0);s0=kink.shifted_values(p0,metadata,digits);active0=[v>0 for v in s0]
    def describe(point,mode):
        p=primal(point);s=kink.shifted_values(p,metadata,digits)
        others=[i for i in range(len(s)) if i!=index and (s[i]>0)!=active0[i]]
        return dict(s=str(s[index]),s_float=float(s[index]),other_switches=len(others),other_switch_indices=others,
            piece_value=str(kink.piece_al(p,metadata,digits,index,mode)),true_value=str(kink.piece_al(p,metadata,digits)))
    result=dict(case=ctx['case'],index=index,rho=rho,s0=str(s0[index]),mu=metadata['mu'][index],
        active_at_x0=bool(active0[index]),constraint_gradient_norm=float(np.linalg.norm(a)),status='complete',optimizer_launched=False,pieces={})
    arrays={}
    try:
        for mode in S['modes']:
            Hp=H if mode=='inactive' else H+rho*np.outer(a,a);w,V,keep,cut=cv.spectral_split(Hp,S['pinv_rcond'])
            x=x0;rows=[];piece_g=true_g=None
            for k in range(S['newton_steps']+1):
                piece_g,true_g=gradients(x,mode);row=dict(index=k,piece_gradient_inf=inf(piece_g),true_gradient_inf=inf(true_g),
                    piece_gradient_norm=float(np.linalg.norm(piece_g)),**describe(x,mode))
                if k<S['newton_steps']:
                    d,_=cv.newton_step(w,V,keep,piece_g);row.update(step_norm=float(np.linalg.norm(d)),**cv.step_in_ulps(d,x))
                    with localcontext() as c:
                        c.prec=digits;x=[u+kink.binary(float(v)) for u,v in zip(x,d)]
                rows.append(row);print(json.dumps(dict(mode=mode,**{k_:v for k_,v in row.items() if k_!='other_switch_indices'})),flush=True)
            last=rows[-1];verdict,reasons=kink.piece_verdict(last['piece_gradient_inf'],mode,D(last['s']),last['other_switches'],S['gradient_inf_target'])
            result['pieces'][mode]=dict(kept=int(keep.sum()),dropped=int((~keep).sum()),cut=cut,eigen_min=float(w[0]),eigen_max=float(w[-1]),
                rows=rows,verdict=verdict,reasons=reasons,point=[str(v) for v in x])
            arrays[f'{mode}_piece_gradient']=piece_g;arrays[f'{mode}_true_gradient']=true_g
        valid=[m for m in S['modes'] if result['pieces'][m]['verdict']=='valid']
        result['found']=bool(valid)
        if valid:
            mode=min(valid,key=lambda m:D(result['pieces'][m]['rows'][-1]['true_value']));result['chosen']=mode
            star=[D(v) for v in result['pieces'][mode]['point']];Hp=H if mode=='inactive' else H+rho*np.outer(a,a)
            star_true=result['pieces'][mode]['rows'][-1]['true_gradient_inf']
            rounded=cv.nearest_binary(star);_,gr=gradients(cv.to_decimal(rounded),mode)
            lattice,kvec,info=kink.lattice_search(gr,Hp,rounded,**S['lattice']);_,gl=gradients(cv.to_decimal(lattice),mode)
            out={}
            for name,point,g in [('rounded',rounded,gr),('lattice',lattice,gl)]:
                _,native=frozen.eval(point);native=native.copy()
                out[name]=dict(point=point.tolist(),gradient_inf=inf(g),gradient_norm=float(np.linalg.norm(g)),native_gradient_inf=inf(native),
                    native_minus_decimal_inf=inf(native-g),changed_from_x0=int(np.count_nonzero(point!=y)),**describe(cv.to_decimal(point),mode))
                arrays[f'{name}_true_gradient']=g
            out['lattice'].update(search=info,k=kvec.tolist())
            out['verdict']=cv.rounding_verdict(star_true,out['rounded']['gradient_inf'],S['gradient_inf_target'])
            out['lattice_reaches_target']=out['lattice']['gradient_inf']<=S['gradient_inf_target']
            result['binary64']=out;print(json.dumps(dict(verdict=out['verdict'],rounded=out['rounded']['gradient_inf'],lattice=out['lattice']['gradient_inf'],search=info)),flush=True)
    except TimeoutError:result['status']='timeout'
    result.update(primal_evaluations=calls['primal'],seconds=monotonic()-start);frozen.close()
    folder=BASE/'side';(folder/'result.json').write_text(json.dumps(result,indent=2)+'\n');np.savez_compressed(folder/'arrays.npz',**arrays)
    print(json.dumps({k:result.get(k) for k in ['status','found','chosen','primal_evaluations','seconds']}),flush=True)


if __name__=='__main__':main()
