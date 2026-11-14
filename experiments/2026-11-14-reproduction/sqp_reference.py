"""Independent SQP reference with original Rust constraints and exact Jacobians."""
import argparse
import json
from pathlib import Path
from time import monotonic
from scipy.optimize import minimize
from independent_al import Model,np,diagnostics


def solve(args):
    model=Model(args.tau,args.seed,args.library)
    y=model.y.copy();stages=[];start=monotonic();states=[]
    lam,mu=np.zeros(model.me),np.zeros(model.mi)
    for stage in range(args.stages):
        model.stage(max(.0005,.2*.6**stage),min(12.,2*1.2**stage))
        cache={}
        def evaluate(point):
            if monotonic()-start>args.timeout:raise TimeoutError()
            if 'point' not in cache or not np.array_equal(point,cache['point']):
                point=np.ascontiguousarray(point)
                model.eval(point,np.zeros(model.me),np.zeros(model.mi),0.)
                cache.update(point=point.copy(),f=float(model.objective[0]),grad=model.grad.copy(),
                             h=model.h.copy(),g=model.g.copy(),jac=None)
            return cache
        def jac(point):
            value=evaluate(point)
            if value['jac'] is None:value['jac']=model.jacobian(np.ascontiguousarray(point))
            return value['jac']
        try:
            result=minimize(lambda point:(evaluate(point)['f'],evaluate(point)['grad']),y,jac=True,
                method='SLSQP',constraints=[
                    dict(type='eq',fun=lambda point:evaluate(point)['h'],jac=lambda point:jac(point)[:model.me]),
                    dict(type='ineq',fun=lambda point:-evaluate(point)['g'],jac=lambda point:-jac(point)[model.me:])],
                options=dict(ftol=1e-12,maxiter=args.inner))
        except TimeoutError:break
        y=np.ascontiguousarray(result.x)
        if hasattr(result,'multipliers'):
            lam=-np.asarray(result.multipliers[:model.me]).copy()
            mu=np.asarray(result.multipliers[model.me:]).copy()
        model.eval(y,lam,mu,0.)
        kkt=dict(stat=float(max(abs(model.grad))),feas=float(max(max(abs(model.h)),max(model.g),0.)),
                 comp=float(max(abs(np.minimum(mu,-model.g)))),dual=float(max(0.,-min(mu))))
        row=dict(stage=stage+1,kkt=kkt,converged=all(v<=1e-6 for v in kkt.values()),
                 objective=float(model.objective[0]),status=result.message,solver_success=bool(result.success),
                 iterations=int(result.nit),elapsed=monotonic()-start)
        print(json.dumps(row),flush=True);stages.append(row);states.append(y.tolist())
    d=model.solution(y);d['stages']=stages
    d['metrics']['converged']=bool(len(stages)==args.stages and stages[-1]['converged'])
    d['metrics']['seconds']=monotonic()-start
    d['experiment']=dict(backend='SLSQP diagnostic; not paper AL',arguments=vars(args),
        diagnostics=diagnostics(model,y,lam,mu),y_full_precision=y.tolist(),stage_states=states)
    Path(args.out).write_text(json.dumps(d,indent=2,allow_nan=False)+'\n');model.close()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--tau',type=int,default=1);p.add_argument('--seed',type=int,default=0)
    p.add_argument('--library',default='/tmp/uav-reproduction-bridge.so')
    p.add_argument('--stages',type=int,default=13);p.add_argument('--inner',type=int,default=2000)
    p.add_argument('--timeout',type=float,default=90.);p.add_argument('--out',required=True)
    solve(p.parse_args())
