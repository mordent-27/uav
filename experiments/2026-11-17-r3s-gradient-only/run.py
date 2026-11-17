import csv
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

BASE=Path(__file__).resolve().parent;ROOT=BASE.parents[1]
PRIOR=ROOT/'experiments/2026-11-17-r3s-step-profile'


def read(p):return json.loads(p.read_text())
def write(p,v):p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')


def freeze():
    assert not (BASE/'source-index.json').exists()
    sources=dict(read(PRIOR/'source-index.json'))
    for p in [PRIOR/'source-index.json',PRIOR/'states.json',PRIOR/'profile_step.py',PRIOR/'NEXT.md',PRIOR/'library-index.json']:
        sources[str(p.relative_to(ROOT))]=hashlib.sha256(p.read_bytes()).hexdigest()
    write(BASE/'source-index.json',sources);print(json.dumps(dict(sources=len(sources))))


def worker(case):
    import numpy as np
    from threadpoolctl import threadpool_info
    import fast_hessian as fast
    os.environ['UAV_R2_CASE']=case;os.environ['UAV_R2B_COND']='G'
    sys.path.insert(0,str(ROOT/'experiments/2026-11-15-r2b-coarse'))
    import helpers as h
    spec=importlib.util.spec_from_file_location('prior_profile',PRIOR/'profile_step.py')
    prior=importlib.util.module_from_spec(spec);spec.loader.exec_module(prior)
    newton=h.load('newton');original_hessian=h.decomposition.hessian_of_al
    state=next(r for r in read(PRIOR/'states.json') if r['case']==case)
    folder=BASE/'cases'/case;folder.mkdir(parents=True,exist_ok=False)
    frozen=h.stage4.Frozen(state['context']);frozen.m.current_stage=1
    y=np.array(state['context']['y']);m=frozen.m
    m.eval(y,frozen.lam,frozen.mu,frozen.rho)
    le=frozen.lam+frozen.rho*m.h.copy();mi=np.maximum(0.,frozen.mu+frozen.rho*m.g.copy())
    points=[y.copy()]
    for j in range(len(y)):
        for sign in [1,-1]:
            p=y.copy();p[j]+=sign*1e-7;points.append(p)
    a=[];b=[]
    def same(x,z):
        assert x.dtype==z.dtype and x.shape==z.shape and x.tobytes()==z.tobytes()
    for point in points:
        reference=m.eval(point,le,mi,0.)[1];rh,rg=m.h.copy(),m.g.copy()
        candidate=fast.gradient_only(m,point,le,mi)
        same(reference,candidate);same(rh,m.h);same(rg,m.g)
        a.append(reference);b.append(candidate)
    original_H,original_skew=original_hessian(frozen,y);rh,rg=m.h.copy(),m.g.copy()
    fast_H,fast_skew=fast.hessian_of_al(frozen,y);same(original_H,fast_H);same(rh,m.h);same(rg,m.g)
    assert original_skew==fast_skew
    np.savez_compressed(folder/'numeric-checks.npz',points=np.array(points),original_gradients=np.array(a),
         fast_gradients=np.array(b),original_H=original_H,fast_H=fast_H,
         original_h=rh,fast_h=m.h.copy(),original_g=rg,fast_g=m.g.copy())
    rows=[];endpoint=None
    def once(candidate):
        h.decomposition.hessian_of_al=fast.hessian_of_al if candidate else original_hessian
        try:return prior.original_step(frozen,y,newton)
        finally:h.decomposition.hessian_of_al=original_hessian
    for i in range(-3,21):
        if i%2:
            changed,changed_ns=once(True);original,original_ns=once(False)
        else:
            original,original_ns=once(False);changed,changed_ns=once(True)
        prior.compare(original,state['first_accepted'],np);prior.compare(changed,original,np)
        same(np.array(original['y']),np.array(changed['y']))
        for k in ['value','gradient_inf','delta','ratio','prediction','gradient_fallback','eigen_min','eigen_max']:
            assert original[k]==changed[k],k
        endpoint=changed
        if i>=0:rows.append(dict(case=case,repeat=i,order='fast_first' if i%2 else 'original_first',
            original_ns=original_ns,fast_ns=changed_ns,accepted_y_bytes_equal=True,decision_scalars_equal=True))
    with (folder/'timings.csv').open('w') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]),lineterminator='\n');writer.writeheader();writer.writerows(rows)
    write(folder/'checks.json',dict(case=case,variables=len(y),gradient_points=len(points),gradient_bytes_equal=True,
         H_bytes_equal=True,cache_bytes_equal=True,skew_equal=True,matching_pairs=24,measured_pairs=21,
         first_accepted=endpoint,original_skew=original_skew,fast_skew=fast_skew))
    write(folder/'environment.json',dict(python=sys.version,numpy=np.__version__,threadpools=threadpool_info(),
          env={k:os.environ.get(k) for k in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS']}))
    frozen.close();print(json.dumps(dict(case=case,gradient_points=len(points),all_checks_passed=True)))


def main():
    if '--freeze' in sys.argv:freeze();return
    for name,digest in read(BASE/'source-index.json').items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
    for name,digest in read(PRIOR/'library-index.json').items():assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==digest,name
    if '--case' in sys.argv:worker(sys.argv[sys.argv.index('--case')+1]);return
    assert not (BASE/'cases').exists()
    env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1')
    for state in read(PRIOR/'states.json'):
        subprocess.run([sys.executable,__file__,'--case',state['case']],env=env,check=True)


if __name__=='__main__':main()
