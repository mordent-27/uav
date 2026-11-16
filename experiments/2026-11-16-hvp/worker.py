import hashlib
import json
import os
from pathlib import Path
from time import perf_counter
import numpy as np
import helpers as h
from curvature_operator import DirectionalCurvature

BASE=Path(__file__).resolve().parent


def main():
    case=os.environ['UAV_R2_CASE'];stage=int(os.environ['UAV_PROFILE_STAGE'])
    source=h.ROOT/'experiments/2026-11-16-r3a-cohort/cases/G'/case/'stages'/f'stage{stage:02d}'/'initial.json'
    raw=source.read_bytes();state=json.loads(raw);out=BASE/'states'/f'{case}-stage{stage:02d}';out.mkdir(parents=True,exist_ok=False)
    f=h.stage4.Frozen(state);y=np.array(state['y']);lam,mu=np.array(state['lam']),np.array(state['mu'])
    metrics=f.m.metrics(y,lam,mu)
    for key in ['common_kkt','paper_units_kkt']:
        np.testing.assert_allclose(list(metrics[key].values()),list(state[key].values()),atol=1e-9,rtol=1e-8)
    _,gradient=f.eval(y);gradient=gradient.copy()
    H,skew=h.decomposition.hessian_of_al(f,y,1e-7)
    Hhalf,skewhalf=h.decomposition.hessian_of_al(f,y,5e-8)
    eigen,vectors=np.linalg.eigh(H)
    rng=np.random.default_rng(20261116+h.TAU+stage)
    directions=np.array([-gradient,rng.normal(size=len(y)),rng.normal(size=len(y)),vectors[:,0]])
    directions/=np.linalg.norm(directions,axis=1)[:,None]
    op=DirectionalCurvature(f,y);products=np.array([op.matvec(v) for v in directions])
    reference=directions@H.T;half=directions@Hhalf.T
    rows=[]
    for name,v,z,r,other in zip(['negative_gradient','random1','random2','min_eigenvector'],directions,products,reference,half):
        absolute=float(np.linalg.norm(z-r));normalized=absolute/max(1.,float(np.linalg.norm(r)))
        curv=float(v@r);candidate=float(v@z)
        rows.append(dict(direction=name,absolute_error=absolute,normalized_error=normalized,
            reference_norm=float(np.linalg.norm(r)),reference_step_sensitivity=float(np.linalg.norm(other-r))/max(1.,float(np.linalg.norm(r))),
            reference_curvature=curv,candidate_curvature=candidate,curvature_error=abs(candidate-curv),
            curvature_sign_equal=bool(np.sign(curv)==np.sign(candidate)),passes=normalized<=1e-5))
    u,v=directions[1:3];hu,hv=products[1:3]
    symmetry=float(abs(u@hv-v@hu))/max(1.,abs(float(u@hv)),abs(float(v@hu)))
    add=float(np.linalg.norm(op.matvec(u+v)-hu-hv))/max(1.,float(np.linalg.norm(hu+hv)))
    np.testing.assert_array_equal(op.matvec(np.zeros_like(y)),np.zeros_like(y))
    timings=[]
    for _ in range(5):
        t=perf_counter();matrix,_=h.decomposition.hessian_of_al(f,y,1e-7);dense=perf_counter()-t
        np.testing.assert_allclose(matrix,H,atol=1e-9,rtol=1e-9)
        t=perf_counter();setup=DirectionalCurvature(f,y);setup_time=perf_counter()-t
        t=perf_counter();observed=np.array([setup.matvec(d) for d in directions]);queries=(perf_counter()-t)/len(directions)
        np.testing.assert_allclose(observed,products,atol=1e-9,rtol=1e-9)
        t=perf_counter()
        for _ in range(100):np.dot(directions,H.T)
        dense_query=(perf_counter()-t)/(100*len(directions))
        timings.append(dict(dense_construction=dense,setup=setup_time,query=queries,dense_query=dense_query))
    medians={key:float(np.median([r[key] for r in timings])) for key in timings[0]}
    budgets=[dict(queries=q,dense_seconds=medians['dense_construction']+q*medians['dense_query'],
        directional_seconds=medians['setup']+q*medians['query']) for q in [1,5,10,25,50,100]]
    np.savez_compressed(out/'vectors.npz',H=H,Hhalf=Hhalf,directions=directions,products=products,reference=reference)
    result=dict(case=case,stage=stage,variables=len(y),source=str(source.relative_to(h.ROOT)),source_sha256=hashlib.sha256(raw).hexdigest(),
        rows=rows,symmetry_error=symmetry,additivity_error=add,
        comparison_passed=all(r['passes'] for r in rows) and symmetry<=1e-5 and add<=1e-5,
        raw_hessian_max_asymmetry=skew,half_step_max_asymmetry=skewhalf,min_reference_eigenvalue=float(eigen[0]),
        timings=timings,medians=medians,budgets=budgets,warmup=1,repetitions=5,
        dense_gradient_calls_per_construction=1+2*len(y),directional_gradient_calls_per_query=2,
        constraint_jacobian_calls_per_setup=1,optimizer_launched=False)
    f.close();assert source.read_bytes()==raw
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(case=case,stage=stage,passed=result['comparison_passed'],medians=medians)))


if __name__=='__main__':main()
