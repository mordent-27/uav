"""Separate-process recheck at 100 digits of the gradients and curvatures used for the fixed verdicts."""
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


def worker():
    import worker as w
    import lowcurv as cv
    case=os.environ['UAV_R2_CASE'];folder=BASE/'states'/case;before={p.name:sha(p) for p in folder.iterdir()}
    targets,target,metadata,frozen,y,H=w.load(case);frozen.close()
    result=json.loads((folder/'result.json').read_text());arrays=np.load(folder/'arrays.npz')
    R=targets['rounding'];C=targets['curvature'];rounding=result['rounding']
    np.testing.assert_array_equal(arrays['y'],y);np.testing.assert_array_equal(arrays['H'],H)
    kernel=w.Kernel(metadata,monotonic()+600);points=[[D(s) for s in p] for p in rounding['points']]
    checks={}
    stored={'x0':arrays['gradients'][0],'x1':arrays['gradients'][1],'x3':arrays['gradients'][3],
        'x1r':np.array(rounding['rounded']['x1']['gradient']),'x3r':np.array(rounding['rounded']['x3']['gradient'])}
    for name,point in [('x0',cv.to_decimal(y)),('x1',points[1]),('x3',points[3]),
            ('x1r',cv.to_decimal(rounding['rounded']['x1']['point'])),('x3r',cv.to_decimal(rounding['rounded']['x3']['point']))]:
        g=w.floats(kernel.gradient(point,R['reference_digits'],R['reference_step']))
        difference=w.inf(g-stored[name])
        checks[name]=dict(gradient_inf_100=w.inf(g),difference_from_80_inf=difference,agrees=difference<=R['gradient_agreement_inf'])
    for name in ['x1','x3']:
        np.testing.assert_array_equal(cv.nearest_binary(points[int(name[1:])]),rounding['rounded'][name]['point'])
    verdicts={name:cv.rounding_verdict(checks[name]['gradient_inf_100'],checks[name+'r']['gradient_inf_100'],R['gradient_inf_target'])
        for name in ['x1','x3']}
    assert all(verdicts[n]==rounding['rounded'][n]['verdict'] for n in verdicts)
    x0=cv.to_decimal(y);base=kernel.scalar(x0,C['reference_digits']);curvatures=[]
    for row,v in zip(result['directions'],arrays['directions']):
        plus,minus=cv.shifted(x0,v,C['reference_width'],C['reference_digits'])
        q=cv.second_quotient(kernel.scalar(plus,C['reference_digits']),base,kernel.scalar(minus,C['reference_digits']),
            C['reference_width'],C['reference_digits'])
        curvatures.append(dict(name=row['name'],q100=str(q),identical=str(q)==row['q100'],
            classification=cv.curvature_class(float(q),C['near_zero'])==row['classification'] or not row['valid']))
    assert all(c['identical'] and c['classification'] for c in curvatures)
    floors=cv.rounding_floors(H,y);assert floors==rounding['floors']
    arrays.close();assert before=={p.name:sha(p) for p in folder.iterdir()}
    out=BASE/'reverification'/f'{case}.json';assert not out.exists()
    out.write_text(json.dumps(dict(case=case,gradient_checks=checks,all_gradients_agree=all(c['agrees'] for c in checks.values()),
        verdicts_100=verdicts,curvatures=curvatures,floors_reproduced=True,rounded_points_reproduced=True,
        state_outputs_unchanged=True,scalar_evaluations=kernel.calls,optimizer_launched=False),indent=2)+'\n')
    print(json.dumps(dict(case=case,checks=checks,verdicts=verdicts)),flush=True)


def main():
    import driver
    with driver.guard.protocol_lock():
        driver.check_inputs(driver.guard.read(BASE/'targets.json'));(BASE/'reverification').mkdir(exist_ok=False)
        for row in json.loads((BASE/'targets.json').read_text())['contexts']:
            env=dict(os.environ,UAV_R2_CASE=row['case'],OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
            subprocess.run([sys.executable,str(Path(__file__).resolve()),'--worker'],env=env,check=True)
        driver.check_inputs(driver.guard.read(BASE/'targets.json'))
        print(json.dumps(dict(states_rechecked=2,inputs_unchanged=True)))


if __name__=='__main__':worker() if '--worker' in sys.argv else main()
