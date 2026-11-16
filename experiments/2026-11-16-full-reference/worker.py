import json
import os
from pathlib import Path
import sys
from decimal import Decimal as D,localcontext
import numpy as np
import helpers as h
from battery_reference import binary
from reference import evaluate,al_difference

BASE=Path(__file__).resolve().parent


def compute(case):
    targets=json.loads((BASE/'targets.json').read_text());target=next(t for t in targets['contexts'] if t['case']==case)
    prior=json.loads((h.ROOT/target['result']).read_text());data=np.load(h.ROOT/target['samples'])
    state=dict(json.loads((h.ROOT/prior['source']).read_text()),y=data['y'].tolist())
    f=h.stage4.Frozen(state);assert np.all(f.m.ratio==1.)
    ns=f.m.stamps-1;assert np.all(f.m.wh[ns:]==1.)
    exported=[json.loads(s) for s in (h.ROOT/targets['full_precision_tasks']).read_text().splitlines()]
    tasks=next(r['tasks'] for r in exported if r['case']==case)
    rounded=f.m.source['instance']['tasks'];np.testing.assert_allclose(tasks,rounded,atol=5.1e-10,rtol=0.)
    instance=dict(f.m.source['instance'],tasks=tasks)
    ph=dict(f.m.source['phys']);ph.update(range=ph['v_d']/ph['zeta'],sigma=(ph['e_max']-ph['e_th'])/ph['kappa'],span=ph['e_max']-ph['e_th'])
    metadata=dict(phys=ph,scale=f.m.scale.tolist(),wh=f.m.wh.tolist(),wg=f.m.wg.tolist(),n_segments=ns,
        lam=state['lam'],mu=state['mu'],rho=state['rho'],eps=state['eps'],p=state['p'],smoothing_delta=1e-3,instance=instance)
    baseline={digits:evaluate(data['y'],metadata,digits) for digits in targets['precisions']}
    max_error=0.;max_delta_disagreement=D(0);rows=[]
    def constraint_error(evaluation,hn,gn):
        return max(float(abs(a-binary(b))) for actual,native in [(evaluation[1],hn),(evaluation[2],gn)] for a,b in zip(actual,native))
    max_error=constraint_error(baseline[80],data['h0'],data['g0'])
    with localcontext() as ctx:
        ctx.prec=100
        for row in prior['rows']:
            if row['direction']!=targets['direction'] or row['width'] not in targets['widths']:continue
            for side in ['plus','minus']:
                item=row[side];i=item['point_index'];point=data['points'][i]
                actual={digits:evaluate(point,metadata,digits) for digits in targets['precisions']}
                diffs={digits:al_difference(baseline[digits],actual[digits],metadata,digits) for digits in targets['precisions']}
                discrepancy=abs(diffs[80][0]-diffs[100][0]);assert discrepancy<D('1e-60'),discrepancy
                max_delta_disagreement=max(max_delta_disagreement,discrepancy)
                max_error=max(max_error,constraint_error(actual[80],data['hs'][i],data['gs'][i]))
                native=(D(0),[binary(x) for x in data['h0']],[binary(x) for x in data['g0']])
                native_trial=(D(0),[binary(x) for x in data['hs'][i]],[binary(x) for x in data['gs'][i]])
                _,native_parts=al_difference(native,native_trial,metadata,100)
                reference_value,parts=diffs[100]
                rows.append(dict(width=row['width'],side=side,point_index=i,native_stable_delta=item['stable'],
                    model_delta=item['model'],reference_delta=str(reference_value),reference_delta_float=float(reference_value),
                    precision_disagreement=str(discrepancy),parts={k:str(v) for k,v in parts.items()},
                    component_corrections={k:str(parts[k]-native_parts[k]) for k in ['battery','tasks','modes','speed','bounds']}))
    assert len(rows)==6 and max_error<2e-14,max_error
    directions=[data['directions'][0],data['directions'][1],np.eye(1,len(data['y']),int(np.argmax(abs(data['gradient']))))[0]]
    derivatives=[];max_derivative_disagreement=D(0)
    for name,v in zip(targets['derivative_directions'],directions):
        for displacement in targets['decimal_displacements']:
            values={}
            for digits in targets['precisions']:
                with localcontext() as ctx:
                    ctx.prec=digits;t=D(displacement);anchor=[binary(x) for x in data['y']];direction=[binary(x) for x in v]
                    plus=[y+t*d for y,d in zip(anchor,direction)];minus=[y-t*d for y,d in zip(anchor,direction)]
                    a=al_difference(baseline[digits],evaluate(plus,metadata,digits),metadata,digits)[0]
                    b=al_difference(baseline[digits],evaluate(minus,metadata,digits),metadata,digits)[0]
                    values[digits]=(a-b)/(2*t)
            with localcontext() as ctx:
                ctx.prec=100;discrepancy=abs(values[80]-values[100]);assert discrepancy<D('1e-45'),discrepancy
                max_derivative_disagreement=max(max_derivative_disagreement,discrepancy)
                native=sum((binary(g)*binary(d) for g,d in zip(data['gradient'],v)),D(0))
                derivatives.append(dict(direction=name,displacement=displacement,native_projection=str(native),
                    reference_derivative=str(values[100]),reference_derivative_float=float(values[100]),
                    difference_from_native=str(values[100]-native),precision_disagreement=str(discrepancy)))
    data.close();f.close()
    return dict(case=case,metadata=metadata,anchor_and_trial_points=7,rows=rows,derivatives=derivatives,
        max_constraint_difference_from_native=max_error,max_80_100_delta_disagreement=str(max_delta_disagreement),
        max_80_100_derivative_disagreement=str(max_derivative_disagreement),
        max_task_coordinate_loss_in_old_json=float(np.max(np.abs(np.array(tasks)-rounded))),
        optimizer_launched=False,all_constraints_high_precision=True,full_gradient_high_precision=False)


def main():
    case=os.environ['UAV_R2_CASE'];result=compute(case);out=BASE/'cases'/case
    if '--verify' in sys.argv:
        assert result==json.loads((out/'result.json').read_text())
        (BASE/'reverification'/f'{case}.json').write_text(json.dumps(dict(case=case,
            points_rechecked=7,derivative_pairs_rechecked=6,all_values_reproduced=True,optimizer_launched=False),indent=2)+'\n')
    else:
        out.mkdir(exist_ok=False);(out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ['case','max_constraint_difference_from_native','max_80_100_delta_disagreement','max_80_100_derivative_disagreement']}),flush=True)


if __name__=='__main__':main()
