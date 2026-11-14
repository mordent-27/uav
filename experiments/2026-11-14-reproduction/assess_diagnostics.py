"""Check KKT in the original model representation, not just the preconditioned one."""
import importlib.util
import json
import math
from pathlib import Path
from independent_al import Model,np
from check_speed import denominator

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
spec=importlib.util.spec_from_file_location('audit',ROOT/'experiments/2026-11-14-validation/audit.py')
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)


def main():
    results=[]
    paths=list((HERE/'diagnostics').glob('*.json'))+list((HERE/'pilot').glob('tau*.json'))
    for path in sorted(paths):
        d=json.loads(path.read_text());exp=d['experiment'];args=exp['arguments']
        if 'y_full_precision' not in exp:continue
        original=Model(args['tau'],args['seed'])
        stage=d['stages'][-1] if d['stages'] else dict(stage=1)
        index=exp.get('active_stage',stage['stage']+int(exp.get('timeout',False)))-1
        original.stage(max(.0005,.2*.6**index),min(12.,2*1.2**index))
        y=np.array(exp['y_full_precision']);lam=np.array(exp['diagnostics']['lam'])
        mu=np.array(exp['diagnostics']['mu'])
        is_speed='speed.so' in args['library']
        if is_speed:mu[:original.stamps-1]/=denominator(original,y)
        original.eval(y,lam,mu,0.)
        kkt=dict(stat=float(max(abs(original.grad))),feas=float(max(max(abs(original.h)),max(original.g),0.)),
                 comp=float(max(abs(np.minimum(mu,-original.g)))),dual=float(max(0.,-min(mu))))
        checked=audit.inspect(d)
        result=dict(case=path.stem,source=str(path.relative_to(HERE)),
            original_kkt=kkt,original_kkt_pass=all(v<=1e-6 for v in kkt.values()),
            stage=index+1,reached_final=bool(index>=12 and not exp.get('timeout',False)),
            skipped_coarse_stages=args.get('start_stage',0)>0,objective=d['metrics']['objective'],
            original_pass=checked['original_pass'],battery_replay_pass=checked['exact_mode_battery_pass'],
            original_violation=d['metrics']['viol'])
        if is_speed:
            changed=Model(args['tau'],args['seed'],library=args['library'])
            changed.stage(max(.0005,.2*.6**index),min(12.,2*1.2**index))
            old_jac,new_jac=original.jacobian(y),changed.jacobian(y)
            result['max_squared_jacobian_singular_value_original']=float(np.linalg.svd(old_jac,compute_uv=False)[0]**2)
            result['max_squared_jacobian_singular_value_scaled']=float(np.linalg.svd(new_jac,compute_uv=False)[0]**2)
            changed.close()
        results.append(result);original.close()
    eps,p,distance=.0005,12.,1.
    alpha=(eps/math.hypot(distance,eps))**p
    root=eps*math.sqrt(math.expm1(-2/p*math.log1p(-alpha)))
    phi0_direct=eps*(1+alpha)**(-1/p)
    degeneracy=dict(eps=eps,p=p,other_distance_km=distance,exact_visit_ring_radius_km=root,
        derivative_at_ring_approx=root/eps,residual_at_zero_direct=phi0_direct-eps,
        residual_at_zero_stable=eps*math.expm1(-math.log1p(alpha)/p),
        note='algebraic two-candidate diagnostic; not proof that all computed KKT points are impossible')
    (HERE/'diagnostic-assessment.json').write_text(json.dumps(dict(cases=results,degeneracy=degeneracy),indent=2)+'\n')
    print(json.dumps(dict(cases=results,degeneracy=degeneracy),indent=2))


if __name__=='__main__':main()
