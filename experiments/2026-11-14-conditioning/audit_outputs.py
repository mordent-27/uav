"""Audit inherited paired outputs and recompute the 39 final-state KKT residuals."""
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys

import numpy as np

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE.parent/'2026-11-14-reproduction'))
from independent_al import Model
spec=importlib.util.spec_from_file_location('audit',ROOT/'experiments/2026-11-14-validation/audit.py')
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)


def main():
    new=HERE/'mc-rho1e4';old=HERE.parent/'2026-11-14-reproduction/mc-original'
    a,b=(json.loads((p/'manifest.json').read_text()) for p in [new,old])
    assert a['source_hashes']==b['source_hashes'] and a['binary_sha256']==b['binary_sha256']
    for name,digest in a['source_hashes'].items():assert hashlib.sha256((ROOT/'src'/name).read_bytes()).hexdigest()==digest
    maximum=0.;count=0;kkt_cases=[]
    for status_file in sorted((new/'cases').glob('tau*/run*/status.json')):
        status=json.loads(status_file.read_text())
        assert status['completed'] and not status['timed_out'] and status['exit_code']==0
        raw=json.loads(status_file.with_name('raw.json').read_text())
        baseline=json.loads((old/'cases'/status_file.parent.relative_to(new/'cases')/'raw.json').read_text())
        for key in ['instance','phys','init']:assert raw[key]==baseline[key],(status_file,key)
        check=audit.inspect(raw);assert check['finite'] and len(raw['stages'])==13
        difference=abs(check['original_residuals']['viol']-raw['metrics']['viol'])
        assert difference<=(2*math.sqrt(2)+36)*.5e-9+1e-12,(status_file,difference)
        maximum=max(maximum,difference)
        last=raw['stages'][-1]
        converged=all(math.isfinite(last[k]) and last[k]<=1e-6 for k in ['stat','feas','comp'])
        assert converged==raw['metrics']['converged']==status['kkt_converged']
        assert status['physical_audit_pass']==(check['original_pass'] and check['exact_mode_battery_pass'])
        if converged:kkt_cases.append(str(status_file.parent.relative_to(new)))
        count+=1
    assert count==900
    states=[]
    for condition in ['N','L','L0']:
        library='/tmp/uav-reproduction-bridge.so' if condition=='L0' else '/tmp/uav-reproduction-speed.so'
        for path in sorted((HERE/'cases'/condition).glob('*.json')):
            d=json.loads(path.read_text());m=Model(d['tau'],d['seed'],library);m.stage(.0005,12.)
            original=Model(d['tau'],d['seed']);original.stage(.0005,12.)
            y,lam,mu=(np.array(d[k]) for k in ['y','lam','mu'])
            m.eval(y,lam,mu,0.)
            normalized=dict(stat=float(max(abs(m.grad))),feas=float(max(max(abs(m.h)),max(m.g),0.)),
                            comp=float(max(abs(np.minimum(mu,-m.g)))))
            assert all(abs(normalized[k]-d[k])<=1e-8*(1+abs(d[k])) for k in normalized),path
            if condition!='L0':
                x=y*m.scale;ns,nr=m.stamps-1,2*(m.stamps-2);doc=m.solution(y)
                r=np.vstack([doc['instance']['r0'],x[:nr].reshape(-1,2),doc['instance']['rf']]);s=x[nr+ns:nr+2*ns]
                den=np.sqrt(np.sum(np.diff(r,axis=0)**2,axis=1)+.001**2)+np.sqrt((36*s)**2+.001**2)
                mu=mu.copy();mu[:ns]/=den
            original.eval(y,lam,mu,0.)
            canonical=dict(stat=float(max(abs(original.grad))),feas=float(max(max(abs(original.h)),max(original.g),0.)),
                comp=float(max(abs(np.minimum(mu,-original.g)))),dual=float(max(0.,-min(mu))))
            doc=m.solution(y);doc['experiment']=dict(source=str(path.relative_to(ROOT)),y_full_precision=y.tolist())
            dest=HERE/'audited-raw'/condition;dest.mkdir(parents=True,exist_ok=True)
            (dest/path.name).write_text(json.dumps(doc,indent=2,allow_nan=False)+'\n')
            physical=audit.inspect(doc)
            states.append(dict(condition=condition,case=path.stem,normalized=normalized,canonical=canonical,
                kkt_pass=not d['timed_out'] and d['reached_final_stage'] and all(v<=1e-6 for v in canonical.values()),
                timed_out=d['timed_out'],original_violation=doc['metrics']['viol'],
                original_pass=physical['original_pass'],battery_replay_pass=physical['exact_mode_battery_pass'],
                battery_replay_violation=physical['replay_violation']))
            m.close();original.close()
    assert len(states)==39
    result=dict(paired_cases=count,identical_binary=True,identical_inputs_and_initial_states=True,
                maximum_original_violation_readback_difference=maximum,baseline_source_unchanged=True,
                kkt_cases=kkt_cases,states=states)
    (HERE/'audit-results.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='states'},indent=2))
    for condition in ['N','L','L0']:
        part=[r for r in states if r['condition']==condition]
        print(condition,'canonical KKT',sum(v['kkt_pass'] for v in part),'/13',
              'battery replay',sum(v['battery_replay_pass'] for v in part),'/13')


if __name__=='__main__':main()
