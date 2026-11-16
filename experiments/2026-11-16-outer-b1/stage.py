"""The stage loop of 2026-11-15-r2b-coarse/run.py for one stage, with a replaceable inner solver."""
from time import monotonic
import numpy as np


def run_stage(y,lam,mu,rho,stage,frozen_for,inner,assess,state,tol,cap,seconds,on_row=lambda row:None,inner_record=lambda outer:(lambda row:None)):
    """Outer AL exactly as run.py: inner solve, multiplier update, assess, rho rule, pass check. Returns (rows, final, stop)."""
    previous=np.inf;stage_start=monotonic();deadline=stage_start+seconds;stop='outer_limit';rows=[]
    for outer in range(cap):
        if monotonic()>=deadline:
            stop='timeout';break
        context=state(y,lam,mu,rho,stage);f=frozen_for(context)
        result=inner(f,context,y.copy(),deadline,inner_record(outer+1))
        info={k:v for k,v in result.items() if k not in ['y','gradient']}
        if result['status']=='timeout':
            f.close();stop='timeout';break
        y=np.ascontiguousarray(result['y']);value,gradient=f.eval(y)
        np.testing.assert_allclose(result['gradient'],gradient,atol=1e-12,rtol=1e-10)
        lam=lam+rho*f.m.h;mu=np.maximum(0.,mu+rho*f.m.g)
        metrics=assess(f,y,lam,mu)
        common=max(metrics['common_kkt'].values())<=tol;physical=max(metrics['paper_units_kkt'].values())<=1e-6
        passed=common and (stage!=13 or physical)
        violation=max(metrics['common_kkt']['feas'],metrics['common_kkt']['comp'])
        increase=violation>tol and violation>.25*previous and result['gradient_inf']<=1e-6 and not passed
        next_rho=min(1e8,10*rho) if increase else rho
        row=dict(**state(y,lam,mu,rho,stage),outer=outer+1,**metrics,inner=info,rho_next=next_rho,violation=violation,
            previous_violation=None if not np.isfinite(previous) else previous,common_pass=common,physical_pass=physical,stage_pass=passed,
            seconds=monotonic()-stage_start)
        rows.append(row);on_row(row);f.close()
        previous,rho=violation,next_rho
        if passed:
            stop='kkt';break
    context=state(y,lam,mu,rho,stage);f=frozen_for(context);metrics=assess(f,y,lam,mu);f.close()
    common=max(metrics['common_kkt'].values())<=tol;physical=max(metrics['paper_units_kkt'].values())<=1e-6
    final=dict(**context,**metrics,common_pass=common,physical_pass=physical,stage_pass=common and (stage!=13 or physical),
        completed_outer=len(rows),seconds=monotonic()-stage_start,stop=stop)
    return rows,final
