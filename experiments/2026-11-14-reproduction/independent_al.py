"""Independent AL diagnostics over the unchanged Rust model and analytic gradient.

Needs NumPy/SciPy. Build the C ABI library first (see REPORT.md); no Rust source changes.
SciPy L-BFGS-B is used without bounds, so all constraints remain in the same AL.
"""

import argparse
import ctypes as ct
import json
from pathlib import Path
from time import monotonic

import numpy as np
from scipy.optimize import minimize


HERE = Path(__file__).resolve().parent
DOUBLE = ct.POINTER(ct.c_double)


class Model:
    def __init__(self, tau=1, seed=0, library='/tmp/uav-reproduction-bridge.so'):
        self.lib = lib = ct.CDLL(library)
        lib.uav_create.argtypes = [ct.c_size_t, ct.c_uint64]
        lib.uav_create.restype = ct.c_void_p
        lib.uav_free.argtypes = [ct.c_void_p]
        lib.uav_dims.argtypes = [ct.c_void_p, ct.POINTER(ct.c_size_t)]
        lib.uav_initial.argtypes = [ct.c_void_p, DOUBLE, DOUBLE]
        lib.uav_stage.argtypes = [ct.c_void_p, ct.c_double, ct.c_double, ct.c_double]
        lib.uav_eval.argtypes = [ct.c_void_p, DOUBLE, DOUBLE, DOUBLE, ct.c_double,
                                DOUBLE, DOUBLE, DOUBLE, DOUBLE]
        lib.uav_eval.restype = ct.c_double
        lib.uav_jacobian.argtypes = [ct.c_void_p, DOUBLE, DOUBLE]
        lib.uav_rust_inner.argtypes = [ct.c_void_p, DOUBLE, DOUBLE, DOUBLE,
                                     ct.c_double, ct.c_size_t, DOUBLE]
        lib.uav_json.argtypes = [ct.c_void_p, DOUBLE, ct.c_void_p, ct.c_size_t]
        lib.uav_json.restype = ct.c_size_t
        self.ctx = lib.uav_create(tau, seed)
        dims = (ct.c_size_t*4)()
        lib.uav_dims(self.ctx, dims)
        self.n, self.me, self.mi, self.stamps = dims
        self.y, self.scale = np.empty(self.n), np.empty(self.n)
        lib.uav_initial(self.ctx, self.ptr(self.y), self.ptr(self.scale))
        self.h, self.g, self.grad = np.empty(self.me), np.empty(self.mi), np.empty(self.n)
        self.objective = np.empty(1)

    @staticmethod
    def ptr(array):
        assert array.dtype == np.float64 and array.flags.c_contiguous
        return array.ctypes.data_as(DOUBLE)

    def close(self):
        if self.ctx:
            self.lib.uav_free(self.ctx)
            self.ctx = None

    def stage(self, eps, p, delta=.001):
        self.lib.uav_stage(self.ctx, eps, p, delta)

    def eval(self, y, lam, mu, rho):
        value = self.lib.uav_eval(self.ctx, self.ptr(y), self.ptr(lam), self.ptr(mu),rho,
            self.ptr(self.grad), self.ptr(self.h), self.ptr(self.g), self.ptr(self.objective))
        if not np.isfinite(value) or not all(np.isfinite(a).all() for a in [self.grad,self.h,self.g]):
            raise FloatingPointError('nonfinite model evaluation')
        return value, self.grad.copy()

    def jacobian(self, y):
        jac = np.empty((self.me+self.mi,self.n))
        self.lib.uav_jacobian(self.ctx, self.ptr(y),self.ptr(jac))
        return jac

    def solution(self, y):
        size = self.lib.uav_json(self.ctx,self.ptr(y),None,0)
        buf = ct.create_string_buffer(size)
        self.lib.uav_json(self.ctx,self.ptr(y),buf,size)
        return json.loads(buf.raw)


def diagnostics(model, y, lam, mu):
    model.eval(y,lam,mu,0.)
    jac = model.jacobian(y)
    ns = model.stamps-1
    norms = np.linalg.norm(jac,axis=1)
    active = np.r_[np.ones(model.me,dtype=bool), (model.g >= -1e-7) | (mu > 1e-7)]
    singular = np.linalg.svd(jac[active],compute_uv=False)
    return dict(task_jacobian_norms=norms[ns:ns+model.me-2*ns].tolist(),
                mode_jacobian_norms=norms[model.me-ns:model.me].tolist(),
                active_constraint_count=int(active.sum()), variable_count=model.n,
                jacobian_singular_values=singular.tolist(),
                lagrangian_gradient=model.grad.tolist(),
                lam=lam.tolist(), mu=mu.tolist())


def solve(args):
    model = Model(args.tau,args.seed,args.library)
    y = model.y.copy()
    lam, mu = np.zeros(model.me), np.zeros(model.mi)
    rho, stages, rows, states = 10., [], [], []
    start = monotonic()
    destination = Path(args.out)
    destination.parent.mkdir(parents=True,exist_ok=True)
    log_path = destination.with_suffix('.outer.jsonl')
    timeout = False
    active_stage = args.start_stage+1
    total_inner, total_evals = 0,0
    try:
        with log_path.open('w') as log:
            for stage in range(args.start_stage,args.start_stage+args.stages):
                active_stage = stage+1
                eps, p = max(.0005,.2*.6**stage), min(12.,2.*1.2**stage)
                model.stage(eps,p)
                if args.reset:
                    rho, lam, mu = 10., np.zeros(model.me), np.zeros(model.mi)
                previous = np.inf
                converged = False
                budget = args.final_outer if stage+1==args.start_stage+args.stages else args.outer
                for outer in range(budget):
                    def fg(point):
                        if monotonic()-start > args.timeout:
                            raise TimeoutError()
                        return model.eval(point,lam,mu,rho)
                    if args.backend == 'rust':
                        result = np.empty(5)
                        model.lib.uav_rust_inner(model.ctx,model.ptr(y),model.ptr(lam),model.ptr(mu),
                                                rho,args.inner,model.ptr(result))
                        inner = dict(value=float(result[0]),grad=float(result[1]),iters=int(result[2]),
                                     evals=int(result[3]),status='rust-'+str(int(result[4])))
                    else:
                        options = dict(gtol=1e-6,maxiter=args.inner)
                        if args.backend == 'scipy-lbfgs':
                            options.update(ftol=args.ftol,maxls=65,maxcor=20,maxfun=100000)
                            method = 'L-BFGS-B'
                        else:
                            method = 'BFGS'
                        result = minimize(fg,y,jac=True,method=method,options=options)
                        y = np.ascontiguousarray(result.x)
                        inner = dict(value=float(result.fun),grad=float(np.max(np.abs(result.jac))),
                                     iters=result.nit,evals=result.nfev,status=str(result.message))
                    total_inner += inner['iters']
                    total_evals += inner['evals']
                    model.eval(y,lam,mu,0.)
                    lam += rho*model.h
                    mu = np.maximum(0.,mu+rho*model.g)
                    model.eval(y,lam,mu,0.)
                    kkt = dict(stat=float(np.max(np.abs(model.grad))),
                               feas=float(max(np.max(np.abs(model.h)),np.max(model.g),0.)),
                               comp=float(np.max(np.abs(np.minimum(mu,-model.g)))))
                    converged = all(v <= 1e-6 for v in kkt.values())
                    row = dict(stage=stage+1,outer=outer+1,eps=eps,p=p,rho=rho,
                               objective=float(model.objective[0]),kkt=kkt,inner=inner,
                               elapsed=monotonic()-start,converged=converged)
                    rows.append(row)
                    log.write(json.dumps(row)+'\n'); log.flush()
                    if converged:
                        break
                    violation = max(kkt['feas'],kkt['comp'])
                    if violation > .25*previous:
                        rho = min(rho*10,1e8)
                    previous = violation
                stages.append(dict(row,inner_iters=total_inner,evals=total_evals))
                states.append(dict(y=y.tolist(),lam=lam.tolist(),mu=mu.tolist(),rho=rho))
                print(json.dumps(row),flush=True)
    except TimeoutError:
        timeout = True
    finally:
        solution = model.solution(y)
        solution['stages'] = stages
        solution['metrics']['converged'] = bool(not timeout and len(stages)==args.stages and stages[-1]['converged'])
        solution['metrics']['seconds'] = monotonic()-start
        solution['experiment'] = dict(backend=args.backend, model='unmodified original Rust',
            scipy_success_is_not_kkt=True,timeout=timeout,arguments=vars(args),
            active_stage=active_stage,
            total_inner=total_inner,total_evals=total_evals,
            y_full_precision=y.tolist(),stage_states=states,
            diagnostics=diagnostics(model,y,lam,mu))
        destination.write_text(json.dumps(solution,indent=2,allow_nan=False)+'\n')
        model.close()
    return solution


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tau',type=int,default=1,help='0 selects fig1')
    parser.add_argument('--seed',type=int,default=0)
    parser.add_argument('--library',default='/tmp/uav-reproduction-bridge.so')
    parser.add_argument('--backend',choices=['rust','scipy-lbfgs','scipy-bfgs'],default='scipy-lbfgs')
    parser.add_argument('--stages',type=int,default=13)
    parser.add_argument('--start-stage',type=int,default=0,help='diagnostic only: skip earlier stages')
    parser.add_argument('--outer',type=int,default=10)
    parser.add_argument('--final-outer',type=int,default=30)
    parser.add_argument('--inner',type=int,default=2000)
    parser.add_argument('--ftol',type=float,default=1e-14)
    parser.add_argument('--timeout',type=float,default=90.)
    parser.add_argument('--reset',action='store_true')
    parser.add_argument('--out',required=True)
    solve(parser.parse_args())
