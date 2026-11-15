"""One unchanged fixed-branch NLP, initialized by the general physical construction."""
import json
from time import monotonic
import casadi as ca
import numpy as np
import helpers as h


def read(name):return json.loads((h.INIT/name).read_text())


def main():
    guard=read('guard.json');assert guard['accepted'] and guard['action']=='repair'
    assert not (h.INIT/'nlp-started.json').exists(),'refuse to retry initialization'
    h.write(h.INIT/'nlp-started.json',dict(case=h.CASE))
    data,witness=read('input.json'),read('witness.json')
    rest=h.load_from(h.R2A,'restore');fb=rest.fb
    m=h.fidelity.Variant('R')
    np.testing.assert_array_equal(m.native.y,read('original-state.json')['y'])
    start=monotonic()
    result=dict(case=h.CASE,accepted=False,input_only=True,moving_geometry=True,
        initial_objective=sum(data['solution']['s']),initial_min_energy=min(data['solution']['e']),
        initial_modes=data['modes'],initial_task_stamps=data['task_stamp'],stamps=m.stamps)
    try:
        model=fb.FixedBranch(data,moving=True);tr=witness['solution']
        point0=np.r_[np.array(tr['r'])[model.free].ravel(),np.array(tr['e'][1:])*model.range,np.array(tr['s'])*model.p['v_d']]
        _,con,_,_=model.evaluate(point0);con=np.array(con).ravel()
        viol=float(max(0.,max(abs(con[:model.me])),max(con[model.me:],default=-np.inf),max(model.lb-point0),max(point0-model.ub)))
        assert viol<=1e-6
        h.write(h.INIT/'starting-point.json',dict(point=point0.tolist(),constraint_violation=viol,source='witness.json'))
        solver=ca.nlpsol('general_init','ipopt',dict(x=model.v,f=model.objective,g=model.constraints),rest.OPTIONS)
        answer=solver(x0=point0,lbx=model.lb,ubx=model.ub,lbg=np.r_[np.zeros(model.me),np.full(model.mi,-np.inf)],ubg=np.zeros(model.me+model.mi))
        point,lam,lam_x=(np.array(answer[k]).ravel() for k in ['x','lam_g','lam_x'])
        raw=model.kkt(point,lam,lam_x)
        result.update(solver_success=bool(solver.stats()['success']),solver_status=solver.stats()['return_status'],
            iterations=solver.stats()['iter_count'],raw_kkt=raw)
        h.write(h.INIT/'solver.json',dict(point=point.tolist(),lam=lam.tolist(),lam_x=lam_x.tolist(),options=rest.OPTIONS))
        if result['solver_success'] and max(raw.values())<=1e-6:
            accepted,report,output=rest.accept(model,data,point,lam,lam_x);result.update(report,accepted=bool(accepted))
            if accepted:
                tr=output['solution'];positions=np.array(tr['r'])
                result.update(max_position_change_km=float(max(np.linalg.norm(positions-np.array(data['solution']['r']),axis=1))),
                    same_modes=output['modes']==data['modes'],same_task_stamps=output['task_stamp']==data['task_stamp'])
                assert result['same_modes'] and result['same_task_stamps']
                y=np.r_[positions[1:-1].ravel(),tr['e'][1:],tr['s'],tr['c']]/m.scale
                m.stage(.0005,12.)
                class Wrap:pass
                w=Wrap();w.m=m
                h.write(h.INIT/'source.json',dict(h.state(y,np.zeros(m.me),np.zeros(m.mi),1e4,0),eps=.0005,p=12.,
                    **h.assess(w,y,np.zeros(m.me),np.zeros(m.mi))))
                output['metrics']=dict(objective=report['objective'],init_objective=result['initial_objective'],converged=False,
                    stamps=m.stamps,seconds=monotonic()-start,**report['original_residuals'])
                output['experiment']=dict(name='general input-only fixed-branch initialization',paper_algorithm=False,
                    y_full_precision=y.tolist(),variant_y=y.tolist())
                output['diagnostic']=dict(method='original fixed-branch input optimization after general repair',paper_algorithm=False,
                    branch_kkt=report['final_kkt'],branch_kkt_pass=True)
                output['stages']=[];h.write(h.INIT/'solution.json',output)
        else:result['reason']='solver flag or returned fixed-branch KKT'
    except (AssertionError,RuntimeError,ValueError) as error:result['reason']=repr(error)
    result['seconds']=monotonic()-start;h.write(h.INIT/'result.json',result);m.close()
    h.load_from(h.BASE,'verify_init').main();print(json.dumps(result),flush=True)


if __name__=='__main__':main()
