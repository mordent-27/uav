import hashlib
import json
import os
from pathlib import Path
import numpy as np
import helpers as h
from ledger import decompose

BASE=Path(__file__).resolve().parent


def main():
    targets=json.loads((BASE/'targets.json').read_text());case=os.environ['UAV_R2_CASE']
    target=next(t for t in targets['contexts'] if t['case']==case)
    state=json.loads((h.ROOT/target['source']).read_text())
    final=json.loads((h.ROOT/target['point_source']).read_text())
    state=dict(state,y=final['y']);f=h.stage4.Frozen(state);y=np.array(state['y'])
    value,gradient=f.eval(y);gradient=gradient.copy()
    np.testing.assert_allclose(gradient,final['gradient'],atol=1e-10,rtol=1e-9)
    stable,sg=f.eval(y,stable=True);assert stable==0.
    np.testing.assert_allclose(sg,gradient,atol=1e-10,rtol=1e-9)
    H,_=h.decomposition.hessian_of_al(f,y,targets['hessian_step']);eigen,V=np.linalg.eigh(H)
    step=json.loads((h.ROOT/target['step_source']).read_text().splitlines()[-1])['step']
    rng=np.random.default_rng(targets['random_seed_base']+h.TAU)
    directions=np.array([-gradient,np.array(step),rng.normal(size=len(y)),V[:,-1],V[:,0]])
    directions/=np.linalg.norm(directions,axis=1)[:,None]
    f.eval(y);h0,g0=f.m.h.copy(),f.m.g.copy();jac=f.m.jacobian(y)
    shifted=f.mu+f.rho*g0;rows=[];points=[];gradients=[];hs=[];gs=[];values=[];stable_values=[]
    for name,v in zip(targets['directions'],directions):
        slope=float(gradient@v);curvature=float(v@H@v)
        for width in targets['widths']:
            observed=[]
            for sign in [1,-1]:
                point=y+sign*width*v;delta=point-y
                val,grad=f.eval(point);grad=grad.copy();hn,gn=f.m.h.copy(),f.m.g.copy()
                sv,sg=f.eval(point,stable=True)
                np.testing.assert_allclose(sg,grad,atol=1e-10,rtol=1e-9)
                parts=decompose(delta,h0,g0,hn,gn,f.lam,f.mu,f.rho,f.gf,jac)
                np.testing.assert_allclose(parts['stable'],sv,atol=1e-22,rtol=1e-10)
                model=float(gradient@delta+.5*delta@H@delta)
                item=dict(point_index=len(points),value=float(val),stable=float(sv),
                    represented_norm=float(np.linalg.norm(delta)),represented_projection=float(v@delta),
                    unchanged_coordinates=int(np.count_nonzero(delta==0)),
                    active_switches=int(np.count_nonzero((f.mu+f.rho*gn>0)!=(shifted>0))),
                    model=model,model_error=float(sv-model),ledger=parts)
                observed.append((item,grad))
                points.append(point);gradients.append(grad);hs.append(hn);gs.append(gn);values.append(val);stable_values.append(sv)
            plus,gp=observed[0];minus,gm=observed[1]
            rows.append(dict(direction=name,width=width,gradient_slope=slope,model_curvature=curvature,
                ordinary_fd_slope=float((plus['value']-minus['value'])/(2*width)),
                stable_fd_slope=float((plus['stable']-minus['stable'])/(2*width)),
                ordinary_fd_curvature=float((plus['value']-value+minus['value']-value)/width**2),
                stable_fd_curvature=float((plus['stable']+minus['stable'])/width**2),
                gradient_fd_curvature=float(v@(gp-gm)/(2*width)),plus=plus,minus=minus))
    folder=BASE/'states'/case;folder.mkdir(exist_ok=False)
    np.savez_compressed(folder/'samples.npz',y=y,gradient=gradient,H=H,jac=jac,h0=h0,g0=g0,
        directions=directions,points=points,gradients=gradients,hs=hs,gs=gs,values=values,stable_values=stable_values)
    result=dict(case=case,variables=len(y),rho=f.rho,source=target['source'],source_sha256=target['sha256'],
        point_source=target['point_source'],point_sha256=target['point_sha256'],initial_value=float(value),
        gradient_inf=float(max(abs(gradient))),gradient_norm=float(np.linalg.norm(gradient)),
        n_segments=f.m.stamps-1,tasks=h.TAU,eigen_min=float(eigen[0]),eigen_max=float(eigen[-1]),
        samples=len(points),rows=rows,optimizer_launched=False)
    f.close();(folder/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ['case','rho','samples','gradient_inf','eigen_min','eigen_max']}),flush=True)


if __name__=='__main__':main()
