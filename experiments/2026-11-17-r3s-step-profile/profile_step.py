"""Fixed-state one-step replay and timing. No continuation or returned-point changes."""
import csv
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from time import perf_counter_ns, monotonic

BASE=Path(__file__).resolve().parent;ROOT=BASE.parents[1]
WARMUP=3;REPEATS=21


def read(p):return json.loads(p.read_text())
def write(p,v):p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')


def validate_times(total, parts):
    assert total>0 and all(v>=0 for v in parts.values())
    remaining=total-sum(parts.values());assert remaining>=0
    return remaining


def timed_hessian(frozen,y,np):
    timing={};start=perf_counter_ns();m=frozen.m
    m.eval(y,frozen.lam,frozen.mu,frozen.rho)
    h,g=m.h.copy(),m.g.copy()
    le=frozen.lam+frozen.rho*h
    shifted=frozen.mu+frozen.rho*g
    active=shifted>0
    mi=np.maximum(0.,shifted)
    t=perf_counter_ns();timing['hessian_setup_ns']=t-start
    jac=m.jacobian(y)
    t2=perf_counter_ns();timing['jacobian_ns']=t2-t
    raw=np.empty((len(y),len(y)))
    for j in range(len(y)):
        a,b=y.copy(),y.copy();a[j]+=1e-7;b[j]-=1e-7
        raw[:,j]=(m.eval(a,le,mi,0.)[1]-m.eval(b,le,mi,0.)[1])/(2*1e-7)
    t=perf_counter_ns();timing['curvature_fd_ns']=t-t2
    J=jac[:m.me];G=jac[m.me:][active]
    H=(raw+raw.T)/2+frozen.rho*(J.T@J+G.T@G)
    skew=float(np.max(abs(raw-raw.T)))
    timing['hessian_assembly_ns']=perf_counter_ns()-t
    return H,skew,timing


def timed_step(frozen,y,h,np):
    parts={};begin=perf_counter_ns()
    f,g=frozen.eval(y);t=perf_counter_ns();parts['initial_eval_ns']=t-begin
    H,skew,ht=timed_hessian(frozen,y,np);parts.update(ht)
    t=perf_counter_ns();w,V=np.linalg.eigh(H);parts['eigh_ns']=perf_counter_ns()-t
    delta=1.;accepted=None;start=perf_counter_ns()
    for trial in range(60):
        step,boundary=h.stage4.old.newton.tr_step(w,V,g,delta)
        pred=-(g@step+.5*step@H@step)
        fn,gn=frozen.eval(y+step)
        fallback=pred<=1e-13*max(1.,abs(f))
        if fallback:ratio=1. if np.linalg.norm(gn)<np.linalg.norm(g) else 0.
        else:ratio=(f-fn)/pred
        if ratio<.25:delta=.25*np.linalg.norm(step)
        elif ratio>.75 and boundary:delta=min(2*delta,1e3)
        if ratio>1e-4:
            accepted=dict(y=(y+step).tolist(),value=float(fn),gradient_inf=float(max(abs(gn))),
                          delta=float(delta),ratio=float(ratio),prediction=float(pred),
                          gradient_fallback=bool(fallback),eigen_min=float(w[0]),eigen_max=float(w[-1]))
            break
        if delta<1e-14:break
    parts['search_ns']=perf_counter_ns()-start
    total=perf_counter_ns()-begin;parts['other_ns']=validate_times(total,parts)
    assert accepted is not None,'first step was not accepted'
    return accepted,H,skew,dict(total_ns=total,trials=trial+1,**parts)


def original_step(frozen,y,newton):
    class FirstAccepted(Exception):pass
    accepted=None
    def record(row):
        nonlocal accepted
        if row['kind']=='accepted':accepted=row;raise FirstAccepted()
    start=perf_counter_ns()
    try:newton.solve(frozen,y.copy(),monotonic()+15,record)
    except FirstAccepted:pass
    elapsed=perf_counter_ns()-start
    assert accepted is not None
    return accepted,elapsed


def compare(a,b,np):
    np.testing.assert_allclose(a['y'],b['y'],atol=1e-11,rtol=1e-11)
    for k in ['value','gradient_inf','delta','ratio','prediction','eigen_min','eigen_max']:
        np.testing.assert_allclose(a[k],b[k],atol=1e-10,rtol=1e-10)
    assert a['gradient_fallback']==b['gradient_fallback']


def worker(case):
    import importlib.metadata
    import numpy as np
    from threadpoolctl import threadpool_info
    os.environ['UAV_R2_CASE']=case;os.environ['UAV_R2B_COND']='G'
    sys.path.insert(0,str(ROOT/'experiments/2026-11-15-r2b-coarse'))
    import helpers as h
    newton=h.load('newton')
    state=next(r for r in read(BASE/'states.json') if r['case']==case)
    output=BASE/'cases'/case;output.mkdir(parents=True,exist_ok=False)
    frozen=h.stage4.Frozen(state['context']);frozen.m.current_stage=1
    y=np.array(state['context']['y']);before=y.copy()
    value,gradient=frozen.eval(y)
    np.testing.assert_allclose(value,state['input']['value'],atol=1e-11,rtol=1e-11)
    np.testing.assert_allclose(max(abs(gradient)),state['input']['gradient_inf'],atol=1e-11,rtol=1e-11)
    baseline_H,baseline_skew=h.decomposition.hessian_of_al(frozen,y)
    endpoint,H,skew,_=timed_step(frozen,y,h,np)
    assert np.array_equal(H,baseline_H) and skew==baseline_skew
    compare(endpoint,state['first_accepted'],np)
    rows=[]
    for i in range(-WARMUP,REPEATS):
        if i%2:
            profiled,H,skew,timing=timed_step(frozen,y,h,np)
            original,baseline_ns=original_step(frozen,y,newton)
        else:
            original,baseline_ns=original_step(frozen,y,newton)
            profiled,H,skew,timing=timed_step(frozen,y,h,np)
        compare(original,state['first_accepted'],np);compare(profiled,original,np)
        assert np.array_equal(H,baseline_H) and np.array_equal(y,before)
        if i>=0:rows.append(dict(case=case,repeat=i,order='profile_first' if i%2 else 'original_first',
                                  variables=len(y),baseline_ns=baseline_ns,**timing))
    with (output/'timings.csv').open('w') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]),lineterminator='\n');writer.writeheader();writer.writerows(rows)
    write(output/'preflight.json',dict(case=case,variables=len(y),H_bitwise_equal=True,skew_equal=True,
          all_saved_steps_replayed=True,all_profiled_steps_match_original=True,input_y_unchanged=True,
          warmup=WARMUP,repeats=REPEATS,first_step=endpoint,initial_value=value,
          initial_gradient_inf=float(max(abs(gradient)))))
    np.savez_compressed(output/'matrices.npz',H=baseline_H,y=y)
    write(output/'environment.json',dict(python=sys.version,executable=sys.executable,numpy=np.__version__,
          scipy=importlib.metadata.version('scipy'),threadpools=threadpool_info(),
          env={k:os.environ.get(k) for k in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS']},
          loadavg=list(os.getloadavg())))
    frozen.close();print(json.dumps(dict(case=case,measurements=len(rows),replay_pass=True)))


def main():
    for index,root in [('source-index.json',ROOT),('library-index.json',Path('/'))]:
        for name,digest in read(BASE/index).items():assert hashlib.sha256((root/name).read_bytes()).hexdigest()==digest,name
    if '--case' in sys.argv:
        worker(sys.argv[sys.argv.index('--case')+1]);return
    assert not (BASE/'cases').exists()
    env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1')
    for state in read(BASE/'states.json'):
        subprocess.run([sys.executable,__file__,'--case',state['case']],env=env,check=True)


if __name__=='__main__':main()
