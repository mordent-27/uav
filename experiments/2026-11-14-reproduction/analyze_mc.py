"""Summarize completed 9x100 baseline and compare distributions with digitized Fig.3."""
import csv
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]


def main():
    with (HERE/'mc-original/results.csv').open() as handle:rows=list(csv.DictReader(handle))
    assert len(rows)==900
    with (ROOT/'data/paper_fig3.csv').open() as handle:paper=list(csv.DictReader(handle))
    groups=[]
    for tau in range(1,10):
        data=[v for v in rows if int(v['tau'])==tau]
        assert len(data)==100
        completed=[v for v in data if v['completed']=='True']
        reference={quantity:[float(v['value']) for v in paper if v['method']=='NLP' and
                             int(v['tau'])==tau and v['quantity']==quantity]
                   for quantity in ['objective_h','violation']}
        # Extraction names are verified explicitly; never silently compare empty samples.
        assert all(len(values)==100 for values in reference.values()), {k:len(v) for k,v in reference.items()}
        def number(key):return np.array([float(v[key]) for v in completed])
        objective,violation=number('objective'),number('original_violation')
        valid=[v for v in completed if v['original_violation_le_1e_3']=='True']
        groups.append(dict(tau=tau,planned=100,completed=len(completed),
            timed_out=sum(v['timed_out']=='True' for v in data),
            kkt_converged=sum(v['kkt_converged']=='True' for v in data),
            original_violation_le_1e_3=len(valid),
            physical_audit_pass=sum(v['physical_audit_pass']=='True' for v in data),
            median_objective=float(np.median(objective)),
            median_objective_passing=float(np.median([float(v['objective']) for v in valid])) if valid else None,
            median_paper_objective=float(np.median(reference['objective_h'])),
            objective_median_ratio=float(np.median(objective)/np.median(reference['objective_h'])),
            median_violation=float(np.median(violation)),max_violation=float(np.max(violation)),
            median_stat=float(np.median(number('stat'))),median_feas=float(np.median(number('feas'))),
            median_comp=float(np.median(number('comp'))),median_seconds=float(np.median(number('solver_seconds'))),
            paper_violation_le_1e_3=sum(v<=1e-3 for v in reference['violation'])))
    (HERE/'mc-comparison.json').write_text(json.dumps(groups,indent=2)+'\n')
    fields=list(groups[0])
    with (HERE/'mc-comparison.csv').open('w',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=fields);writer.writeheader();writer.writerows(groups)

    fig,axes=plt.subplots(1,3,figsize=(14,4.6),layout='constrained')
    colors=['#3673b9','#c45536']
    for ax,quantity,key in [(axes[0],'objective_h','objective'),(axes[1],'violation','original_violation')]:
        for method,color,offset in [('paper',colors[0],-.18),('Rust',colors[1],.18)]:
            values=[]
            for tau in range(1,10):
                if method=='paper':
                    vals=[float(v['value']) for v in paper if v['method']=='NLP' and int(v['tau'])==tau and v['quantity']==quantity]
                else:
                    vals=[float(v[key]) for v in rows if int(v['tau'])==tau and v['completed']=='True']
                values.append(np.maximum(vals,1e-16))
            box=ax.boxplot(values,positions=np.arange(1,10)+offset,widths=.3,patch_artist=True,
                           showfliers=False,manage_ticks=False)
            for patch in box['boxes']:patch.set_facecolor(color);patch.set_alpha(.6)
        ax.set_xticks(range(1,10));ax.set_xlabel('Number of tasks');ax.grid(axis='y',alpha=.2)
    axes[0].set_ylabel('Mission time (h), all completed outputs')
    axes[0].legend(handles=[Patch(color=colors[0],label='Paper NLP (digitized)'),
                            Patch(color=colors[1],label='Original Rust baseline')],fontsize=8)
    axes[1].set_yscale('log');axes[1].set_ylabel('Original constraint violation (mixed units)')
    axes[1].axhline(1e-3,color='gray',ls=':',lw=1)
    for name,label in [('stat','Stationarity'),('feas','Feasibility'),('comp','Complementarity')]:
        axes[2].plot(range(1,10),[max(v['median_'+name],1e-16) for v in groups],marker='o',label=label)
    axes[2].axhline(1e-6,color='black',ls=':',label='Local KKT tolerance')
    axes[2].set_yscale('log');axes[2].set_xlabel('Number of tasks');axes[2].set_ylabel('Median KKT residual, Rust baseline')
    axes[2].set_xticks(range(1,10));axes[2].legend(fontsize=8);axes[2].grid(alpha=.2)
    fig.suptitle('Independent random instances and solver settings; distribution comparison, not a matched replication',fontsize=11)
    fig.savefig(HERE/'mc-comparison.png',dpi=180)
    fig.savefig(HERE/'mc-comparison.svg')
    print(json.dumps(groups,indent=2))


if __name__=='__main__':main()
