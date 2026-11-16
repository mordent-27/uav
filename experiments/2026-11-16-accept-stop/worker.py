"""One frozen-AL inner solve from a saved checkpoint with acceptance A/B and stop 0/1. Gradient and Hessian are native."""
from decimal import localcontext
import importlib.util
import json
import os
from pathlib import Path
import sys
from time import monotonic
import numpy as np
import helpers as h
import loop

BASE=Path(__file__).resolve().parent


def _load(name,path):
    if name in sys.modules:return sys.modules[name]
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module;spec.loader.exec_module(module);return module


kink=_load('kink',BASE.parent/'2026-11-16-kink-sides/kink.py')


def native_metadata(frozen,state,tasks):
    """Decimal metadata for the problem the native model solves, with full-precision task coordinates (as stuck-trials)."""
    m=frozen.m;ns=m.stamps-1
    assert np.all(m.ratio==1.) and np.all(m.wh[ns:]==1.)
    np.testing.assert_allclose(tasks,m.source['instance']['tasks'],atol=5.1e-10,rtol=0.)
    ph=dict(m.source['phys']);ph.update(range=ph['v_d']/ph['zeta'],sigma=(ph['e_max']-ph['e_th'])/ph['kappa'],span=ph['e_max']-ph['e_th'])
    return dict(phys=ph,scale=m.scale.tolist(),wh=m.wh.tolist(),wg=m.wg.tolist(),n_segments=ns,lam=state['lam'],mu=state['mu'],rho=state['rho'],
        eps=state['eps'],p=state['p'],smoothing_delta=1e-3,instance=dict(m.source['instance'],tasks=tasks))


def setup(case):
    targets=json.loads((BASE/'targets.json').read_text());row=next(r for r in targets['states'] if r['case']==case)
    state=json.loads((h.ROOT/row['checkpoint']).read_text());frozen=h.stage4.Frozen(state)
    tasks=next(json.loads(s)['tasks'] for s in (h.ROOT/row['full_precision_tasks']).read_text().splitlines() if json.loads(s)['case']==case)
    metadata=native_metadata(frozen,state,tasks);digits=targets['digits']
    def exact(point):return kink.piece_al(kink.reference.evaluate(kink.lowcurv.to_decimal(point),metadata,digits),metadata,digits)
    def decimal_gradient(point,d=digits,step=targets['gradient_step']):
        g,=kink.central_pair(lambda q:kink.reference.evaluate(q,metadata,d),[lambda q:kink.piece_al(q,metadata,d)],kink.lowcurv.to_decimal(point),d,step)
        return np.array([float(v) for v in g])
    return targets,row,state,frozen,metadata,exact,decimal_gradient


def main():
    case=os.environ['UAV_R2_CASE'];arm=os.environ['UAV_ARM'];assert arm in ('A0','B0','A1','B1')
    targets,row,state,frozen,metadata,exact,decimal_gradient=setup(case)
    y0=np.array(state['y']);folder=BASE/'inner'/f'{case}-{arm}';folder.mkdir(parents=True,exist_ok=False)
    f0,_=frozen.eval(y0);e0=exact(y0);gap=abs(float(e0)-f0)/max(1.,abs(f0));use_exact=arm[0]=='B'
    if use_exact:assert gap<=targets['decimal_value_gap'],gap
    def evaluate(point,deadline):
        if monotonic()>=deadline:raise TimeoutError()
        v,g=frozen.eval(point);return v,np.array(g,dtype=float).copy()
    def hessian(point,counts):return h.decomposition.hessian_of_al(frozen,point,targets['hessian_step'],counts)[0]
    start=monotonic()
    with (folder/'trace.jsonl').open('x') as trace:
        result=loop.solve(evaluate,hessian,y0.copy(),start+targets['seconds'],lambda r:trace.write(json.dumps(r)+'\n'),
            exact_value=exact if use_exact else None,floor_stop=arm[1]=='1',tol=targets['tolerance'],factor=targets['floor_factor'])
    y=np.array(result['y']);gd=decimal_gradient(y);e1=exact(y)
    with localcontext() as c:
        c.prec=targets['digits'];decrease=float(e0-e1)
    result.update(case=case,arm=arm,rho=state['rho'],decimal_value_gap_at_start=gap,decimal_gradient_inf=float(abs(gd).max()),
        decimal_gradient_norm=float(np.linalg.norm(gd)),decimal_al_decrease=decrease,final_floor=loop.floor_estimate(h.decomposition.hessian_of_al(frozen,y,targets['hessian_step'])[0],y),
        frozen_al_only=True,outer_solver_launched=False)
    frozen.close();(folder/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ['case','arm','status','accepted','iterations','gradient_inf','decimal_gradient_inf','decimal_al_decrease','seconds','decimal_calls','stop']}),flush=True)


if __name__=='__main__':main()
