"""Recompute both convex-relaxation certificates with independent NumPy formulas."""
import json
from pathlib import Path
import numpy as np

HERE=Path(__file__).resolve().parent


def evaluate(d,x,battery):
    p=d['phys'];n=len(d['solution']['r']);ns=n-1
    anchors={0:d['instance']['r0'],n-1:d['instance']['rf']}
    for k,a in zip(d['task_stamp'],d['instance']['tasks']):anchors[k]=a
    free=[k for k in range(n) if k not in anchors];nr=2*len(free);offset={k:2*i for i,k in enumerate(free)}
    r=np.array(d['solution']['r']);r[free]=x[:nr].reshape(-1,2)
    for k,a in anchors.items():r[k]=a
    h=[];g=[];jh=[];jg=[]
    def position(row,k,value):
        if k in offset:row[offset[k]:offset[k]+2]+=value
    def energy(row,k,value):
        if k:row[nr+ns+k-1]+=value
    for k,mode in enumerate(d['modes']):
        a=(p['v_c'] if mode>=0 else p['v_d'])/p['v_d'];length=a*x[nr+k];delta=r[k+1]-r[k]
        g.append(delta@delta/length-length)
        row=np.zeros(len(x));position(row,k+1,2*delta/length);position(row,k,-2*delta/length)
        row[nr+k]=-a*(delta@delta/length**2+1);jg.append(row)
    for j,k in sorted({(m,k0) for k,m in enumerate(d['modes']) if m>=0 for k0 in [k,k+1]}):
        if k not in offset:continue
        region=d['instance']['regions'][j];delta=r[k]-region['o']
        g.append((delta@delta-region['rho']**2)/(2*region['rho']))
        row=np.zeros(len(x));position(row,k,delta/region['rho']);jg.append(row)
    if battery:
        e=np.r_[p['e_max']*p['v_d']/p['zeta'],x[nr+ns:]]
        for k,mode in enumerate(d['modes']):
            row=np.zeros(len(x));energy(row,k+1,1.);energy(row,k,-1.)
            delta=e[k+1]-e[k]
            if mode<0:
                row[nr+k]=1.;h.append(delta+x[nr+k]);jh.append(row)
            else:
                row[nr+k]=-p['kappa']/p['zeta']
                g.append(delta-p['kappa']/p['zeta']*x[nr+k]);jg.append(row)
                other=np.zeros(len(x));energy(other,k,1.);energy(other,k+1,-1.)
                g.append(-delta);jg.append(other)
    objective=float(sum(x[nr:nr+ns])/p['v_d']);gradient=np.zeros(len(x));gradient[nr:nr+ns]=1/p['v_d']
    return objective,np.array(h+g),np.array(jh+jg),gradient,len(h)


def main():
    d=json.loads((HERE/'geometry.json').read_text());results=[]
    for name,battery in [('travel-bound',False),('charging-bound',True)]:
        saved=json.loads((HERE/(name+'.json')).read_text());x=np.array(saved['point']);mu=np.array(saved['multipliers'])
        f,c,jac,grad,me=evaluate(d,x,battery)
        assert min(mu[me:])>=0
        np.testing.assert_allclose(c,saved['constraint_values'],rtol=1e-10,atol=1e-10)
        residual=grad+jac.T@mu
        np.testing.assert_allclose(residual,saved['gradient_residual'],rtol=1e-7,atol=1e-12)
        lower,upper=np.array(saved['lower_bounds']),np.array(saved['upper_bounds'])
        bound=float(f+mu@c+np.minimum(residual*(lower-x),residual*(upper-x)).sum())
        assert abs(bound-saved['affine_dual_lower_bound'])<1e-8
        # Supporting-plane inequality for the convex Lagrangian on the stated domain.
        rng=np.random.default_rng(191)
        for _ in range(30):
            point=rng.uniform(lower,upper);fv,cv,_,_,_=evaluate(d,point,battery)
            support=f+mu@c+residual@(point-x)
            assert fv+mu@cv>=support-1e-8
        results.append(dict(name=name,independent_lower_bound=bound,equality_count=me,
                            convex_support_checks=30,agrees=True))
    (HERE/'bound-verification.json').write_text(json.dumps(results,indent=2)+'\n');print(json.dumps(results,indent=2))


if __name__=='__main__':main()
