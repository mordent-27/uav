"""Compare restoration costs and the independently checked frozen-branch bounds."""
import json
from pathlib import Path
import math

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from fixed_branch import restore_source,diag,ROOT,HERE

source=restore_source(json.loads((ROOT/'experiments/2026-11-14-final-continuation/fig1-accurate/raw.json').read_text()))
data=[('source',source)]+[(name,json.loads((HERE/(name+'.json')).read_text())) for name in ['timing','geometry']]
rows=[]
for name,d in data:
    p=d['phys'];tr=d['solution'];replay=diag.replay(d)
    rows.append(dict(name=name,objective=sum(tr['s']),min_replayed_energy=min(replay),max_replayed_energy=max(replay),
        replay_energy_violation=max([0.]+[max(p['e_min']-e,e-p['e_max']) for e in replay]),
        original_residuals=diag.residuals(d),charge_segments=sum(m>=0 for m in d['modes']),
        flight_hours=sum(s for s,m in zip(tr['s'],d['modes']) if m<0),
        charge_hours=sum(s for s,m in zip(tr['s'],d['modes']) if m>=0)))
bound=json.loads((HERE/'charging-bound.json').read_text())['affine_dual_lower_bound']
paper=1.8932
summary=dict(cases=rows,paper_readback_hours=paper,
    timing_cost_seconds=(rows[1]['objective']-rows[0]['objective'])*3600,
    geometry_gain_seconds=(rows[1]['objective']-rows[2]['objective'])*3600,
    net_cost_seconds=(rows[2]['objective']-rows[0]['objective'])*3600,
    optimistic_bound_hours=bound,
    frozen_branch_optimum_interval=[bound,rows[2]['objective']],
    maximum_possible_further_improvement_seconds=(rows[2]['objective']-bound)*3600,
    gap_to_paper_seconds=(rows[2]['objective']-paper)*3600,
    bound_above_paper_seconds=(bound-paper)*3600,
    gap_ratio=rows[2]['objective']/paper-1)
(HERE/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
fig,ax=plt.subplots(figsize=(9,4),layout='constrained')
items=[('Battery-free lower bound',json.loads((HERE/'travel-bound.json').read_text())['affine_dual_lower_bound']),
       ('Paper (digitized; different branch)',paper),('Max-rate battery lower bound',bound),
       ('Smoothed KKT point (battery-infeasible)',rows[0]['objective']),
       ('Exact modes, timing restored',rows[1]['objective']),('Exact modes, geometry reoptimized',rows[2]['objective'])]
ax.axvspan(bound,rows[2]['objective'],color='#66a277',alpha=.22,label='Frozen-branch optimum interval')
for i,(name,value) in enumerate(items):
    ax.scatter(value,i,color='#3673b9' if i in [0,2] else '#c45536' if i==1 else '#333333',s=45,zorder=3)
    ax.annotate(f'{value:.6f} h',(value,i),xytext=(7,0),textcoords='offset points',va='center',fontsize=9)
ax.set_yticks(range(len(items)),[name for name,_ in items]);ax.invert_yaxis();ax.set_xlim(1.70,2.18)
ax.set_xlabel('Mission time (hours)');ax.grid(axis='x',alpha=.2);ax.legend(loc='lower left',fontsize=8)
ax.set_title('Current visit/mode/region assignment and N=37 are fixed',fontsize=11)
fig.savefig(HERE/'restoration.png',dpi=180);fig.savefig(HERE/'restoration.svg')
p=HERE/'restoration.svg';p.write_text('\n'.join(line.rstrip() for line in p.read_text().splitlines())+'\n')
print(json.dumps(summary,indent=2))
