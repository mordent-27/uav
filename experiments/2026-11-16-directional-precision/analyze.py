import json
from pathlib import Path
import numpy as np

BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[1]


def main():
    rows=[];table=['# 最後のTR方向に沿うモデルと値差','',
        '| 入力 | 幅 | AL値差 | モデル値差 | 勾配差分の曲率相対誤差 | 活性切替（正/負） |',
        '|---|---:|---:|---:|---:|---|']
    for folder in sorted((BASE/'states').glob('*/')):
        r=json.loads((folder/'result.json').read_text());data=np.load(folder/'samples.npz')
        state=json.loads((ROOT/r['source']).read_text());ld=np.longdouble
        h0,g0=data['h0'].astype(ld),data['g0'].astype(ld)
        le=np.array(state['lam'],dtype=ld)+ld(r['rho'])*h0
        mi=np.maximum(0,np.array(state['mu'],dtype=ld)+ld(r['rho'])*g0)
        jac=data['jac'].astype(ld);ns=r['n_segments'];small=[];witnesses=[]
        for sample in r['rows']:
            if sample['width']<=1e-10 and sample['direction']!='min_eigenvector':
                for sign in ['plus','minus']:
                    q=sample[sign];i=q['point_index'];delta=(data['points'][i]-data['y']).astype(ld)
                    rh=data['hs'][i].astype(ld)-h0-jac[:len(h0)]@delta
                    rg=data['gs'][i].astype(ld)-g0-jac[len(h0):]@delta
                    battery=float(le[:ns]@rh[:ns]);affine=float(mi[ns:]@rg[ns:])
                    small.append(dict(direction=sample['direction'],width=sample['width'],side=sign,
                        stable=q['stable'],model=q['model'],model_error=q['model_error'],
                        battery_weighted_residual=battery,affine_bound_rounding=affine,
                        model_error_after_removing_battery_and_affine_residual=q['model_error']-battery-affine))
            if sample['direction']=='last_tr_step' and sample['width'] in [1e-6,1e-8,1e-9,1e-10,1e-12]:
                error=abs(sample['gradient_fd_curvature']-sample['model_curvature'])/max(abs(sample['model_curvature']),1.)
                q=sample['plus'];table.append(f"| {r['case']} | {sample['width']:.0e} | {q['stable']:.6e} | {q['model']:.6e} | {error:.3e} | {q['active_switches']}/{sample['minus']['active_switches']} |")
                witnesses.append(dict(width=sample['width'],gradient_slope=sample['gradient_slope'],
                    stable_fd_slope=sample['stable_fd_slope'],model_curvature=sample['model_curvature'],
                    gradient_fd_curvature=sample['gradient_fd_curvature'],curvature_relative_error=error,
                    plus=q,minus=sample['minus']))
        rows.append(dict(case=r['case'],rho=r['rho'],gradient_inf=r['gradient_inf'],
            max_abs_weighted_affine_rounding=max(abs(x['affine_bound_rounding']) for x in small),
            max_abs_battery_weighted_residual=max(abs(x['battery_weighted_residual']) for x in small),
            max_abs_model_error=max(abs(x['model_error']) for x in small),
            max_abs_model_error_after_residual_removal=max(abs(x['model_error_after_removing_battery_and_affine_residual']) for x in small),
            small_width_samples=small,last_tr_witnesses=witnesses))
        data.close()
    summary=dict(states=2,directions=10,direction_width_pairs=130,perturbed_points=260,
        execution_seconds=json.loads((BASE/'execution.json').read_text())['seconds'],rows=rows,
        optimizer_launched=False,affine_residual_has_no_mathematical_nonlinearity=True,
        battery_residual_can_include_nonlinearity=True)
    (BASE/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    (BASE/'comparison.md').write_text('\n'.join(table)+'\n')
    print(json.dumps([{k:v for k,v in r.items() if k not in ['small_width_samples','last_tr_witnesses']} for r in rows]))


if __name__=='__main__':main()
