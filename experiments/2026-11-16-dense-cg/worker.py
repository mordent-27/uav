import hashlib
import json
import os
from pathlib import Path
from time import monotonic
import numpy as np
import helpers as h
import inner_cg

BASE=Path(__file__).resolve().parent


class DenseCurvature:
    counts=dict(gradient_calls=0,jacobian_calls=0)
    def __init__(self,frozen,y):
        self.H,_=h.decomposition.hessian_of_al(frozen,y,1e-7,self.counts)
    def matvec(self,v):return self.H@v


def main():
    case=os.environ['UAV_R2_CASE']
    target=next(t for t in json.loads((BASE/'targets.json').read_text())['contexts'] if t['case']==case)
    source=h.ROOT/target['source'];raw=source.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==target['sha256']
    state=json.loads(raw);f=h.stage4.Frozen(state);y=np.array(state['y'])
    initial_value,initial_gradient=f.eval(y);initial_gradient=initial_gradient.copy()
    folder=BASE/'inner'/f'{case}-dense-cg';folder.mkdir(exist_ok=False)
    H,_=h.decomposition.hessian_of_al(f,y,1e-7)
    prior=h.ROOT/'experiments/2026-11-16-hvp-high-rho/states'/f'{case}-stage13/vectors.npz'
    with np.load(prior) as data:np.testing.assert_allclose(H,data['H'],atol=1e-9,rtol=1e-9)
    w,V=np.linalg.eigh(H)
    old_step,old_boundary=h.stage4.old.newton.tr_step(w,V,initial_gradient,1.)
    cg_step,cg_boundary,cg_iterations,cg_reason=inner_cg.cg_step(lambda v:H@v,initial_gradient,1.)
    first={}
    for method,step,boundary in [('dense_eigen',old_step,old_boundary),('dense_cg',cg_step,cg_boundary)]:
        first[method]=dict(step_norm=float(np.linalg.norm(step)),boundary=bool(boundary),
            predicted_decrease=-float(initial_gradient@step+.5*step@H@step),
            model_gradient_norm=float(np.linalg.norm(initial_gradient+H@step)))
    first.update(cg_iterations=cg_iterations,cg_reason=cg_reason,min_eigenvalue=float(w[0]),max_eigenvalue=float(w[-1]))
    (folder/'first-step.json').write_text(json.dumps(first,indent=2)+'\n')
    np.savez_compressed(folder/'first-step.npz',H=H,g=initial_gradient,old_step=old_step,cg_step=cg_step)
    inner_cg.DirectionalCurvature=DenseCurvature
    with (folder/'trace.jsonl').open('x') as log:
        result=inner_cg.solve(f,y.copy(),monotonic()+30.,lambda r:log.write(json.dumps(r)+'\n'))
    result['y']=result['y'].tolist();result['gradient']=result['gradient'].tolist()
    result['hessian_gradient_calls']=DenseCurvature.counts['gradient_calls']
    result['jacobian_calls']=DenseCurvature.counts['jacobian_calls']
    result['dense_matvec_queries']=result.pop('hvp_queries')
    value,gradient=f.eval(np.array(result['y']))
    np.testing.assert_allclose(value,result['value'],atol=1e-9,rtol=1e-10)
    np.testing.assert_allclose(gradient,result['gradient'],atol=1e-9,rtol=1e-9)
    result.update(case=case,method='dense-cg',source=target['source'],source_sha256=target['sha256'],
        rho=state['rho'],initial_value=float(initial_value),initial_gradient_inf=float(max(abs(initial_gradient))),
        al_decrease=float(initial_value-value),fixed_multiplier_and_rho=True,
        final_metrics=f.m.metrics(np.array(result['y']),np.array(state['lam']),np.array(state['mu'])))
    f.close();assert source.read_bytes()==raw
    (folder/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ['case','method','status','accepted','gradient_inf','al_decrease','seconds']}),flush=True)


if __name__=='__main__':main()
