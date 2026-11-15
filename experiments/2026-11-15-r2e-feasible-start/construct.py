"""One deterministic physical witness: move r20 inside disk 0, then replay charge to .99."""
import copy
import math
from time import monotonic
import numpy as np
import helpers as h


def build(data,model):
    start=monotonic()
    assert h.CASE=='tau7-seed3'
    output=copy.deepcopy(data)
    output.pop('experiment',None)
    tr,phys=output['solution'],output['phys']
    r=np.array(tr['r'])
    assert 20 in model.free and data['modes'][19]==0 and data['modes'][20]==-1
    region=data['instance']['regions'][0]
    center=np.array(region['o']);toward=r[21]-center
    r[20]=center+(region['rho']-.001)*toward/np.linalg.norm(toward)
    ns=len(data['modes']);durations=[];energy=[phys['e_max']]
    sigma=(phys['e_max']-phys['e_th'])/phys['kappa']
    for k,mode in enumerate(data['modes']):
        speed=phys['v_c'] if mode>=0 else phys['v_d']
        duration=max(phys['s_min'],math.dist(r[k],r[k+1])/speed)
        if mode>=0:
            before=energy[-1];target=.99
            if before>=target:
                charging=0.
            elif before<phys['e_th']:
                charging=(phys['e_th']-before)/phys['kappa']+sigma*math.log((phys['e_max']-phys['e_th'])/(phys['e_max']-target))
            else:
                charging=sigma*math.log((phys['e_max']-before)/(phys['e_max']-target))
            duration=max(duration,charging)
            after=h.tr.diag.charge(phys,before,duration)
        else:
            after=energy[-1]-phys['zeta']*duration
        assert phys['e_min']<=after<=phys['e_max'],(k,after)
        assert duration<=phys['s_max'],(k,duration)
        durations.append(duration);energy.append(after)
    tr.update(r=r.tolist(),e=energy,s=durations,c=[s if mode>=0 else 0. for s,mode in zip(durations,data['modes'])])
    residual=h.tr.diag.residuals(output)
    assert residual['viol']<=1e-6
    assert all(tr['r'][stamp]==task for stamp,task in zip(data['task_stamp'],data['instance']['tasks']))
    fb=h.load_from(h.ROOT/'experiments/2026-11-14-restoration','fixed_branch')
    fb.build_history(output)
    assert min(output['history']['e'])>=0. and max(output['history']['e'])<=1.
    report=dict(accepted=True,seconds=monotonic()-start,objective=sum(durations),original_residuals=residual,
        min_energy=min(energy),max_energy=max(energy),changed_stamp=20,target_energy=.99,
        original_leg20_km=math.dist(data['solution']['r'][20],data['solution']['r'][21]),
        new_leg20_km=math.dist(r[20],r[21]),same_modes=True,same_task_stamps=True)
    output['metrics']=dict(objective=sum(durations),init_objective=sum(data['init']['s']),
        converged=False,stamps=ns+1,seconds=report['seconds'],**residual)
    output['diagnostic']=dict(method='constructed physical initial trajectory, no optimization',paper_algorithm=False)
    output['stages']=[]
    h.write(h.INIT/'witness.json',output);h.write(h.INIT/'witness-check.json',report)
    point=np.r_[r[model.free].ravel(),np.array(energy[1:])*model.range,np.array(durations)*phys['v_d']]
    _,con,_,_=model.evaluate(point)
    con=np.array(con).ravel()
    violation=max(0.,max(abs(con[:model.me])),max(con[model.me:],default=-np.inf),max(model.lb-point),max(point-model.ub))
    assert violation<=1e-6,violation
    h.write(h.INIT/'starting-point.json',dict(point=point.tolist(),constraint_violation=float(violation),
        source='witness.json',only_NLP_initial_point_changed=True))
    return point
