"""Convex battery-free relaxation and an affine dual lower-bound certificate.

Only the frozen visit/mode/region assignment is certified. No energy, carrier
repositioning, or global disjunction search is included.
"""
import json
import argparse
from pathlib import Path
from time import monotonic

import casadi as ca
import numpy as np
from fixed_branch import FixedBranch,HERE

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--linear-battery',action='store_true')
args=parser.parse_args()
d=json.loads((HERE/'geometry.json').read_text());p=d['phys'];upper=d['metrics']['objective']
branch=FixedBranch(d,moving=True);nr,ns=branch.nr,branch.ns
x=ca.SX.sym('x',nr+ns+(ns if args.linear_battery else 0));positions=[ca.DM(r) for r in branch.initial_positions]
for i,k in enumerate(branch.free):positions[k]=x[2*i:2*i+2]
times=[x[nr+k]/p['v_d'] for k in range(ns)]
g=[];h=[]
for k,mode in enumerate(branch.modes):
    speed=p['v_c'] if mode>=0 else p['v_d'];length=speed*times[k]
    g.append(ca.sumsqr(positions[k+1]-positions[k])/length-length)
for j,k in sorted({(m,k0) for k,m in enumerate(branch.modes) if m>=0 for k0 in [k,k+1]}):
    if k not in branch.free:continue
    region=d['instance']['regions'][j]
    g.append((ca.sumsqr(positions[k]-ca.DM(region['o']))-region['rho']**2)/(2*region['rho']))
if args.linear_battery:
    energy=[ca.SX(p['e_max']*branch.range)]+[x[nr+ns+k] for k in range(ns)]
    for k,mode in enumerate(branch.modes):
        delta=energy[k+1]-energy[k]
        if mode<0:h.append(delta+x[nr+k])
        else:
            g.append(delta-(p['kappa']/p['zeta'])*x[nr+k])
            g.append(-delta)
me=len(h);g=ca.vertcat(*(h+g));f=sum(times)
origin=np.array(d['instance']['r0']);radius=p['v_d']*upper
lb=np.r_[np.tile(origin-radius,len(branch.free)),np.full(ns,p['v_d']*p['s_min'])]
ub=np.r_[np.tile(origin+radius,len(branch.free)),np.full(ns,p['v_d']*p['s_max'])]
x0=np.r_[np.array(d['solution']['r'])[branch.free].ravel(),np.array(d['solution']['s'])*p['v_d']]
if args.linear_battery:
    lb=np.r_[lb,np.full(ns,p['e_min']*branch.range)]
    ub=np.r_[ub,np.full(ns,p['e_max']*branch.range)]
    x0=np.r_[x0,np.array(d['solution']['e'][1:])*branch.range]
options={'print_time':False,'ipopt':{'print_level':0,'sb':'yes','hessian_approximation':'exact',
    'tol':1e-10,'dual_inf_tol':1e-8,'constr_viol_tol':1e-11,'compl_inf_tol':1e-9,
    'acceptable_iter':0,'max_iter':1500,'max_wall_time':300.,'nlp_scaling_method':'none',
    'bound_relax_factor':0.,'mu_strategy':'adaptive'}}
solver=ca.nlpsol('travel_relaxation','ipopt',dict(x=x,f=f,g=g),options)
start=monotonic();solution=solver(x0=x0,lbx=lb,ubx=ub,lbg=np.r_[np.zeros(me),np.full(int(g.numel())-me,-np.inf)],ubg=0.)
point=np.array(solution['x']).ravel();mu=np.array(solution['lam_g']).ravel()
mu[me:]=np.maximum(0.,mu[me:])
evaluate=ca.Function('dual_certificate',[x],[f,g,ca.gradient(f,x),ca.jacobian(g,x)])
value,con,gradient,jac=evaluate(point);value=float(value);con=np.array(con).ravel()
residual=np.array(gradient).ravel()+np.array(jac).T@mu
# Convexity gives a supporting affine function for f+mu.g, for every nonnegative mu.
# Minimize that affine function exactly over the finite box, absorbing stationarity error.
box_correction=np.minimum(residual*(lb-point),residual*(ub-point))
bound=float(value+mu@con+box_correction.sum())
result=dict(scope='current N and frozen visit/mode/region assignment only; '+
    ('maximum-rate linear battery relaxation' if args.linear_battery else 'energy constraints removed'),
    primal_objective=value,affine_dual_lower_bound=bound,stationarity_box_correction=float(box_correction.sum()),
    multiplier_constraint_term=float(mu@con),duality_gap=value-bound,
    source_feasible_upper=upper,coordinate_box_radius_km=radius,variables=int(x.numel()),constraints=int(g.numel()),
    solver_status=solver.stats()['return_status'],iterations=solver.stats()['iter_count'],seconds=monotonic()-start,
    point=point.tolist(),multipliers=mu.tolist(),gradient_residual=residual.tolist(),
    lower_bounds=lb.tolist(),upper_bounds=ub.tolist(),constraint_values=con.tolist(),options=options)
name='charging-bound' if args.linear_battery else 'travel-bound'
(HERE/(name+'.json')).write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
print(json.dumps({k:v for k,v in result.items() if k not in ['point','multipliers','gradient_residual','lower_bounds','upper_bounds','constraint_values','options']},indent=2))
