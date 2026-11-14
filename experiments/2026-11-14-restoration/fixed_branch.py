"""Exact original constraints on a frozen visit/mode branch, with automatic derivatives.

This is feasibility restoration/reoptimization, not the paper's smoothing algorithm.
"""
import copy
import json
import math
from pathlib import Path
import sys
from time import monotonic

import casadi as ca
import numpy as np

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import diagnose_solution as diag
import carrier_certificate as carrier

ENERGY_BUFFER=1e-8


def charge_expr(p,e,t):
    sigma=(p['e_max']-p['e_th'])/p['kappa']
    transition=(p['e_th']-e)/p['kappa']
    cv=lambda start,time:p['e_max']-(p['e_max']-start)*ca.exp(-time/sigma)
    return ca.if_else(e<p['e_th'],ca.if_else(t<=transition,e+p['kappa']*t,
        cv(p['e_th'],t-transition)),cv(e,t))


def restore_source(d):
    d=copy.deepcopy(d)
    tr,p=d['solution'],d['phys'];n=len(tr['r']);ns=n-1;nr=2*(n-2)
    y=np.array(d['experiment']['y_full_precision'])
    scale=np.r_[np.ones(nr),np.full(ns,p['zeta']/p['v_d']),np.full(2*ns,1/p['v_d'])]
    assert len(y)==len(scale)
    x=y*scale
    tr['r']=[d['instance']['r0']]+x[:nr].reshape(-1,2).tolist()+[d['instance']['rf']]
    tr['e']=[p['e_max']]+x[nr:nr+ns].tolist()
    tr['s']=x[nr+ns:nr+2*ns].tolist();tr['c']=x[nr+2*ns:].tolist()
    return d


class FixedBranch:
    def __init__(self,d,moving):
        self.data=copy.deepcopy(d);self.p=p=d['phys'];self.moving=moving
        self.n=len(d['solution']['r']);self.ns=self.n-1
        self.modes=list(d['modes']);self.stamps=list(d['task_stamp'])
        r=np.array(d['solution']['r']);anchors={0:d['instance']['r0'],self.n-1:d['instance']['rf']}
        for point,k in zip(d['instance']['tasks'],self.stamps):
            if k in anchors:assert np.linalg.norm(np.array(anchors[k])-point)<1e-14
            anchors[k]=point
        for k,point in anchors.items():r[k]=point
        self.initial_positions=r
        self.free=[k for k in range(self.n) if moving and k not in anchors]
        self.nr=2*len(self.free);self.range=p['v_d']/p['zeta']
        self.v=ca.SX.sym('y',self.nr+2*self.ns)
        positions=[ca.DM(point) for point in r]
        for i,k in enumerate(self.free):positions[k]=self.v[2*i:2*i+2]
        self.energy=[ca.SX(p['e_max'])]+[self.v[self.nr+k]/self.range for k in range(self.ns)]
        self.durations=[self.v[self.nr+self.ns+k]/p['v_d'] for k in range(self.ns)]
        self.lb=np.r_[np.full(self.nr,-np.inf),np.full(self.ns,(p['e_min']+ENERGY_BUFFER)*self.range),
                      np.full(self.ns,p['s_min']*p['v_d'])]
        self.ub=np.r_[np.full(self.nr,np.inf),np.full(self.ns,p['e_max']*self.range),
                      np.full(self.ns,p['s_max']*p['v_d'])]
        self.speed_lower=[]
        for k,mode in enumerate(self.modes):
            speed=p['v_c'] if mode>=0 else p['v_d']
            lower=max(p['s_min'],math.dist(r[k],r[k+1])/speed+1e-12)
            self.speed_lower.append(lower)
            if not moving:self.lb[self.nr+self.ns+k]=lower*p['v_d']
        eq=[];ineq=[]
        for k,mode in enumerate(self.modes):
            before,after=self.energy[k:k+2];s=self.durations[k]
            predicted=charge_expr(p,before,s) if mode>=0 else before-p['zeta']*s
            eq.append(self.range*(after-predicted))
            if moving:
                speed=p['v_c'] if mode>=0 else p['v_d']
                distance2=ca.sumsqr(positions[k+1]-positions[k])
                denominator=ca.sqrt(distance2+1e-6)+ca.sqrt((speed*s)**2+1e-6)
                ineq.append((distance2-(speed*s)**2)/denominator)
        contacts={(mode,k0) for k,mode in enumerate(self.modes) if mode>=0 for k0 in [k,k+1]}
        for j,k in sorted(contacts):
            reg=d['instance']['regions'][j]
            if k in self.free:
                ineq.append((ca.sumsqr(positions[k]-ca.DM(reg['o']))-reg['rho']**2)/(2*reg['rho']))
            else:
                assert math.dist(r[k],reg['o'])<=reg['rho']+1e-10,(j,k,'fixed task/contact conflict')
        self.me=len(eq);self.mi=len(ineq)
        self.h=ca.vertcat(*eq);self.g=ca.vertcat(*ineq) if ineq else ca.SX.zeros(0,1)
        self.constraints=ca.vertcat(self.h,self.g);self.objective=sum(self.durations)
        self.evaluate=ca.Function('branch_values',[self.v],[self.objective,self.constraints,
            ca.gradient(self.objective,self.v),ca.jacobian(self.constraints,self.v)])
        tr=d['solution']
        initial_e=np.clip(np.array(tr['e'][1:]),p['e_min']+ENERGY_BUFFER,p['e_max'])
        initial_s=np.maximum(np.array(tr['s']),np.array(self.speed_lower))
        self.x0=np.r_[r[self.free].ravel(),initial_e*self.range,initial_s*p['v_d']]

    def kkt(self,point,lam,lam_x):
        f,con,gradient,jac=self.evaluate(point)
        con=np.array(con).ravel();grad=np.array(gradient).ravel()+np.array(jac).T@lam+lam_x
        h,g=con[:self.me],con[self.me:]
        lower=np.isfinite(self.lb);upper=np.isfinite(self.ub)
        lower_mu=np.maximum(-lam_x,0.);upper_mu=np.maximum(lam_x,0.)
        comp=[0.]+np.abs(np.minimum(lam[self.me:],-g)).tolist()
        comp+=np.abs(np.minimum(lower_mu[lower],point[lower]-self.lb[lower])).tolist()
        comp+=np.abs(np.minimum(upper_mu[upper],self.ub[upper]-point[upper])).tolist()
        return dict(stat=float(max(abs(grad))),
            feas=float(max([0.]+abs(h).tolist()+g.tolist()+(self.lb-point).tolist()+(point-self.ub).tolist())),
            comp=float(max(comp)),dual=float(max([0.]+(-lam[self.me:]).tolist()+
                lower_mu[~lower].tolist()+upper_mu[~upper].tolist())))

    def decode(self,point):
        r=self.initial_positions.copy()
        for i,k in enumerate(self.free):r[k]=point[2*i:2*i+2]
        return r,point[self.nr+self.ns:]/self.p['v_d']

    def run(self,name):
        options={'print_time':False,'ipopt':{'print_level':0,'sb':'yes','hessian_approximation':'exact',
            'tol':1e-10,'dual_inf_tol':1e-8,'constr_viol_tol':1e-11,'compl_inf_tol':1e-9,
            'acceptable_iter':0,'max_iter':1500,'max_wall_time':300.,'nlp_scaling_method':'none',
            'bound_relax_factor':0.,'mu_strategy':'adaptive'}}
        solver=ca.nlpsol('fixed_branch','ipopt',dict(x=self.v,f=self.objective,g=self.constraints),options)
        start=monotonic()
        solution=solver(x0=self.x0,lbx=self.lb,ubx=self.ub,
            lbg=np.r_[np.zeros(self.me),np.full(self.mi,-np.inf)],ubg=np.zeros(self.me+self.mi))
        elapsed=monotonic()-start
        point=np.array(solution['x']).ravel();lam=np.array(solution['lam_g']).ravel();lam_x=np.array(solution['lam_x']).ravel()
        residual=self.kkt(point,lam,lam_x);r,s=self.decode(point)
        (HERE/(name+'-solver.json')).write_text(json.dumps(dict(point=point.tolist(),lam=lam.tolist(),
            lam_x=lam_x.tolist(),kkt=residual,solver_status=solver.stats()['return_status'],
            solver_success=bool(solver.stats()['success']),iterations=solver.stats()['iter_count'],
            seconds=elapsed,options=options),indent=2,allow_nan=False)+'\n')
        # Only remove roundoff in speed/time bounds, then certify with a complete battery replay.
        before=s.copy()
        for k,mode in enumerate(self.modes):
            speed=self.p['v_c'] if mode>=0 else self.p['v_d']
            s[k]=max(s[k],self.p['s_min'],math.dist(r[k],r[k+1])/speed)
        assert max(s)<=self.p['s_max']+1e-11
        d=copy.deepcopy(self.data);d.pop('experiment',None)
        tr=d['solution']=dict(r=r.tolist(),s=s.tolist(),c=[float(t) if m>=0 else 0. for t,m in zip(s,self.modes)])
        tr['e']=diag.replay(d)
        check=diag.residuals(d)
        assert check['viol']<1e-10,check
        assert min(tr['e'])>=self.p['e_min'] and max(tr['e'])<=self.p['e_max']
        d['stages']=[]
        d['metrics']=dict(objective=sum(s),init_objective=sum(d['init']['s']),converged=False,
            seconds=elapsed,stamps=self.n,**check)
        d['diagnostic']=dict(method='exact fixed visits/modes NLP; geometry '+('free' if self.moving else 'fixed'),
            source_objective=self.data['metrics']['objective'],paper_algorithm=False,global_optimality=False,
            energy_buffer=ENERGY_BUFFER,branch_kkt=residual,branch_kkt_pass=all(v<=1e-6 for v in residual.values()),
            max_roundoff_time_correction_hours=float(max(abs(s-before))),
            max_position_change_km=float(max(np.linalg.norm(r-np.array(self.data['solution']['r']),axis=1))))
        d['restoration']=dict(name=name,solver_status=solver.stats()['return_status'],solver_success=bool(solver.stats()['success']),
            iterations=solver.stats()['iter_count'],variables=int(self.v.numel()),equalities=self.me,inequalities=self.mi,
            options=options,solver_point=point.tolist(),lam=lam.tolist(),lam_x=lam_x.tolist())
        certificate=carrier.certify(d)
        if certificate['feasible']:certificate['independent_check']=carrier.check_constructed(d,certificate)
        (HERE/(name+'-carrier.json')).write_text(json.dumps(certificate,indent=2,allow_nan=False)+'\n')
        build_history(d)
        (HERE/(name+'.json')).write_text(json.dumps(d,indent=2,allow_nan=False)+'\n')
        print(json.dumps(dict(name=name,objective=float(sum(s)),min_energy=min(tr['e']),original_violation=check['viol'],
            branch_kkt=residual,solver_status=solver.stats()['return_status'],carrier=certificate['feasible'],seconds=elapsed)),flush=True)
        return d


def build_history(d):
    tr,p=d['solution'],d['phys'];h=dict(t=[],e=[],d=[],stamps=[0.]);t0=0.
    for k,(s,mode) in enumerate(zip(tr['s'],d['modes'])):
        for i in range(61):
            fraction=i/60;r=[(1-fraction)*a+fraction*b for a,b in zip(tr['r'][k],tr['r'][k+1])]
            e=diag.charge(p,tr['e'][k],fraction*s) if mode>=0 else tr['e'][k]-p['zeta']*fraction*s
            h['t'].append(t0+fraction*s);h['e'].append(e)
            h['d'].append(max(0.,min(math.dist(r,reg['o'])-reg['rho'] for reg in d['instance']['regions'])))
        t0+=s;h['stamps'].append(t0)
    d['history']=h


if __name__=='__main__':
    source=ROOT/'experiments/2026-11-14-final-continuation/fig1-accurate/raw.json'
    d=restore_source(json.loads(source.read_text()))
    assert not (HERE/'geometry.json').exists() and not (HERE/'timing.json').exists(),'do not overwrite results'
    a=FixedBranch(d,moving=False).run('timing')
    b=FixedBranch(a,moving=True).run('geometry')
