"""Read back every new G inner/outer point with the unchanged G verifier; never solve."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from time import monotonic
import traceback

BASE=Path(__file__).resolve().parent


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def snapshot(folder):return {str(p.relative_to(folder)):sha(p) for p in folder.rglob('*') if p.is_file()}
def write(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x') as stream:stream.write(json.dumps(data,indent=2)+'\n')


def worker():
    import numpy as np
    import helpers as h
    start=monotonic();before=snapshot(h.HERE)
    verify=h.load_from(h.R2B,'verify');captured={};comparisons=[]
    original_write,original_close=h.write,verify.close
    def capture(path,data):
        assert Path(path)==h.HERE/'verification.json'
        captured['verification']=data
    def close(a,b,tol=1e-9):
        x,y=np.asarray(a,dtype=float),np.asarray(b,dtype=float)
        comparisons.append(dict(values=int(x.size),max_abs_difference=float(np.max(abs(x-y))) if x.size else 0.,tolerance=tol))
        return original_close(a,b,tol)
    report=dict(case=h.CASE,optimizer_launched=False,verifier_sha256=sha(h.R2B/'verify.py'))
    h.write,verify.close=capture,close
    try:
        verify.main()
        report['existing_verifier_passed']=True
    except Exception:report.update(existing_verifier_passed=False,error=traceback.format_exc())
    finally:h.write,verify.close=original_write,original_close
    saved=json.loads((h.HERE/'verification.json').read_text())
    report['saved_verification_reproduced']=captured.get('verification')==saved
    report['counts']={key:saved[key] for key in ['completed_outer','accepted_inner_points','interrupted_accepted_points']}
    report['stages']=len(saved['stages'])
    source=json.loads(h.SOURCE.read_text());m=h.fidelity.Variant('R');m.stage(.2,2.)
    np.testing.assert_array_equal(source['y'],m.native.y)
    y=np.array(source['y']);lam,mu=np.zeros(m.me),np.zeros(m.mi)
    value,gradient=m.eval(y,lam,mu,1e4)
    le,mi=1e4*m.h,np.maximum(0.,1e4*m.g)
    jac=m.jacobian(y);_,gf=m.eval(y,lam,mu,0.)
    difference=float(max(abs(gradient-gf-jac[:m.me].T@le-jac[m.me:].T@mi)))
    np.testing.assert_allclose(gradient,gf+jac[:m.me].T@le+jac[m.me:].T@mi,atol=1e-8,rtol=1e-8)
    m.close()
    report['added_initial_AL']=dict(initial_y_exactly_native=True,value=float(value),
        gradient_inf=float(max(abs(gradient))),gradient_minus_jacobian_form_inf=difference)
    report['comparison_calls']=len(comparisons)
    report['compared_values']=sum(row['values'] for row in comparisons)
    report['max_abs_difference']=max(row['max_abs_difference'] for row in comparisons)
    report['existing_files_unchanged']=before==snapshot(h.HERE)
    report['existing_files_hashed']=len(before);report['seconds']=monotonic()-start
    write(BASE/'reverification'/f'{h.CASE}.json',report)
    assert report['existing_verifier_passed'] and report['saved_verification_reproduced'] and report['existing_files_unchanged']


def driver():
    catalog=json.loads((BASE/'catalog.json').read_text())
    def launch(case):
        env=dict(os.environ,UAV_R2_CASE=case,UAV_R2H_PHASE='G',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
        log=BASE/'reverification/logs'/f'{case}.log';log.parent.mkdir(parents=True,exist_ok=True)
        with log.open('x') as stream:
            run=subprocess.run([sys.executable,str(Path(__file__).resolve())],env=env,stdout=stream,stderr=subprocess.STDOUT)
        return dict(case=case,returncode=run.returncode)
    start=monotonic()
    with ThreadPoolExecutor(8) as pool:runs=list(pool.map(launch,catalog['new_G_cases']))
    reports=[json.loads((BASE/'reverification'/f'{row["case"]}.json').read_text()) for row in runs]
    summary=dict(optimizer_launched=False,runs=runs,seconds=monotonic()-start,workers=8,
        cases=len(reports),existing_verifier_passed=sum(r['existing_verifier_passed'] for r in reports),
        saved_verification_reproduced=sum(r['saved_verification_reproduced'] for r in reports),
        existing_files_unchanged=sum(r['existing_files_unchanged'] for r in reports),
        stages=sum(r['stages'] for r in reports),
        counts={key:sum(r['counts'][key] for r in reports) for key in reports[0]['counts']},
        comparison_calls=sum(r['comparison_calls'] for r in reports),
        compared_values=sum(r['compared_values'] for r in reports),
        max_abs_difference=max(r['max_abs_difference'] for r in reports),
        max_initial_gradient_minus_jacobian_form=max(r['added_initial_AL']['gradient_minus_jacobian_form_inf'] for r in reports))
    write(BASE/'reverification.json',summary);print(json.dumps(summary),flush=True)
    assert all(row['returncode']==0 for row in runs)


if __name__=='__main__':worker() if os.environ.get('UAV_R2_CASE') else driver()
