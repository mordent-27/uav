"""Replay the stuck TR iteration at one saved final point. Evaluation only; the point never moves."""
from decimal import localcontext
import json
import os
from pathlib import Path
from time import monotonic
import numpy as np
import helpers as h
import replay

BASE=Path(__file__).resolve().parent
kink=replay.onesided.fixh.kink


def native_metadata(frozen,state,tasks=None):
    """Decimal metadata from the native model; tasks=None keeps f.m.source (first run), else full-precision tasks (addendum)."""
    m=frozen.m;ns=m.stamps-1
    if not (np.all(m.ratio==1.) and np.all(m.wh[ns:]==1.)):return None
    ph=dict(m.source['phys']);ph.update(range=ph['v_d']/ph['zeta'],sigma=(ph['e_max']-ph['e_th'])/ph['kappa'],span=ph['e_max']-ph['e_th'])
    return dict(phys=ph,scale=m.scale.tolist(),wh=m.wh.tolist(),wg=m.wg.tolist(),n_segments=ns,lam=state['lam'],mu=state['mu'],rho=state['rho'],
        eps=state['eps'],p=state['p'],smoothing_delta=1e-3,instance=m.source['instance'] if tasks is None else dict(m.source['instance'],tasks=tasks))


def main():
    name=os.environ['UAV_STUCK_TARGET'];targets=json.loads((BASE/'targets.json').read_text());T=next(t for t in targets['targets'] if t['name']==name)
    start=monotonic();deadline=start+targets['seconds']
    state=json.loads((h.ROOT/T['checkpoint']).read_text());frozen=h.stage4.Frozen(state)
    solved=json.loads((h.ROOT/T['result']).read_text());trace=[json.loads(s) for s in (h.ROOT/T['trace']).read_text().splitlines()]
    y=np.array(solved['y']);delta=trace[-1]['delta'];assert solved['status']=='stuck'
    rule=replay.onesided.switch_rule(frozen.m.scale.tolist(),dict(frozen.m.source['phys']),frozen.m.stamps-1,targets['hessian_step'])
    if T['method']=='old':H,_=h.decomposition.hessian_of_al(frozen,y,targets['hessian_step'])
    else:H,_=replay.onesided.hessian_onesided(h.decomposition.hessian_of_al,frozen,y,targets['hessian_step'],None,rule,dict(builds=0,triggered=0,max_coordinates=0))
    def evaluate(point):
        if monotonic()>=deadline:raise TimeoutError()
        v,g=frozen.eval(point);return v,np.array(g,dtype=float).copy()
    f,g=evaluate(y);np.testing.assert_allclose(f,solved['value'],rtol=0,atol=0);stable0,_=frozen.eval(y,stable=True)
    tasks=None;out=BASE/'replays'
    if os.environ.get('UAV_STUCK_FULL_TASKS'):
        rows_=[json.loads(x) for x in (h.ROOT/targets['addendum']['full_precision_tasks']).read_text().splitlines()]
        tasks=next(r['tasks'] for r in rows_ if r['case']==T['case']);out=BASE/'replays-decimal'
        np.testing.assert_allclose(tasks,frozen.m.source['instance']['tasks'],atol=5.1e-10,rtol=0.)
    if os.environ.get('UAV_STUCK_OUT_DIR'):out=Path(os.environ['UAV_STUCK_OUT_DIR'])  # verification only; default unchanged
    metadata=native_metadata(frozen,state,tasks);digits=int(os.environ.get('UAV_STUCK_DIGITS',targets['digits']));decimal=None;gap=None
    if metadata is not None:
        value=lambda p:kink.piece_al(kink.reference.evaluate(kink.lowcurv.to_decimal(p),metadata,digits),metadata,digits)
        decimal0=value(y);gap=replay.relative_gap(float(decimal0),f);decimal=value if gap<=targets['decimal_value_gap'] else None
    def extra(point):
        s,_=frozen.eval(point,stable=True);out=dict(stable_decrease=float(stable0)-float(s))
        if decimal is not None:
            with localcontext() as c:
                c.prec=digits;out['decimal_decrease']=float(decimal0-decimal(point))
        return out
    rows=replay.replay(evaluate,H,y,f,g,delta,extra,targets['max_trials'])
    key='decimal_decrease' if decimal is not None else 'stable_decrease'
    for r in rows:r['precise_ratio']=replay.precise_ratio(r[key],r['prediction'])
    w=np.linalg.eigvalsh(H)
    result=dict(name=name,case=T['case'],method=T['method'],value=f,value_ulp=float(np.spacing(abs(f))),fallback_threshold=1e-13*max(1.,abs(f)),
        gradient_inf=float(abs(g).max()),gradient_norm=float(np.linalg.norm(g)),start_radius=delta,eigen_min=float(w[0]),eigen_max=float(w[-1]),
        decimal_available=decimal is not None,decimal_value_gap=gap,precise_key=key,trials=len(rows),rows=rows,
        verdict=replay.verdict(rows),fallback_trials=sum(r['fallback'] for r in rows),nonpositive_predictions=sum(r['prediction']<=0 for r in rows),
        precise_accepting_trials=sum(r['precise_ratio'] is not None and r['precise_ratio']>1e-4 for r in rows),
        rule_at_point=sorted(rule(y)),seconds=monotonic()-start,optimizer_launched=False)
    result['full_precision_tasks']=tasks is not None
    frozen.close();(out/f'{name}.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ['name','verdict','trials','fallback_trials','precise_accepting_trials','decimal_available','decimal_value_gap','value','seconds']}),flush=True)


if __name__=='__main__':main()
