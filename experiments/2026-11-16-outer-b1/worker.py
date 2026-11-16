"""Stage 13 from the saved R3 stage-13 initial point with inner L / A0 / B1. Writes outer rows, inner traces and the final state."""
import gzip
import importlib.util
import json
import os
from pathlib import Path
import sys
from time import monotonic
import numpy as np
import helpers as h
import stage

BASE=Path(__file__).resolve().parent


def _load(name,path):
    if name in sys.modules:
        assert Path(sys.modules[name].__file__).resolve()==path.resolve(),name
        return sys.modules[name]
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module;spec.loader.exec_module(module);return module


loop=_load('loop',BASE.parent/'2026-11-16-accept-stop/loop.py')
accept=_load('accept_stop_worker',BASE.parent/'2026-11-16-accept-stop/worker.py')
kink=accept.kink
newton=h.load('newton')


def frozen_for(context):
    f=h.stage4.Frozen(context);f.m.current_stage=context['stage'];return f


def make_inner(arm,targets,tasks,counters):
    digits=targets['digits']
    def native(f,context,y,deadline,record):
        r=newton.solve(f,y,deadline,record);return r
    def modern(f,context,y,deadline,record):
        exact=None
        if arm=='B1':
            metadata=accept.native_metadata(f,context,tasks)
            def exact(point):
                counters['decimal']+=1
                return kink.piece_al(kink.reference.evaluate(kink.lowcurv.to_decimal(point),metadata,digits),metadata,digits)
        def evaluate(point,dl):
            if monotonic()>=dl:raise TimeoutError()
            v,g=f.eval(point);return v,np.array(g,dtype=float).copy()
        def hessian(point,counts):return h.decomposition.hessian_of_al(f,point,targets['hessian_step'],counts)[0]
        r=loop.solve(evaluate,hessian,y,deadline,record,exact_value=exact,floor_stop=arm=='B1',tol=targets['inner_tolerance'],factor=targets['floor_factor'])
        r['y']=np.array(r['y']);r['gradient']=np.array(r['gradient']);return r
    return native if arm=='L' else modern


def main():
    case=os.environ['UAV_R2_CASE'];arm=os.environ['UAV_ARM'];assert arm in ('L','A0','B1')
    targets=json.loads((BASE/'targets.json').read_text());row=next(r for r in targets['states'] if r['case']==case)
    initial=json.loads((h.ROOT/row['initial']).read_text());assert initial['stage']==13 and initial['rho']==1e4
    tasks=next(json.loads(s)['tasks'] for s in (h.ROOT/row['full_precision_tasks']).read_text().splitlines() if json.loads(s)['case']==case)
    folder=BASE/'stages'/f'{case}-{arm}';folder.mkdir(parents=True,exist_ok=False);logs=BASE/'inner-logs'/f'{case}-{arm}';logs.mkdir(parents=True,exist_ok=False)
    y=np.array(initial['y']);lam,mu=np.zeros(len(initial['lam'])),np.zeros(len(initial['mu']))
    assert not np.any(initial['lam']) and not np.any(initial['mu'])
    context=h.state(y,lam,mu,1e4,13);f=frozen_for(context);v,_=f.eval(y)
    meta=accept.native_metadata(f,context,tasks);d=kink.piece_al(kink.reference.evaluate(kink.lowcurv.to_decimal(y),meta,targets['digits']),meta,targets['digits'])
    gap=abs(float(d)-v)/max(1.,abs(v));f.close()
    if arm=='B1':assert gap<=targets['decimal_value_gap'],gap
    counters=dict(decimal=0);inner=make_inner(arm,targets,tasks,counters)
    outer_log=gzip.open(folder/'outer.jsonl.gz','wt')
    def on_row(r):outer_log.write(json.dumps(r,allow_nan=False)+'\n');outer_log.flush()
    open_logs=[]
    def inner_record(outer):
        stream=gzip.open(logs/f'inner{outer:04d}.jsonl.gz','wt',compresslevel=1);open_logs.append(stream)
        return lambda r:stream.write(json.dumps(r)+'\n')
    start=monotonic()
    rows,final=stage.run_stage(y,lam,mu,1e4,13,frozen_for,inner,h.assess,h.state,targets['stage_tolerance'],targets['outer_cap'],targets['seconds'],on_row,inner_record)
    outer_log.close()
    for s in open_logs:s.close()
    statuses={}
    for r in rows:statuses[r['inner']['status']]=statuses.get(r['inner']['status'],0)+1
    final.update(case=case,arm=arm,decimal_value_gap_at_start=gap,decimal_calls=counters['decimal'],inner_statuses=statuses,wall_seconds=monotonic()-start,
        max_common_kkt=max(final['common_kkt'].values()),max_paper_kkt=max(final['paper_units_kkt'].values()),outer_logs=len(open_logs))
    (folder/'result.json').write_text(json.dumps(final,indent=2)+'\n')
    print(json.dumps({k:final[k] for k in ['case','arm','stop','completed_outer','stage_pass','max_common_kkt','max_paper_kkt','objective','rho','seconds','inner_statuses','decimal_calls']}),flush=True)


if __name__=='__main__':main()
