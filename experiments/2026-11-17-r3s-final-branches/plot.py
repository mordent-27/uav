import json
import math
import os
from pathlib import Path
os.environ.setdefault('MPLCONFIGDIR','/tmp/uav-final-branches-matplotlib')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Circle

BASE=Path(__file__).resolve().parent
points=json.loads((BASE/'summary.json').read_text())['points']
final=[r for r in points if r['point']=='stage13']
fig,axes=plt.subplots(1,2,figsize=(11,5.2),layout='constrained')
for ax,r in zip(axes,final):
    bound=r['bounds'][0];nodes=bound['nodes'];path=[n['center'][:] for n in nodes[:-1]];target=nodes[-1]
    center=target['center'];last=path[-1];distance=math.dist(last,center)
    endpoint=last if distance<=target['radius'] else [c+target['radius']*(p-c)/distance for p,c in zip(last,center)]
    path.append(endpoint)
    ax.add_patch(Circle(center,target['radius'],facecolor='#66ccee',edgecolor='#0077bb',alpha=.35))
    ax.scatter(*center,color='#0077bb',marker='+');ax.annotate(target['label'],center,xytext=(5,5),textcoords='offset points',fontsize=9)
    ax.plot([p[0] for p in path],[p[1] for p in path],'-o',color='#cc3311',markersize=4,label='Shortest path through assigned tasks')
    for n in nodes[:-1]:ax.annotate(n['label'],n['center'],xytext=(5,5),textcoords='offset points',fontsize=9)
    actual=sum(math.dist(a,b) for a,b in zip(path,path[1:]));assert abs(actual-bound['flight_lower_bound_km'])<1e-10
    ax.set(title=r['case']+'\n'+f"Flight lower bound {actual:.2f} km > battery range 14.40 km",xlabel='x [km]',ylabel='y [km]')
    ax.set_aspect('equal',adjustable='datalim');ax.grid(alpha=.2);ax.margins(.15)
fig.suptitle('First discharge block: charging begins only after the blue region is reached',fontsize=11)
fig.savefig(BASE/'infeasible-flight-blocks.png',dpi=180);fig.savefig(BASE/'infeasible-flight-blocks.pdf');plt.close(fig)
print('infeasible-flight-blocks.png, infeasible-flight-blocks.pdf')
