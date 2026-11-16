import json
import os
from pathlib import Path
import sys
from decimal import Decimal as D,localcontext
import numpy as np
import helpers as h
from reference import binary,constraints,delta

BASE=Path(__file__).resolve().parent


def compute(case):
    targets=json.loads((BASE/'targets.json').read_text())
    target=next(t for t in targets['contexts'] if t['case']==case)
    prior=json.loads((h.ROOT/target['result']).read_text());data=np.load(h.ROOT/target['samples'])
    state=dict(json.loads((h.ROOT/prior['source']).read_text()),y=data['y'].tolist())
    f=h.stage4.Frozen(state);assert np.all(f.m.ratio==1.)
    ph=dict(f.m.source['phys']);ph.update(range=ph['v_d']/ph['zeta'],
        sigma=(ph['e_max']-ph['e_th'])/ph['kappa'],span=ph['e_max']-ph['e_th'])
    metadata=dict(phys=ph,scale=f.m.scale.tolist(),wh=f.m.wh.tolist(),wg=f.m.wg.tolist(),
        n_segments=f.m.stamps-1,lam=state['lam'],mu=state['mu'],rho=state['rho'])
    ns=metadata['n_segments'];baseline={digits:constraints(data['y'],metadata,digits) for digits in targets['precisions']}
    max_native_error=0.;max_precision_disagreement=D(0);rows=[]
    for actual,stored in [(baseline[80][0],data['h0'][:ns]),(baseline[80][1],data['g0'][ns:])]:
        error=max(float(abs(a-binary(b))) for a,b in zip(actual,stored));max_native_error=max(max_native_error,error)
    with localcontext() as ctx:
        ctx.prec=80
        for row in prior['rows']:
            if row['direction']!=targets['direction'] or row['width'] not in targets['widths']:continue
            for side in ['plus','minus']:
                item=row[side];i=item['point_index'];point=data['points'][i]
                computed={digits:constraints(point,metadata,digits) for digits in targets['precisions']}
                diffs={digits:delta(*baseline[digits],*computed[digits],metadata,digits) for digits in targets['precisions']}
                discrepancy=max(abs(a-b) for a,b in zip(diffs[80],diffs[100]))
                assert discrepancy<D('1e-60'),discrepancy
                max_precision_disagreement=max(max_precision_disagreement,discrepancy)
                for actual,stored in [(computed[80][0],data['hs'][i][:ns]),(computed[80][1],data['gs'][i][ns:])]:
                    error=max(float(abs(a-binary(b))) for a,b in zip(actual,stored));max_native_error=max(max_native_error,error)
                native=delta([binary(x) for x in data['h0'][:ns]],[binary(x) for x in data['g0'][ns:]],
                    [binary(x) for x in data['hs'][i][:ns]],[binary(x) for x in data['gs'][i][ns:]],metadata,80)
                correction=sum(diffs[80])-sum(native)
                partial=binary(item['stable'])+correction
                rows.append(dict(width=row['width'],side=side,point_index=i,
                    native_stable_delta=item['stable'],model_delta=item['model'],
                    native_battery_delta=str(native[0]),reference_battery_delta=str(diffs[80][0]),
                    native_bounds_delta=str(native[1]),reference_bounds_delta=str(diffs[80][1]),
                    precision_disagreement=str(discrepancy),component_correction=str(correction),
                    partially_corrected_delta=str(partial),partially_corrected_delta_float=float(partial)))
    assert len(rows)==6 and max_native_error<2e-14,max_native_error
    data.close();f.close()
    return dict(case=case,metadata=metadata,anchor_and_trial_points=7,rows=rows,
        max_constraint_difference_from_native=max_native_error,max_80_100_digit_disagreement=str(max_precision_disagreement),
        optimizer_launched=False,gradient_changed=False,remaining_constraints_high_precision=False)


def main():
    case=os.environ['UAV_R2_CASE'];result=compute(case);out=BASE/'cases'/case
    if '--verify' in sys.argv:
        assert result==json.loads((out/'result.json').read_text())
        (BASE/'reverification'/f'{case}.json').write_text(json.dumps(dict(case=case,
            points_rechecked=7,all_component_values_reproduced=True,optimizer_launched=False),indent=2)+'\n')
    else:
        out.mkdir(exist_ok=False);(out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ['case','max_constraint_difference_from_native','max_80_100_digit_disagreement']}),flush=True)


if __name__=='__main__':main()
