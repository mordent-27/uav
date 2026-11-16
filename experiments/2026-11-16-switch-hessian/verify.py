"""Separate-process recheck: replaced columns, gate curvatures, 100-digit decision gradients, and the 24 straddling counts."""
from decimal import Decimal as D,localcontext
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from time import monotonic
import numpy as np

BASE=Path(__file__).resolve().parent


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def fix():
    import helpers as h
    import fixh
    kink=fixh.kink;cv=fixh.lowcurv
    targets=json.loads((BASE/'targets.json').read_text());P=targets['fix'];ctx=P['context']
    metadata=json.loads((h.ROOT/ctx['metadata_source']).read_text())['metadata'];result=json.loads((BASE/'fix'/'result.json').read_text())
    arrays=np.load(BASE/'fix'/'arrays.npz');before={p.name:sha(p) for p in (BASE/'fix').iterdir()};deadline=monotonic()+900
    y=np.load(h.ROOT/ctx['samples'])['y'];x0=cv.to_decimal(y);ns=metadata['n_segments']
    J,_=fixh.straddling(fixh.margins(y,metadata['scale'],metadata['phys'],ns),metadata['scale'],metadata['phys'],ns,P['old_hessian_step'])
    assert J==arrays['J'].tolist()
    def grad(p,d,s):
        g,=kink.central_pair(lambda q:kink.reference.evaluate(q,metadata,d),[lambda q:kink.piece_al(q,metadata,d)],p,d,s,deadline);return g
    columns=[]
    for j in J:
        e=np.zeros(len(y));e[j]=1.;plus,minus=cv.shifted(x0,e,P['column_width'],P['digits'])
        gp,gm=grad(plus,P['digits'],P['column_gradient_step']),grad(minus,P['digits'],P['column_gradient_step'])
        with localcontext() as c:
            c.prec=P['digits'];t=D(P['column_width']);columns.append(np.array([float((a-b)/(2*t)) for a,b in zip(gp,gm)]))
    np.testing.assert_array_equal(np.array(columns),arrays['columns'])
    points={'x0':x0,'x_star':[D(v) for v in result['points'][result['first_reaching']]],
        'rounded':cv.to_decimal(result['binary64']['rounded']['point']),'lattice':cv.to_decimal(result['binary64']['lattice']['point'])}
    stored={'x0':result['newton'][0]['gradient_inf'],'x_star':result['newton'][result['first_reaching']]['gradient_inf'],
        'rounded':result['binary64']['rounded']['gradient_inf'],'lattice':result['binary64']['lattice']['gradient_inf']}
    checks={}
    for name,point in points.items():
        g=np.array([float(v) for v in grad(point,P['reference_digits'],P['reference_step'])]);value=float(abs(g).max())
        checks[name]=dict(gradient_inf_100=value,stored_80=stored[name],difference=abs(value-stored[name]),agrees=abs(value-stored[name])<=P['gradient_agreement_inf'])
    verdict=cv.rounding_verdict(checks['x_star']['gradient_inf_100'],checks['rounded']['gradient_inf_100'],P['gradient_inf_target'])
    assert verdict==result['binary64']['verdict'] and all(c['agrees'] for c in checks.values())
    assert (checks['lattice']['gradient_inf_100']<=P['gradient_inf_target'])==result['binary64']['lattice_reaches_target']
    np.testing.assert_array_equal(cv.nearest_binary(points['x_star']),result['binary64']['rounded']['point'])
    arrays.close();assert before=={p.name:sha(p) for p in (BASE/'fix').iterdir()}
    (BASE/'reverification'/'fix.json').write_text(json.dumps(dict(straddling_reproduced=True,columns_identical=True,gradient_checks=checks,
        verdict_100=verdict,outputs_unchanged=True,optimizer_launched=False),indent=2)+'\n');print(json.dumps(checks),flush=True)


def switch():
    import worker_switch as w
    case=os.environ['UAV_R2_CASE'];stored=json.loads((BASE/'switch'/f'{case}.json').read_text())
    again=json.loads(json.dumps(w.count(case)));assert again==stored,case
    (BASE/'reverification'/f'switch-{case}.json').write_text(json.dumps(dict(case=case,identical=True),indent=2)+'\n')


def main():
    import driver
    with driver.guard.protocol_lock():
        targets=driver.guard.read(BASE/'targets.json');driver.check_inputs(targets);(BASE/'reverification').mkdir(exist_ok=False)
        base=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1')
        subprocess.run([sys.executable,str(Path(__file__).resolve()),'--fix'],env=dict(base,UAV_R2_CASE=targets['fix']['context']['case']),check=True)
        for r in targets['switch']['states']:
            subprocess.run([sys.executable,str(Path(__file__).resolve()),'--switch'],env=dict(base,UAV_R2_CASE=r['case']),check=True)
        driver.check_inputs(targets);print(json.dumps(dict(fix_rechecked=True,switch_rechecked=len(targets['switch']['states']),inputs_unchanged=True)))


if __name__=='__main__':
    if '--fix' in sys.argv:fix()
    elif '--switch' in sys.argv:switch()
    else:main()
