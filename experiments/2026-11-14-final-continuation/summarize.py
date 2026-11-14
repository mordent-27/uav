"""Summarize saved continuation traces and draw the scalar-law comparison."""
import csv
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE=Path(__file__).resolve().parent


def read_rows(path):return [json.loads(s) for s in path.read_text().splitlines()]


def main():
    rows=[]
    for name in ['tau1-seed1','tau3-seed0','fig1','tau1-seed2']:
        p=HERE/'cases'/name
        result=json.loads((p/'result.json').read_text());initial=json.loads((p/'initial.json').read_text())
        rows.append(dict(case=name,phase='original Hessian step',stop=result['stop'],extra_outer=result['extra_outer'],
            extra_seconds=result['extra_seconds'],total_outer=result['total_outer'],
            prediction=initial['predicted_extra_outer'],stat=result['original_kkt']['stat'],feas=result['original_kkt']['feas'],
            comp=result['original_kkt']['comp'],objective=result['objective'],
            original_violation=result['original_violation'],battery_violation=result['physical_audit']['replay_violation']))
    for directory in ['fig1-refined','fig1-accurate']:
        p=HERE/directory/'result.json'
        if p.exists():
            result=json.loads(p.read_text());rows.append(dict(case='fig1',phase=directory,stop=result['stop'],
                extra_outer=result['extra_outer'],extra_seconds=result['extra_seconds'],total_outer=result['total_outer'],
                prediction=None,stat=result['original_kkt']['stat'],feas=result['original_kkt']['feas'],comp=result['original_kkt']['comp'],
                objective=result['objective'],original_violation=result['original_violation'],
                battery_violation=result['physical_audit']['replay_violation']))
    with (HERE/'summary.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');writer.writeheader();writer.writerows(rows)
    fig,axes=plt.subplots(1,2,figsize=(11,4.2),layout='constrained')
    for name,color in [('tau1-seed1','#3673b9'),('tau3-seed0','#328443'),('fig1','#bd6435')]:
        p=HERE/'cases'/name;initial=json.loads((p/'initial.json').read_text());trace=read_rows(p/'outer.jsonl')
        values=[initial['original_kkt']['feas']]+[r['original_kkt']['feas'] for r in trace]
        if name=='fig1':
            for directory in ['fig1-refined','fig1-accurate']:
                path=HERE/directory/'outer.jsonl'
                if path.exists():values.extend(r['original_kkt']['feas'] for r in read_rows(path))
        x=np.arange(len(values));axes[0].plot(x,values,color=color,label=name)
        curve=np.linspace(0,max(len(values)-1,initial['predicted_extra_outer']),250)
        h,lam=initial['worst_mode_h'],initial['lambda_at_row']
        estimate=h*(1+3*1e4*h/lam*curve)**(-2/3)
        axes[0].plot(curve,estimate,color=color,ls='--',alpha=.55)
    bad=read_rows(HERE/'cases/tau1-seed2/outer.jsonl')
    for key,label in [('feas','Feasibility'),('stat','Stationarity')]:
        axes[1].plot([r['extra_outer'] for r in bad],[r['original_kkt'][key] for r in bad],label=label)
    for ax in axes:
        ax.axhline(1e-6,color='black',ls=':',label='Tolerance 1e-6')
        ax.set_yscale('log');ax.set_xlabel('Additional AL outer iterations');ax.grid(alpha=.2);ax.legend(fontsize=8)
    axes[0].set_ylabel('Original-representation feasibility residual')
    axes[0].set_title('Selected near-feasible states; dashed = scalar estimate',fontsize=10)
    axes[1].set_ylabel('Original-representation KKT residual')
    axes[1].set_title('Route with charging stops already lost',fontsize=10)
    fig.savefig(HERE/'continuation.png',dpi=180);fig.savefig(HERE/'continuation.svg')
    p=HERE/'continuation.svg';p.write_text('\n'.join(s.rstrip() for s in p.read_text().splitlines())+'\n')
    print(json.dumps(rows,indent=2))


if __name__=='__main__':main()
