import csv
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import numpy as np

BASE=Path(__file__).resolve().parent;ROOT=BASE.parents[1]


def main():
    from analyze import verify_sources
    verify_sources();summary=json.loads((BASE/'summary.json').read_text())
    with (BASE/'cases.csv').open() as stream:cases=list(csv.DictReader(stream))
    with (ROOT/'data/paper_fig3.csv').open() as stream:paper=list(csv.DictReader(stream))
    own={t:[float(r['objective_h']) for r in cases if int(r['tau'])==t and r['objective_h']] for t in range(1,10)}
    ref={t:[float(r['value']) for r in paper if r['quantity']=='objective_h' and r['method']=='NLP' and int(r['tau'])==t] for t in range(1,10)}
    blue,orange,green='#2c6ba0','#c85827','#3b8656'
    plt.rcParams.update({'font.size':10,'svg.fonttype':'none','svg.hashsalt':'r3s-paper-20261117'})
    fig,axes=plt.subplots(1,2,figsize=(14.4,5.8),gridspec_kw={'width_ratios':[1.65,1]})
    for values,color,offset in [(ref,blue,-.18),(own,orange,.18)]:
        box=axes[0].boxplot([values[t] for t in range(1,10)],positions=np.arange(1,10)+offset,
            widths=.29,whis=(10,90),showfliers=True,patch_artist=True,manage_ticks=False,
            medianprops={'color':'#222222','linewidth':1.4},flierprops={'markersize':2,'markeredgecolor':color,'alpha':.4})
        for patch in box['boxes']:patch.set_facecolor(color);patch.set_alpha(.65)
    axes[0].set_xticks(range(1,10),[f'{t}\nn={len(own[t])}' for t in range(1,10)])
    axes[0].set(xlabel='Tasks (n = number of feasible returned points)',ylabel='Mission time (h)',
        title='Objective distributions: Q25 / median / Q75; whiskers P10 / P90')
    axes[0].legend(handles=[Patch(facecolor=blue,alpha=.65,label='Paper NLP: 100 plotted points/task'),
        Patch(facecolor=orange,alpha=.65,label='R3/R3s: feasible returned points')],loc='upper left',fontsize=9)
    groups=summary['groups'];tau=np.arange(1,10)
    ratios=[g['median_ratio'] for g in groups]
    cert=[g['certified_objective']['median']/g['paper']['NLP']['median'] for g in groups]
    rule=[g['by_origin']['2026-11-16-r3s-cohort']['median']/g['paper']['NLP']['median'] for g in groups]
    axes[1].fill_between(tau,[g['missing_median_ratio_lower'] for g in groups],
        [g['missing_median_ratio_upper'] for g in groups],color=orange,alpha=.16,label='All-100 median bounds for missing values')
    axes[1].plot(tau,ratios,'o-',color=orange,label='All feasible returns (894)')
    axes[1].plot(tau,cert,'s--',color=green,markersize=4,label='Fixed-branch KKT subset (830)')
    axes[1].plot(tau,rule,':',color='#815c99',label='Rule cohort only (870 returns)')
    axes[1].axhline(1,color='#555555',linewidth=1,linestyle='--')
    axes[1].set(xticks=tau,xlabel='Tasks',ylabel='Median / paper NLP median',title='Unpaired ratios of medians')
    axes[1].legend(fontsize=8.4,loc='upper left')
    for ax in axes:ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True)
    fig.subplots_adjust(bottom=.2,top=.89,left=.06,right=.98,wspace=.22)
    fig.text(.06,.045,'Different input populations and solvers. R3/R3s combines 24 old-entry and 876 rule-entry cases.\nSix cases returned no feasible point; objective medians are conditional. Bounds are sensitivity ranges, not confidence intervals.',fontsize=9)
    for ext in ['png','svg']:fig.savefig(BASE/f'objective-distributions.{ext}',dpi=180,metadata={'Date':None} if ext=='svg' else None)
    plt.close(fig)

    fig,axes=plt.subplots(3,3,figsize=(12.5,10.2),sharey=True)
    for t,ax in enumerate(axes.flat,1):
        limit=1.04*max(max(own[t]),max(ref[t]))
        for values,color,label in [(ref[t],blue,'Paper NLP plotted'),(own[t],orange,'R3/R3s feasible return')]:
            a=np.sort(values);x=np.r_[0,a,limit];y=np.r_[0,np.arange(1,len(a)+1)/100,len(a)/100]
            ax.step(x,y,where='post',color=color,linewidth=1.5,label=label)
        ax.set(title=f'Tasks = {t}; returned {len(own[t])}/100',xlim=(0,limit),ylim=(0,1.025))
        ax.grid(alpha=.2)
    for ax in axes[-1]:ax.set_xlabel('Mission time (h)')
    for ax in axes[:,0]:ax.set_ylabel('Fraction of all 100 instances')
    handles,labels=axes.flat[0].get_legend_handles_labels();fig.legend(handles,labels,loc='upper center',ncol=2,bbox_to_anchor=(.5,.99))
    fig.subplots_adjust(top=.93,bottom=.105,left=.075,right=.98,wspace=.16,hspace=.3)
    fig.text(.075,.025,'Unreturned cases have mass at +infinity, so the orange curve may stop below 1.\nPaper points are all plotted NLP objectives; their feasibility is not linked to this panel. Input instances are not paired.',fontsize=9)
    for ext in ['png','svg']:fig.savefig(BASE/f'objective-ecdf.{ext}',dpi=180,metadata={'Date':None} if ext=='svg' else None)
    plt.close(fig);verify_sources()


if __name__=='__main__':main()
