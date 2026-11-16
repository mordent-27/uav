"""One saved input-NLP replay, observed first iterate, one bound_push factor."""
import copy
import hashlib
import json
import os
from pathlib import Path
from time import monotonic
import casadi as ca
import numpy as np
import helpers as h
from observe import FirstPoint,violation

BASE=Path(__file__).resolve().parent


def read(path):return json.loads(path.read_text())
def write(path,value):path.write_text(json.dumps(value,indent=2)+'\n')
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    case=os.environ['UAV_DIAG_CASE'];arm=os.environ['UAV_DIAG_ARM'];assert arm in ['baseline','small_push']
    entry=read(BASE/'targets.json')['cases'][case];folder=h.ROOT/entry['source']
    out=BASE/'cases'/arm/case;out.mkdir(parents=True,exist_ok=False)
    data=read(folder/'input.json');start=read(folder/'starting-point.json');x0=np.array(start['point'])
    rest=h.load_from(h.R2A,'restore');model=rest.fb.FixedBranch(data,moving=True)
    options=copy.deepcopy(read(folder/'solver.json')['options']);assert options==rest.OPTIONS
    if arm=='small_push':options['ipopt']['bound_push']=1e-8
    observer=FirstPoint('first_point',len(x0),model.me+model.mi)
    options['iteration_callback']=observer
    assert violation(model,x0)<=1e-6
    t=monotonic();solver=ca.nlpsol('replay','ipopt',dict(x=model.v,f=model.objective,g=model.constraints),options)
    answer=solver(x0=x0,lbx=model.lb,ubx=model.ub,lbg=np.r_[np.zeros(model.me),np.full(model.mi,-np.inf)],ubg=np.zeros(model.me+model.mi))
    seconds=monotonic()-t;stats=solver.stats()
    point,lam,lam_x=(np.array(answer[k]).ravel() for k in ['x','lam_g','lam_x'])
    assert observer.point is not None,'first iterate was not observed'
    kkt=model.kkt(point,lam,lam_x);accepted=False;checks=None;output=None
    if stats['success'] and max(kkt.values())<=1e-6:accepted,checks,output=rest.accept(model,data,point,lam,lam_x)
    result=dict(case=case,arm=arm,stratum=entry['stratum'],solver_success=bool(stats['success']),
        solver_status=stats['return_status'],iterations=stats['iter_count'],raw_kkt=kkt,accepted=bool(accepted),
        seconds=seconds,checks=checks,provided_start_violation=violation(model,x0),
        first_iterate_violation=violation(model,observer.point),first_minus_provided_inf=float(max(abs(observer.point-x0))),
        first_position_delta_km_inf=float(max(abs(observer.point[:model.nr]-x0[:model.nr]),default=0.)),
        first_energy_delta_inf=float(max(abs(observer.point[model.nr:model.nr+model.ns]-x0[model.nr:model.nr+model.ns]))/model.range),
        first_duration_delta_seconds_inf=float(max(abs(observer.point[model.nr+model.ns:]-x0[model.nr+model.ns:]))/model.p['v_d']*3600.),
        callback_calls=observer.calls,source=str(folder.relative_to(h.ROOT)),
        starting_point_sha256=sha(folder/'starting-point.json'),paper_reproduction=False)
    serial_options={k:v for k,v in options.items() if k!='iteration_callback'}
    write(out/'solver.json',dict(point=point.tolist(),lam=lam.tolist(),lam_x=lam_x.tolist(),options=serial_options))
    write(out/'first-point.json',dict(provided=x0.tolist(),observed=observer.point.tolist()))
    write(out/'iteration-stats.json',stats.get('iterations',{}))
    if accepted:
        output['metrics']=dict(objective=checks['objective'],init_objective=sum(data['init']['s']),converged=False,
            stamps=model.n,seconds=seconds,**checks['original_residuals'])
        output['diagnostic']=dict(method='fixed-branch input-NLP bound initialization diagnostic',paper_algorithm=False,
            branch_kkt=checks['final_kkt'],branch_kkt_pass=True)
        output['stages']=[];write(out/'solution.json',output)
    write(out/'result.json',result);print(json.dumps(result),flush=True)


if __name__=='__main__':main()
