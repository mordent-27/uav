import hashlib
import importlib.util
import json
import os
from pathlib import Path
from time import monotonic
import numpy as np
import helpers as h
import inner_cg

BASE=Path(__file__).resolve().parent


def main():
    case=os.environ['UAV_R2_CASE'];method=os.environ['UAV_INNER_METHOD']
    source=h.ROOT/'experiments/2026-11-16-r3a-cohort/cases/G'/case/'stages/stage13/checkpoint.json'
    raw=source.read_bytes();state=json.loads(raw);f=h.stage4.Frozen(state)
    y=np.array(state['y']);initial_value,initial_gradient=f.eval(y)
    folder=BASE/'inner'/f'{case}-{method}';folder.mkdir(exist_ok=False)
    if method=='dense':
        spec=importlib.util.spec_from_file_location('old_inner_newton',h.ROOT/'experiments/2026-11-15-decomposed-follow/newton.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);solve=module.solve
    else:
        assert method=='cg';solve=inner_cg.solve
    with (folder/'trace.jsonl').open('x') as log:
        def record(row):log.write(json.dumps(row)+'\n')
        result=solve(f,y.copy(),monotonic()+30.,record)
    result['y']=result['y'].tolist();result['gradient']=result['gradient'].tolist()
    value,gradient=f.eval(np.array(result['y']))
    np.testing.assert_allclose(value,result['value'],atol=1e-9,rtol=1e-10)
    np.testing.assert_allclose(gradient,result['gradient'],atol=1e-9,rtol=1e-9)
    result.update(case=case,method=method,source=str(source.relative_to(h.ROOT)),
        source_sha256=hashlib.sha256(raw).hexdigest(),rho=state['rho'],
        initial_value=float(initial_value),initial_gradient_inf=float(max(abs(initial_gradient))),
        al_decrease=float(initial_value-value),fixed_multiplier_and_rho=True,
        source_unchanged=source.read_bytes()==raw,
        final_metrics=f.m.metrics(np.array(result['y']),np.array(state['lam']),np.array(state['mu'])))
    f.close();assert result['source_unchanged']
    (folder/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ['case','method','status','accepted','gradient_inf','al_decrease','seconds']}),flush=True)


if __name__=='__main__':main()
