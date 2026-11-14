"""Continue four frozen final AL states; fixed penalty, unchanged constraints/tolerances."""
from concurrent.futures import ThreadPoolExecutor,as_completed
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from time import monotonic

import numpy as np

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OLD=HERE.parent/'2026-11-14-conditioning'
sys.path.insert(0,str(OLD))
import newton_al as na
spec=importlib.util.spec_from_file_location('audit',ROOT/'experiments/2026-11-14-validation/audit.py')
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
CASES=['tau1-seed1','tau3-seed0','fig1','tau1-seed2']


def canonical(original,model,y,lam,mu):
    ns,nr=model.stamps-1,2*(model.stamps-2)
    x=y*model.scale
    doc=model.solution(y)
    r=np.vstack([doc['instance']['r0'],x[:nr].reshape(-1,2),doc['instance']['rf']])
    s=x[nr+ns:nr+2*ns]
    denominator=np.sqrt(np.sum(np.diff(r,axis=0)**2,axis=1)+.001**2)+np.sqrt((36*s)**2+.001**2)
    mapped=mu.copy();mapped[:ns]/=denominator
    original.eval(y,lam,mapped,0.)
    return dict(stat=float(max(abs(original.grad))),
        feas=float(max(max(abs(original.h)),max(original.g),0.)),
        comp=float(max(abs(np.minimum(mapped,-original.g)))),dual=float(max(0.,-min(mapped))))


def run(name):
    directory=HERE/'cases'/name;directory.mkdir(parents=True,exist_ok=True)
    if (directory/'result.json').exists():raise RuntimeError('case already run; do not overwrite')
    source=OLD/'cases/N'/f'{name}.json';saved=json.loads(source.read_text())
    assert saved['reached_final_stage'] and not saved['timed_out'] and saved['rho']==1e4
    model=na.Model(saved['tau'],saved['seed'],library='/tmp/uav-reproduction-speed.so')
    original=na.Model(saved['tau'],saved['seed'])
    model.stage(.0005,12.);original.stage(.0005,12.)
    y,lam,mu=(np.array(saved[k]) for k in ['y','lam','mu']);rho=1e4
    first=na.kkt(model,y,lam,mu)
    assert all(abs(first[k]-saved[k])<=1e-9*(1+abs(saved[k])) for k in first),(name,first,saved)
    mode_start=model.me-(model.stamps-1)
    i=mode_start+int(np.argmax(model.h[mode_start:]));h0=float(model.h[i]);lambda0=float(lam[i])
    forecast=None
    if h0>1e-6 and lambda0>0:
        forecast=lambda0/(3*rho*h0)*((h0/1e-6)**1.5-1)
    initial=dict(case=name,source=str(source.relative_to(ROOT)),source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        normalized_kkt=first,original_kkt=canonical(original,model,y,lam,mu),
        worst_mode_row=i,worst_mode_h=h0,lambda_at_row=lambda0,predicted_extra_outer=forecast,
        limits=dict(extra_outer=600,inner=300,seconds=300,workers=2),
        original_outer=saved['outer_total'],original_seconds=saved['seconds'])
    (directory/'initial.json').write_text(json.dumps(initial,indent=2)+'\n')
    start=monotonic();rows=[];stop='outer_limit';inner_evals=0
    with (directory/'outer.jsonl').open('w') as output:
        for outer in range(600):
            def fg(point):
                if monotonic()-start>300:raise TimeoutError()
                return model.eval(point,lam,mu,rho)
            try:res=na.tr_newton(fg,y,gtol=1e-6,max_iter=300)
            except TimeoutError:stop='timeout';break
            y=np.ascontiguousarray(res['y']);inner_evals+=res['evals']
            model.eval(y,lam,mu,0.)
            lam+=rho*model.h;mu=np.maximum(0.,mu+rho*model.g)
            normalized=na.kkt(model,y,lam,mu)
            checked=canonical(original,model,y,lam,mu)
            row=dict(extra_outer=outer+1,normalized_kkt=normalized,original_kkt=checked,
                objective=float(model.objective[0]),inner_status=res['status'],inner_iters=res['iters'],
                elapsed=monotonic()-start)
            rows.append(row);output.write(json.dumps(row)+'\n');output.flush()
            (directory/'state.json').write_text(json.dumps(dict(y=y.tolist(),lam=lam.tolist(),mu=mu.tolist(),rho=rho))+'\n')
            if all(v<=1e-6 for v in checked.values()):stop='kkt';break
    doc=model.solution(y);physical=audit.inspect(doc)
    result=dict(case=name,stop=stop,kkt_converged=stop=='kkt',extra_outer=len(rows),extra_seconds=monotonic()-start,
        total_outer=saved['outer_total']+len(rows),total_seconds=saved['seconds']+monotonic()-start,
        original_kkt=canonical(original,model,y,lam,mu),normalized_kkt=na.kkt(model,y,lam,mu),
        objective=doc['metrics']['objective'],original_violation=doc['metrics']['viol'],
        physical_audit=physical,inner_evals=inner_evals)
    doc['experiment']=dict(initial=initial,result=result,y_full_precision=y.tolist(),lam=lam.tolist(),mu=mu.tolist())
    doc['metrics']['converged']=result['kkt_converged']
    (directory/'raw.json').write_text(json.dumps(doc,indent=2,allow_nan=False)+'\n')
    (directory/'result.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    model.close();original.close();return result


if __name__=='__main__':
    results=[]
    with ThreadPoolExecutor(max_workers=2) as executor:
        for future in as_completed([executor.submit(run,name) for name in CASES]):
            result=future.result();results.append(result)
            (HERE/'results.json').write_text(json.dumps(results,indent=2,allow_nan=False)+'\n')
            print(json.dumps({k:result[k] for k in ['case','stop','extra_outer','extra_seconds','original_kkt']}),flush=True)
