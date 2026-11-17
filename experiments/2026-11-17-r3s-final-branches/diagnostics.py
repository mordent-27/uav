"""Pure-Python residuals and necessary conditions for one assigned physical branch."""
import math
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts'))
from diagnose_solution import signed_charge


def decode(y,scale,template):
    ns=len(template['solution']['s']);nr=2*(ns-1);x=[a*b for a,b in zip(y,scale)]
    assert len(x)==nr+3*ns
    return dict(r=[template['instance']['r0']]+[x[i:i+2] for i in range(0,nr,2)]+[template['instance']['rf']],
                e=[template['phys']['e_max']]+x[nr:nr+ns],s=x[nr+ns:nr+2*ns],c=x[nr+2*ns:])


def psi(value):
    return 0. if value<=-.001 else (value+.001)**2/.004 if value<=.001 else value


def softmin(values,p):
    low=min(values);return low*sum((low/z)**p for z in values)**(-1/p)


def rows(data,eps,p,mu):
    tr,ph,inst=data['solution'],data['phys'],data['instance'];ns=len(tr['s']);flight_range=ph['v_d']/ph['zeta']
    eq=[];ineq=[]
    def equal(kind,index,value,scale):eq.append(dict(kind=kind,index=index,value=value,physical=value*scale))
    def bound(kind,index,value,scale,dual):
        ineq.append(dict(kind=kind,index=index,value=value,physical=value*scale,dual=dual,
                         complementarity=abs(min(dual,-value))))
    for k in range(ns):
        residual=tr['e'][k+1]-signed_charge(ph,tr['e'][k],tr['c'][k])+ph['zeta']*(tr['s'][k]-tr['c'][k])
        equal('dynamics',k,flight_range*residual,1/flight_range)
    for i,task in enumerate(inst['tasks']):
        z=[math.sqrt(math.dist(pos,task)**2+eps**2) for pos in tr['r']]
        equal('task',i,softmin(z,p)-eps,1.)
    for k in range(ns):
        a,b=tr['r'][k:k+2];s,c=tr['s'][k],tr['c'][k];z=[math.hypot(c,eps)]
        for region in inst['regions']:
            v=[psi(math.dist(a,region['o'])-region['rho']),psi(math.dist(b,region['o'])-region['rho']),psi(math.dist(a,b)-ph['v_c']*s)]
            z.append(math.sqrt((c-s)**2+sum(t*t for t in v)+eps**2))
        equal('mode',k,softmin(z,p)-eps,1.)
    for k in range(ns):
        dist=math.dist(*tr['r'][k:k+2]);s=tr['s'][k];denom=math.sqrt(dist**2+.001**2)+math.sqrt((ph['v_d']*s)**2+.001**2)
        bound('speed_squared',k,dist**2-ph['v_d']**2*s*abs(s),1.,mu[k]/denom)
    for block,kind,scale in [(1,'energy_lower',flight_range),(2,'energy_upper',flight_range),
                             (3,'duration_lower',ph['v_d']),(4,'duration_upper',ph['v_d']),(5,'charge_lower',ph['v_d'])]:
        for k in range(ns):
            raw={'energy_lower':ph['e_min']-tr['e'][k+1],'energy_upper':tr['e'][k+1]-ph['e_max'],
                 'duration_lower':ph['s_min']-tr['s'][k],'duration_upper':tr['s'][k]-ph['s_max'],'charge_lower':-tr['c'][k]}[kind]
            bound(kind,k,scale*raw,1/scale,mu[block*ns+k]/scale)
    return eq,ineq


def domain_distance(a,b):
    return max(0.,math.dist(a['center'],b['center'])-a['radius']-b['radius'])


def branch_bounds(data):
    inst,ph=data['instance'],data['phys'];modes=data['modes'];stamps=data['task_stamp'];ns=len(modes)
    def fixed(point,label):return dict(center=point,radius=0.,label=label)
    def region(index):
        r=inst['regions'][index];return dict(center=r['o'],radius=r['rho'],label='region'+str(index))
    runs=[];start=0
    while start<ns:
        if modes[start]>=0:start+=1;continue
        end=start
        while end+1<ns and modes[end+1]<0:end+=1
        left=fixed(inst['r0'],'start') if start==0 else region(modes[start-1])
        right=fixed(inst['rf'],'finish') if end==ns-1 else region(modes[end+1])
        tasks=sorted([(stamp,i) for i,stamp in enumerate(stamps) if start<=stamp<=end+1])
        nodes=[left]+[fixed(inst['tasks'][i],'task'+str(i)) for _,i in tasks]+[right]
        distances=[domain_distance(a,b) for a,b in zip(nodes,nodes[1:])]
        lower=sum(distances);capacity=ph['v_d']*(ph['e_max']-ph['e_min'])/ph['zeta']
        runs.append(dict(start_segment=start,end_segment=end,task_ids=[i for _,i in tasks],nodes=nodes,
             leg_lower_bounds_km=distances,flight_lower_bound_km=lower,full_battery_range_km=capacity,
             excess_km=lower-capacity,infeasible_branch_proven=lower>capacity+1e-6))
        start=end+1
    return runs
