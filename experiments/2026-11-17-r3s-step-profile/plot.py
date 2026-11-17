import json
import os
from pathlib import Path
os.environ.setdefault('MPLCONFIGDIR','/tmp/uav-step-profile-matplotlib')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

BASE=Path(__file__).resolve().parent
cases=json.loads((BASE/'summary.json').read_text())['cases']
groups=[('Curvature finite differences',['curvature_fd_ns'],'#4477aa'),
        ('Jacobian',['jacobian_ns'],'#66ccee'),('Hessian setup / assembly',['hessian_setup_ns','hessian_assembly_ns'],'#228833'),
        ('Eigendecomposition',['eigh_ns'],'#ccbb44'),('Search',['search_ns'],'#ee6677'),
        ('Initial evaluation / other',['initial_eval_ns','other_ns'],'#bbbbbb')]
fig,ax=plt.subplots(figsize=(10,3.9),layout='constrained');left=[0]*len(cases)
for label,keys,color in groups:
    values=[100*sum(r['parts'][k]['share'] for k in keys) for r in cases]
    ax.barh(range(len(cases)),values,left=left,label=label,color=color)
    left=[a+b for a,b in zip(left,values)]
ax.set(yticks=range(len(cases)),yticklabels=[r['case'] for r in cases],xlim=(0,100),
       xlabel='Share of instrumented time across 21 repeats [%]',title='Fixed-state first step; one process, one BLAS thread')
ax.invert_yaxis();ax.legend(loc='upper center',bbox_to_anchor=(.5,-.22),ncol=2,fontsize=8)
fig.savefig(BASE/'step-profile.png',dpi=180);fig.savefig(BASE/'step-profile.pdf');plt.close(fig)
print('step-profile.png, step-profile.pdf')
