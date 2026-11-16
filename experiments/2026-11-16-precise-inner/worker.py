import json
import os
from pathlib import Path
import sys
from time import monotonic
import numpy as np
import helpers as h
from precision import DecimalEvaluator
from inner import solve

BASE=Path(__file__).resolve().parent


def context():
    case=os.environ['UAV_R2_CASE'];targets=json.loads((BASE/'targets.json').read_text())
    target=next(t for t in targets['contexts'] if t['case']==case)
    metadata=json.loads((h.ROOT/target['metadata_source']).read_text())['metadata']
    prior=json.loads((h.ROOT/target['result']).read_text());data=np.load(h.ROOT/target['samples'])
    state=dict(json.loads((h.ROOT/prior['source']).read_text()),y=data['y'].tolist())
    frozen=h.stage4.Frozen(state);y=data['y'].copy();data.close()
    return case,targets,metadata,frozen,y


def check_gradient():
    case,targets,metadata,frozen,y=context();spec=targets['gradient_check'];start=monotonic();deadline=start+120
    a=DecimalEvaluator(metadata,spec['digits'],spec['step']);b=DecimalEvaluator(metadata,spec['reference_digits'],spec['reference_step'])
    va,ga,ea=a(y,deadline);vb,gb,eb=b(y,deadline);_,native=frozen.eval(y)
    error=float(max(abs(ga-gb)));native_error=float(max(abs(native-gb)))
    result=dict(case=case,y=y.tolist(),value_80=str(ea),value_100=str(eb),gradient_80=ga.tolist(),gradient_100=gb.tolist(),
        native_gradient=native.tolist(),gradient_inf_80=float(max(abs(ga))),gradient_inf_100=float(max(abs(gb))),
        comparison_error_inf=error,native_error_inf=native_error,passed=error<=spec['max_inf_difference'],
        scalar_evaluations=a.calls+b.calls,seconds=monotonic()-start,optimizer_launched=False)
    frozen.close();(BASE/'gradient-checks'/f'{case}.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ['case','comparison_error_inf','native_error_inf','gradient_inf_100','passed','seconds']}),flush=True)


def run_inner():
    case,targets,metadata,frozen,y=context();method=os.environ['UAV_INNER_METHOD'];folder=BASE/'inner'/f'{case}-{method}'
    folder.mkdir(exist_ok=False);kernel=None
    if method=='decimal':kernel=DecimalEvaluator(metadata);evaluate=kernel
    else:
        assert method=='native'
        def evaluate(point,deadline):
            if monotonic()>=deadline:raise TimeoutError()
            value,gradient=frozen.eval(point);return value,gradient,None
    def hessian(point,counts):return h.decomposition.hessian_of_al(frozen,point,1e-7,counts)[0]
    start=monotonic()
    with (folder/'trace.jsonl').open('x') as trace:
        try:result=solve(evaluate,hessian,y.copy(),start+30.,lambda r:trace.write(json.dumps(r)+'\n'))
        except TimeoutError:
            result=dict(y=y.tolist(),gradient=None,status='initial_gradient_timeout',accepted=0,
                gradient_inf=None,value=None,value_decimal=None,seconds=monotonic()-start)
    result.update(case=case,method=method,rho=metadata['rho'],frozen_al_only=True,
        decimal_scalar_evaluations=0 if kernel is None else kernel.calls)
    frozen.close();(folder/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ['case','method','status','accepted','gradient_inf','seconds','decimal_scalar_evaluations']}),flush=True)


if __name__=='__main__':check_gradient() if '--check-gradient' in sys.argv else run_inner()
