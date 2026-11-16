import importlib.util
import json
import os
from pathlib import Path
import sys
from time import monotonic
import numpy as np
import helpers as h

sys.path.insert(0,str(h.ROOT/'scripts'))
import trust_region

BASE=Path(__file__).resolve().parent


def main():
    case=os.environ['UAV_R2_CASE']
    target=next(t for t in json.loads((BASE/'targets.json').read_text())['contexts'] if t['case']==case)
    source=h.ROOT/target['source'];raw=source.read_bytes();state=json.loads(raw)
    frozen=h.stage4.Frozen(state);y=np.array(state['y'])
    initial_value,initial_gradient=frozen.eval(y);initial_gradient=initial_gradient.copy()
    folder=BASE/'inner'/f'{case}-boundary-fixed';folder.mkdir(exist_ok=False)
    spec=importlib.util.spec_from_file_location('original_dense_solver',h.ROOT/'experiments/2026-11-15-decomposed-follow/newton.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    norms=[]
    with (folder/'tr-steps.jsonl').open('x') as steps, (folder/'trace.jsonl').open('x') as trace:
        def checked_step(w,V,g,delta):
            p,boundary=trust_region.tr_step(w,V,g,delta)
            norm=float(np.linalg.norm(p));ratio=norm/delta if delta else 0.
            assert norm<=delta*(1+1e-12)+1e-30,(norm,delta)
            norms.append(ratio)
            steps.write(json.dumps(dict(delta=float(delta),step=p.tolist(),norm=norm,
                norm_over_radius=ratio,boundary=bool(boundary)))+'\n')
            return p,boundary
        # The original loop is unchanged; substitution is local to this child process.
        h.stage4.old.newton.tr_step=checked_step
        result=module.solve(frozen,y.copy(),monotonic()+30.,lambda r:trace.write(json.dumps(r)+'\n'))
    result['y']=result['y'].tolist();result['gradient']=result['gradient'].tolist()
    value,gradient=frozen.eval(np.array(result['y']))
    np.testing.assert_allclose(value,result['value'],atol=1e-9,rtol=1e-10)
    np.testing.assert_allclose(gradient,result['gradient'],atol=1e-9,rtol=1e-9)
    result.update(case=case,method='boundary-fixed',source=target['source'],source_sha256=target['sha256'],
        rho=state['rho'],initial_value=float(initial_value),initial_gradient_inf=float(max(abs(initial_gradient))),
        al_decrease=float(initial_value-value),fixed_multiplier_and_rho=True,
        tr_step_calls=len(norms),max_step_norm_over_radius=max(norms,default=0.),
        final_metrics=frozen.m.metrics(np.array(result['y']),np.array(state['lam']),np.array(state['mu'])))
    frozen.close();assert source.read_bytes()==raw
    (folder/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ['case','status','accepted','gradient_inf','seconds','max_step_norm_over_radius']}),flush=True)


if __name__=='__main__':main()
