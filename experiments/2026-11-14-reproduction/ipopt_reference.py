"""Diagnostic IPOPT solve of the same Rust NLP, with an exact callback Jacobian.

This is an independent feasibility/conditioning reference, not the paper's AL.
"""
import argparse
import json
from pathlib import Path
from time import monotonic

import casadi as ca
from independent_al import Model,np,diagnostics


class Jacobian(ca.Callback):
    def __init__(self,name,model):
        self.model=model
        ca.Callback.__init__(self)
        self.construct(name,{})
    def get_n_in(self):return 4
    def get_n_out(self):return 3
    def get_sparsity_in(self,i):
        m=self.model
        return ca.Sparsity.dense([m.n,1,m.me,m.mi][i],1)
    def get_sparsity_out(self,i):
        m=self.model
        return ca.Sparsity.dense([1,m.me,m.mi][i],m.n)
    def eval(self,args):
        m=self.model;y=np.asarray(args[0]).ravel().copy()
        _,grad=m.eval(y,np.zeros(m.me),np.zeros(m.mi),0.)
        jac=m.jacobian(y)
        return [ca.DM(grad.reshape(1,-1)),ca.DM(jac[:m.me]),ca.DM(jac[m.me:])]


class Oracle(ca.Callback):
    def __init__(self,name,model):
        self.model=model;self.derivatives=[]
        ca.Callback.__init__(self)
        self.construct(name,{})
    def get_n_in(self):return 1
    def get_n_out(self):return 3
    def get_sparsity_in(self,i):return ca.Sparsity.dense(self.model.n,1)
    def get_sparsity_out(self,i):
        return ca.Sparsity.dense([1,self.model.me,self.model.mi][i],1)
    def has_jacobian(self):return True
    def get_jacobian(self,name,inames,onames,opts):
        result=Jacobian(name,self.model);self.derivatives.append(result);return result
    def eval(self,args):
        m=self.model;y=np.asarray(args[0]).ravel().copy()
        m.eval(y,np.zeros(m.me),np.zeros(m.mi),0.)
        return [ca.DM(m.objective),ca.DM(m.h),ca.DM(m.g)]


def solve(args):
    m=Model(args.tau,args.seed,args.library)
    oracle=Oracle('rust_model',m)
    x=ca.MX.sym('y',m.n)
    f,h,g=oracle(x)
    options={'print_time':False,'ipopt':{'print_level':0,'hessian_approximation':'limited-memory',
        'tol':1e-6,'dual_inf_tol':1e-6,'constr_viol_tol':1e-6,'compl_inf_tol':1e-6,
        'acceptable_iter':0,'max_iter':args.inner,'max_cpu_time':args.timeout,
        'nlp_scaling_method':'none','bound_relax_factor':0.,'sb':'yes'}}
    solver=ca.nlpsol('reference','ipopt',dict(x=x,f=f,g=ca.vertcat(h,g)),options)
    y=m.y.copy();stages=[];start=monotonic()
    lam,mu=np.zeros(m.me),np.zeros(m.mi)
    for stage in range(args.stages):
        m.stage(max(.0005,.2*.6**stage),min(12.,2*1.2**stage))
        result=solver(x0=y,lbg=np.r_[np.zeros(m.me),np.full(m.mi,-np.inf)],ubg=np.zeros(m.me+m.mi))
        y=np.asarray(result['x']).ravel().copy()
        dual=np.asarray(result['lam_g']).ravel();lam,mu=dual[:m.me].copy(),dual[m.me:].copy()
        m.eval(y,lam,mu,0.)
        kkt=dict(stat=float(max(abs(m.grad))),feas=float(max(max(abs(m.h)),max(m.g),0.)),
                 comp=float(max(abs(np.minimum(mu,-m.g)))))
        row=dict(stage=stage+1,kkt=kkt,solver_status=solver.stats()['return_status'],
                 solver_success=solver.stats()['success'],objective=float(m.objective[0]),
                 converged=all(v<=1e-6 for v in kkt.values()),elapsed=monotonic()-start)
        print(json.dumps(row),flush=True);stages.append(row)
    d=m.solution(y)
    d['stages']=stages;d['metrics']['converged']=stages[-1]['converged']
    d['metrics']['seconds']=monotonic()-start
    d['experiment']=dict(backend='IPOPT diagnostic; not paper AL',arguments=vars(args),
                         diagnostics=diagnostics(m,y,lam,mu),y_full_precision=y.tolist())
    Path(args.out).write_text(json.dumps(d,indent=2,allow_nan=False)+'\n');m.close()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--tau',type=int,default=1);p.add_argument('--seed',type=int,default=0)
    p.add_argument('--library',default='/tmp/uav-reproduction-bridge.so')
    p.add_argument('--stages',type=int,default=13);p.add_argument('--inner',type=int,default=2000)
    p.add_argument('--timeout',type=float,default=90.);p.add_argument('--out',required=True)
    solve(p.parse_args())
