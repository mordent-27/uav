"""One input-only moving-geometry fixed-branch initialization, using R2a's options."""
import copy
import json
from time import monotonic
import casadi as ca
import numpy as np
import helpers as h


def main():
    h.INIT.mkdir(parents=True, exist_ok=False)
    m = h.fidelity.Variant('R')
    original = m.native.y.copy()
    prior = json.loads((h.R2D/'cases/G'/h.CASE/'source.json').read_text())
    np.testing.assert_array_equal(original, prior['y'])
    data = copy.deepcopy(m.source)
    trajectory = h.tr.decode(m, original, m.source)
    data['init'] = copy.deepcopy(trajectory)
    data['solution'] = copy.deepcopy(trajectory)
    full_tasks = [trajectory['r'][stamp] for stamp in data['task_stamp']]
    assert max(np.linalg.norm(np.array(a)-b) for a,b in zip(full_tasks,data['instance']['tasks'])) <= 1e-9
    data['instance']['tasks'] = full_tasks
    h.write(h.INIT/'input.json', data)
    restoration = h.load_from(h.R2A, 'restore')
    fb = restoration.fb
    start = monotonic()
    result = dict(case=h.CASE, accepted=False, input_only=True, moving_geometry=True,
        initial_objective=sum(trajectory['s']), initial_min_energy=min(trajectory['e']),
        stamps=m.stamps, initial_modes=data['modes'], initial_task_stamps=data['task_stamp'])
    try:
        model = fb.FixedBranch(data, moving=True)
        model.x0 = h.load_from(h.BASE, 'construct').build(data, model)
        solver = ca.nlpsol('position_init', 'ipopt', dict(x=model.v,f=model.objective,g=model.constraints), restoration.OPTIONS)
        answer = solver(x0=model.x0,lbx=model.lb,ubx=model.ub,
            lbg=np.r_[np.zeros(model.me),np.full(model.mi,-np.inf)],ubg=np.zeros(model.me+model.mi))
        point = np.array(answer['x']).ravel()
        lam, lam_x = np.array(answer['lam_g']).ravel(),np.array(answer['lam_x']).ravel()
        raw = model.kkt(point,lam,lam_x)
        result.update(solver_success=bool(solver.stats()['success']), solver_status=solver.stats()['return_status'],
            iterations=solver.stats()['iter_count'], raw_kkt=raw)
        h.write(h.INIT/'solver.json',dict(point=point.tolist(),lam=lam.tolist(),lam_x=lam_x.tolist(),options=restoration.OPTIONS))
        if result['solver_success'] and max(raw.values()) <= 1e-6:
            accepted, report, output = restoration.accept(model,data,point,lam,lam_x)
            result.update(report,accepted=bool(accepted))
            if accepted:
                positions=np.array(output['solution']['r'])
                result.update(max_position_change_km=float(max(np.linalg.norm(positions-np.array(trajectory['r']),axis=1))),
                    same_modes=output['modes']==data['modes'],same_task_stamps=output['task_stamp']==data['task_stamp'])
                assert result['same_modes'] and result['same_task_stamps'] and model.n==m.stamps
                tr=output['solution']
                y=np.r_[positions[1:-1].ravel(),tr['e'][1:],tr['s'],tr['c']]/m.scale
                m.stage(.0005,12.)
                class Wrap:
                    pass
                wrap=Wrap();wrap.m=m
                source=dict(h.state(y,np.zeros(m.me),np.zeros(m.mi),1e4,0),eps=.0005,p=12.,
                    **h.assess(wrap,y,np.zeros(m.me),np.zeros(m.mi)),
                    note='input-only original fixed-branch NLP initialization with moving positions')
                h.write(h.INIT/'source.json',source)
                output['metrics']=dict(objective=report['objective'],init_objective=result['initial_objective'],
                    converged=False,stamps=m.stamps,seconds=monotonic()-start,**report['original_residuals'])
                output['stages']=[]
                output['experiment']=dict(name='moving-position-input-initialization',paper_algorithm=False,
                    y_full_precision=y.tolist(),variant_y=y.tolist())
                output['diagnostic']=dict(method='original fixed-branch input initialization; geometry free',
                    paper_algorithm=False,branch_kkt=report['final_kkt'],branch_kkt_pass=True)
                h.write(h.INIT/'solution.json',output)
        else:
            result['reason']='solver flag or returned fixed-branch KKT'
    except (AssertionError,RuntimeError,ValueError) as error:
        result['reason']=repr(error)
    result['seconds']=monotonic()-start
    h.write(h.INIT/'result.json',result)
    m.close()
    h.load_from(h.BASE,'verify_init').main()
    print(json.dumps(result,allow_nan=False),flush=True)


if __name__=='__main__':
    main()
