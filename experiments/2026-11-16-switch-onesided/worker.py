"""One frozen-AL inner solve from a saved checkpoint with the old or the one-sided Hessian. Native evaluation only."""
import hashlib
import json
import os
from pathlib import Path
from time import monotonic
import numpy as np
import helpers as h
import onesided

BASE=Path(__file__).resolve().parent


def load(case):
    targets=json.loads((BASE/'targets.json').read_text());row=next(r for r in targets['states'] if r['case']==case)
    state=json.loads((h.ROOT/row['checkpoint']).read_text());frozen=h.stage4.Frozen(state)
    rule=onesided.switch_rule(frozen.m.scale.tolist(),dict(frozen.m.source['phys']),frozen.m.stamps-1,targets['hessian_step'])
    return targets,row,state,frozen,rule


def hessian_function(method,frozen,rule,step,stats):
    if method=='old':
        def hessian(point,counts):
            stats['builds']+=1;return h.decomposition.hessian_of_al(frozen,point,step,counts)[0]
    else:
        assert method=='onesided'
        def hessian(point,counts):return onesided.hessian_onesided(h.decomposition.hessian_of_al,frozen,point,step,counts,rule,stats)[0]
    return hessian


def digest(H):return hashlib.sha256(np.ascontiguousarray(H).tobytes()).hexdigest()


def main():
    case=os.environ['UAV_R2_CASE'];method=os.environ['UAV_HESSIAN_METHOD'];targets,row,state,frozen,rule=load(case)
    y0=np.array(state['y']);folder=BASE/'inner'/f'{case}-{method}';folder.mkdir(parents=True,exist_ok=False)
    stats=dict(builds=0,triggered=0,max_coordinates=0)
    def evaluate(point,deadline):
        if monotonic()>=deadline:raise TimeoutError()
        value,gradient=frozen.eval(point);return value,np.array(gradient,dtype=float).copy(),None
    hessian=hessian_function(method,frozen,rule,targets['hessian_step'],stats)
    start=monotonic()
    with (folder/'trace.jsonl').open('x') as trace:
        result=onesided.inner.solve(evaluate,hessian,y0.copy(),start+targets['seconds'],lambda r:trace.write(json.dumps(r)+'\n'))
    y=np.array(result['y']);stable,_=frozen.eval(y,stable=True);_,g0=frozen.eval(y0);g0=np.array(g0).copy()
    final_old,_=h.decomposition.hessian_of_al(frozen,y,targets['hessian_step'])
    final_new,_=onesided.hessian_onesided(h.decomposition.hessian_of_al,frozen,y,targets['hessian_step'],None,rule,dict(builds=0,triggered=0,max_coordinates=0))
    result.update(case=case,method=method,rho=state['rho'],initial_gradient_inf=float(abs(g0).max()),
        final_gradient_norm=float(np.linalg.norm(result['gradient'])),stable_al_change=stable,al_decrease=-stable,
        hessian_stats=stats,rule_at_start=sorted(rule(y0)),rule_at_end=sorted(rule(y)),
        final_old_hessian_sha256=digest(final_old),final_onesided_hessian_sha256=digest(final_new),frozen_al_only=True,optimizer='frozen_inner_tr')
    frozen.close();(folder/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ['case','method','status','accepted','iterations','gradient_inf','al_decrease','seconds','hessian_stats']}),flush=True)


if __name__=='__main__':main()
