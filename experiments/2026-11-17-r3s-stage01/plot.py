import csv
from collections import Counter
import os
from pathlib import Path
os.environ.setdefault('MPLCONFIGDIR','/tmp/uav-stage01-matplotlib')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

BASE=Path(__file__).resolve().parent
with (BASE/'cases.csv').open() as stream:
    rows=[r for r in csv.DictReader(stream) if r['origin']=='2026-11-16-r3s-cohort']
fig,axes=plt.subplots(1,2,figsize=(11,5),layout='constrained')
ax=axes[0];bottom=[0]*9
for stop,label,color in [('kkt','Stage-1 common KKT','#228833'),('outer_limit','Advance after 10 outer steps','#4477aa'),('timeout','120 s timeout','#ee7733')]:
    counts=[sum(int(r['tau'])==tau and r['stage_stop']==stop for r in rows) for tau in range(1,10)]
    ax.bar(range(1,10),counts,bottom=bottom,label=label,color=color)
    bottom=[a+b for a,b in zip(bottom,counts)]
ax.set(xlabel='Number of tasks',ylabel='Cases (new 876 only)',xticks=range(1,10),title='Stage-1 exits; no new solves')
ax.legend(fontsize=8,loc='upper center',bbox_to_anchor=(.5,-.17))
ax=axes[1]
for target,label,color in [('False','Other 657 cases','#4477aa'),('True','Timeout 219 cases','#ee7733')]:
    sub=[r for r in rows if r['target']==target]
    ax.scatter([int(r['variables']) for r in sub],
               [float(r['inner_seconds'])/int(r['hessian_builds']) for r in sub],s=13,alpha=.45,color=color,label=label)
ax.set(xlabel='Number of variables',ylabel='Inner time / Hessian builds [s]',title='Includes all inner work; shared 8-worker timing')
ax.legend(fontsize=8);ax.grid(alpha=.2)
fig.savefig(BASE/'stage01-diagnosis.png',dpi=180)
fig.savefig(BASE/'stage01-diagnosis.pdf')
plt.close(fig)
print('stage01-diagnosis.png, stage01-diagnosis.pdf')
