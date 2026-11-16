"""Part 1: rebuild the straddling Hessian columns at the fixed tau6 point, check curvature, then fixed-H Newton. No optimizer."""
from decimal import Decimal as D,localcontext
import json
from pathlib import Path
from time import monotonic
import numpy as np
import helpers as h
import fixh

BASE=Path(__file__).resolve().parent
kink=fixh.kink;cv=fixh.lowcurv


def floats(v):return np.array([float(a) for a in v])
def inf(v):return float(max(abs(np.asarray(v,dtype=float))))


def main():
    targets=json.loads((BASE/'targets.json').read_text());P=targets['fix'];ctx=P['context'];start=monotonic();deadline=start+P['seconds']
    metadata=json.loads((h.ROOT/ctx['metadata_source']).read_text())['metadata']
    prior=json.loads((h.ROOT/ctx['result']).read_text());data=np.load(h.ROOT/ctx['samples'])
    y=data['y'].copy();H_old=data['H'].copy();data.close();ns=metadata['n_segments']
    frozen=h.stage4.Frozen(dict(json.loads((h.ROOT/prior['source']).read_text()),y=y.tolist()))
    side=json.loads((h.ROOT/P['previous_side_result']).read_text())
    g_post=np.load(h.ROOT/P['previous_side_arrays'])['inactive_piece_gradient']
    calls=dict(primal=0)
    def primal(p,d):
        if monotonic()>=deadline:raise TimeoutError()
        calls['primal']+=1;return kink.reference.evaluate(p,metadata,d)
    def scalar(p,d):return kink.piece_al(primal(p,d),metadata,d)
    def gradient(p,d=P['digits'],s=P['gradient_step']):
        g,=kink.central_pair(lambda q:primal(q,d),[lambda q:kink.piece_al(q,metadata,d)],p,d,s,deadline);return g
    def curvature(x,v):
        plus,minus=cv.shifted(x,v,P['curvature_width'],P['curvature_digits']);d=P['curvature_digits']
        return float(cv.second_quotient(scalar(plus,d),scalar(x,d),scalar(minus,d),P['curvature_width'],d))
    def describe(x,active0):
        pr=primal(x,P['digits']);s=kink.shifted_values(pr,metadata,P['digits'])
        rows=fixh.margins(x,metadata['scale'],metadata['phys'],ns)
        m17=next((float(r['margin']) for r in rows if r['segment']==P['segment']),None)
        return dict(segment_margin=m17,c30_s=float(s[P['c30_index']]),other_switches=sum((v>0)!=a for i,(v,a) in enumerate(zip(s,active0)) if i!=P['c30_index']))
    x0=cv.to_decimal(y);result=dict(case=ctx['case'],status='complete',optimizer_launched=False)
    try:
        rows=fixh.margins(y,metadata['scale'],metadata['phys'],ns);J,reasons=fixh.straddling(rows,metadata['scale'],metadata['phys'],ns,P['old_hessian_step'])
        result.update(straddling=reasons,nearest_margins=[dict(segment=r['segment'],margin=float(r['margin'])) for r in sorted(rows,key=lambda r:abs(r['margin']))[:3]])
        columns=[]
        for j in J:
            e=np.zeros(len(y));e[j]=1.;plus,minus=cv.shifted(x0,e,P['column_width'],P['digits'])
            gp,gm=gradient(plus,s=P['column_gradient_step']),gradient(minus,s=P['column_gradient_step'])
            with localcontext() as c:
                c.prec=P['digits'];t=D(P['column_width']);columns.append(floats([(a-b)/(2*t) for a,b in zip(gp,gm)]))
        H_fix=fixh.replace_columns(H_old,J,columns)
        result.update(replaced=len(J),column_change=[dict(index=j,old_diag=float(H_old[j,j]),new_diag=float(H_fix[j,j]),
            column_difference_norm=float(np.linalg.norm(H_fix[:,j]-H_old[:,j]))) for j in J])
        w,V,keep,cut=cv.spectral_split(H_fix,P['pinv_rcond'])
        g0=floats(gradient(x0));d_fix,_=cv.newton_step(w,V,keep,g0)
        w_old,V_old,keep_old,_=cv.spectral_split(H_old,P['pinv_rcond']);d_post,_=cv.newton_step(w_old,V_old,keep_old,g_post)
        gate_rows=[]
        for name,d in [('previous_posthoc_direction',d_post),('fix_newton_direction_at_x0',d_fix)]:
            v=d/np.linalg.norm(d);q=curvature(x0,v)
            gate_rows.append(dict(direction=name,decimal=q,old=float(v@H_old@v),fix=float(v@H_fix@v),ratio_old=q/float(v@H_old@v),ratio_fix=q/float(v@H_fix@v)))
        passed=fixh.gate([r['ratio_fix'] for r in gate_rows],*P['gate'])
        result.update(gate=gate_rows,gate_passed=passed,kept=int(keep.sum()),dropped=int((~keep).sum()))
        print(json.dumps(dict(J=reasons,gate=gate_rows,passed=passed)),flush=True)
        if passed:
            active0=[v>0 for v in kink.shifted_values(primal(x0,P['digits']),metadata,P['digits'])]
            x=x0;g=g0;path=[];points=[x0];star=None
            for k in range(P['newton_steps']+1):
                row=dict(index=k,gradient_inf=inf(g),gradient_norm=float(np.linalg.norm(g)),**describe(x,active0))
                if star is None and k>=1 and row['gradient_inf']<=P['gradient_inf_target']:star=k
                if k<P['newton_steps']:
                    d,_=cv.newton_step(w,V,keep,g);v=d/np.linalg.norm(d);q=curvature(x,v)
                    row.update(step_norm=float(np.linalg.norm(d)),step_ratio_fix=q/float(v@H_fix@v),**cv.step_in_ulps(d,x))
                    with localcontext() as c:
                        c.prec=P['digits'];x=[a+kink.binary(float(b)) for a,b in zip(x,d)]
                    points.append(x)
                path.append(row);print(json.dumps(row),flush=True)
                if k<P['newton_steps']:g=floats(gradient(x))
            result.update(newton=path,found=star is not None,first_reaching=star,points=[[str(a) for a in p] for p in points])
            if star is not None:
                xstar=points[star];rounded=cv.nearest_binary(xstar);gr=floats(gradient(cv.to_decimal(rounded)))
                lattice,kvec,info=kink.lattice_search(gr,H_fix,rounded,**P['lattice']);gl=floats(gradient(cv.to_decimal(lattice)))
                out={}
                for name,point,gg in [('rounded',rounded,gr),('lattice',lattice,gl)]:
                    _,native=frozen.eval(point);native=native.copy()
                    out[name]=dict(point=point.tolist(),gradient_inf=inf(gg),gradient_norm=float(np.linalg.norm(gg)),native_gradient_inf=inf(native),
                        native_minus_decimal_inf=inf(native-gg),changed_from_x0=int(np.count_nonzero(point!=y)),**describe(cv.to_decimal(point),active0))
                out['lattice'].update(search=info,k=kvec.tolist())
                out['verdict']=cv.rounding_verdict(path[star]['gradient_inf'],out['rounded']['gradient_inf'],P['gradient_inf_target'])
                out['lattice_reaches_target']=out['lattice']['gradient_inf']<=P['gradient_inf_target']
                result['binary64']=out;print(json.dumps(dict(verdict=out['verdict'],rounded=out['rounded']['gradient_inf'],lattice=out['lattice']['gradient_inf'],search=info)),flush=True)
        result.update(status='complete')
    except TimeoutError:result['status']='timeout'
    result.update(primal_evaluations=calls['primal'],seconds=monotonic()-start);frozen.close()
    (BASE/'fix'/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    if 'H_fix' in locals():np.savez_compressed(BASE/'fix'/'arrays.npz',H_fix=H_fix,J=np.array(J),columns=np.array(columns),g0=g0)
    print(json.dumps({k:result.get(k) for k in ['status','gate_passed','found','first_reaching','primal_evaluations','seconds']}),flush=True)


if __name__=='__main__':main()
