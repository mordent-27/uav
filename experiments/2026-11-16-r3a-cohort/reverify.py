"""Read back every actually executed G/direct phase and input NLP, without optimizing."""
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
OUT=BASE/'batches'/os.environ.get('UAV_R3_BATCH','000')


def read(path):return json.loads(path.read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x') as stream:stream.write(json.dumps(data,indent=2)+'\n')
def snapshot(case):
    folders=[BASE/'inputs'/case,BASE/'initializations'/case,BASE/'cases/G'/case,BASE/'cases/fallback'/case]
    return {str(p.relative_to(BASE)):sha(p) for folder in folders for p in folder.rglob('*') if p.is_file()}


def worker():
    import numpy as np
    import helpers as h
    start=monotonic();before=snapshot(h.CASE)
    checks=[]
    for route in ['G','fallback']:
        h.HERE=BASE/'cases'/route/h.CASE;h.SOURCE=h.HERE/'source.json';h.PHASE=route
        if not h.HERE.exists():continue
        preflight=read(h.HERE/'preflight.json');h.KIND=preflight.get('kind','original')
        verifier=h.load_from(h.R2B if route=='G' else h.DIRECT,'verify')
        captured={};differences=[]
        original_write,original_close=h.write,verifier.close
        def capture(path,data):
            assert Path(path)==h.HERE/'verification.json'
            captured['verification']=data
        def close(a,b,tol=1e-9):
            x,y=np.asarray(a,dtype=float),np.asarray(b,dtype=float)
            differences.append(dict(values=int(x.size),max_abs=float(np.max(abs(x-y))) if x.size else 0.))
            return original_close(a,b,tol)
        report=dict(route=route,kind=h.KIND,verifier_sha256=sha((h.R2B if route=='G' else h.DIRECT)/'verify.py'))
        h.write,verifier.close=capture,close
        try:
            verifier.main();saved=read(h.HERE/'verification.json')
            assert captured['verification']==saved
            report.update(existing_verifier_passed=True,saved_verification_reproduced=True,
                stages=len(saved['stages']),counts={key:saved[key] for key in
                    ['completed_outer','accepted_inner_points','interrupted_accepted_points']})
        except Exception:report.update(existing_verifier_passed=False,error=traceback.format_exc())
        finally:h.write,verifier.close=original_write,original_close
        report.update(comparison_calls=len(differences),compared_values=sum(row['values'] for row in differences),
            max_abs_difference=max((row['max_abs'] for row in differences),default=0.))
        try:
            source=read(h.SOURCE);m=h.fidelity.Variant('R');m.stage(*((.2,2.) if route=='G' else (.0005,12.)))
            expected=read(h.INIT/'source.json')['y'] if route=='fallback' and h.KIND=='repaired' else read(h.INPUT/'original-state.json')['y']
            np.testing.assert_array_equal(source['y'],expected)
            if route=='G' or h.KIND=='original':np.testing.assert_array_equal(source['y'],m.native.y)
            y=np.array(source['y']);lam,mu=np.zeros(m.me),np.zeros(m.mi)
            assert source['lam']==lam.tolist() and source['mu']==mu.tolist() and source['rho']==1e4
            value,gradient=m.eval(y,lam,mu,1e4);le,mi=1e4*m.h,np.maximum(0.,1e4*m.g)
            jac=m.jacobian(y);_,gf=m.eval(y,lam,mu,0.)
            independent=gf+jac[:m.me].T@le+jac[m.me:].T@mi
            np.testing.assert_allclose(gradient,independent,atol=1e-8,rtol=1e-8)
            report['added_initial_AL']=dict(input_state_exactly_verified=True,value=float(value),
                gradient_inf=float(max(abs(gradient))),gradient_minus_jacobian_form_inf=float(max(abs(gradient-independent))))
            m.close()
        except Exception:report['added_initial_AL_error']=traceback.format_exc()
        report['passed']=bool(report['existing_verifier_passed'] and 'added_initial_AL' in report)
        checks.append(report)
    init=None
    if (h.INIT/'result.json').exists():
        original_write=h.write;captured={}
        def capture_init(path,data):
            assert Path(path)==h.INIT/'verification.json'
            captured['verification']=data
        h.write=capture_init
        try:
            h.load_from(h.R2F,'verify_init').main()
            assert captured['verification']==read(h.INIT/'verification.json')
            init=dict(passed=True,saved_verification_reproduced=True,accepted=read(h.INIT/'result.json')['accepted'])
        except Exception:init=dict(passed=False,error=traceback.format_exc())
        finally:h.write=original_write
    report=dict(case=h.CASE,optimizer_launched=False,phases=checks,initialization=init,
        existing_files_hashed=len(before),existing_files_unchanged=before==snapshot(h.CASE),seconds=monotonic()-start)
    write(OUT/'reverification'/f'{h.CASE}.json',report)
    assert checks and all(row['passed'] for row in checks) and report['existing_files_unchanged'] and (init is None or init['passed'])


def driver():
    def launch(case):
        env=dict(os.environ,UAV_R2_CASE=case,UAV_R2H_PHASE='G',UAV_R2F_KIND='original',
            OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1')
        log=OUT/'reverification/logs'/f'{case}.log';log.parent.mkdir(parents=True,exist_ok=True)
        with log.open('x') as stream:
            run=subprocess.run([sys.executable,str(Path(__file__).resolve())],env=env,stdout=stream,stderr=subprocess.STDOUT)
        return dict(case=case,returncode=run.returncode)
    start=monotonic()
    with ThreadPoolExecutor(8) as pool:runs=list(pool.map(launch,list(dict.fromkeys(case for p in sorted(OUT.glob('attempt*.json')) for case in read(p)['cases']))))
    reports=[read(OUT/'reverification'/f'{r["case"]}.json') for r in runs]
    phases=[p for r in reports for p in r['phases']]
    summary=dict(optimizer_launched=False,runs=runs,seconds=monotonic()-start,workers=8,cases=len(reports),
        phases=len(phases),phases_passed=sum(p['passed'] for p in phases),
        initializations_checked=sum(r['initialization'] is not None for r in reports),
        initializations_passed=sum(bool(r['initialization'] and r['initialization']['passed']) for r in reports),
        existing_files_unchanged=sum(r['existing_files_unchanged'] for r in reports),
        stages=sum(p.get('stages',0) for p in phases),
        counts={key:sum(p.get('counts',{}).get(key,0) for p in phases) for key in
            ['completed_outer','accepted_inner_points','interrupted_accepted_points']},
        comparison_calls=sum(p['comparison_calls'] for p in phases),
        compared_values=sum(p['compared_values'] for p in phases),
        max_abs_difference=max(p['max_abs_difference'] for p in phases),
        max_initial_gradient_minus_jacobian_form=max(p.get('added_initial_AL',{}).get('gradient_minus_jacobian_form_inf',0.) for p in phases))
    write(OUT/'reverification.json',summary);print(json.dumps(summary),flush=True)
    assert all(r['returncode']==0 for r in runs)


if __name__=='__main__':
    if os.environ.get('UAV_R2_CASE'):worker()
    else:
        import driver as cohort_driver
        with cohort_driver.protocol_lock():driver()
