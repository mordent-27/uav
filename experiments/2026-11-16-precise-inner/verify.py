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
    from worker import context
    from precision import DecimalEvaluator
    case,targets,metadata,frozen,y=context();method=os.environ['UAV_INNER_METHOD']
    folder=BASE/'inner'/f'{case}-{method}';before={p.name:sha(p) for p in folder.iterdir()}
    result=json.loads((folder/'result.json').read_text())
    trace=[json.loads(s) for s in (folder/'trace.jsonl').read_text().splitlines()]
    assert len(trace)==result['accepted']+1
    np.testing.assert_array_equal(trace[0]['y'],y)
    kernel=DecimalEvaluator(metadata,100,'1e-24');rows=[]
    for index,row in enumerate(trace):
        point=np.array(row['y']);value,g,exact=kernel(point,monotonic()+120)
        native,ng=frozen.eval(point)
        if method=='native':
            np.testing.assert_allclose(native,row['value'],atol=1e-12,rtol=1e-12)
            np.testing.assert_allclose(max(abs(ng)),row['gradient_inf'],atol=1e-12,rtol=1e-9)
        else:
            with localcontext() as ctx:
                ctx.prec=100;assert abs(exact-D(row['value_decimal']))<D('1e-60')
            np.testing.assert_allclose(max(abs(g)),row['gradient_inf'],atol=1e-10,rtol=1e-9)
        rows.append(dict(index=index,gradient_100=g.tolist(),gradient_inf_100=float(max(abs(g))),
            gradient_norm_100=float(np.linalg.norm(g)),value_100=str(exact),
            native_gradient_error_inf=float(max(abs(ng-g)))))
    np.testing.assert_array_equal(trace[-1]['y'],result['y'])
    if method=='decimal':np.testing.assert_allclose(result['gradient'],rows[-1]['gradient_100'],atol=1e-10,rtol=1e-9)
    else:
        _,g=frozen.eval(np.array(result['y']));np.testing.assert_allclose(result['gradient'],g,atol=1e-12,rtol=1e-9)
    with localcontext() as ctx:
        ctx.prec=100;decrease=D(rows[0]['value_100'])-D(rows[-1]['value_100'])
    frozen.close();assert before=={p.name:sha(p) for p in folder.iterdir()}
    out=BASE/'reverification'/f'{case}-{method}.json';assert not out.exists()
    out.write_text(json.dumps(dict(case=case,method=method,points_recomputed=len(rows),
        final_gradient_inf_100=rows[-1]['gradient_inf_100'],passes_gradient_tolerance_100=rows[-1]['gradient_inf_100']<=1e-8,
        initial_gradient_norm_100=rows[0]['gradient_norm_100'],final_gradient_norm_100=rows[-1]['gradient_norm_100'],
        al_decrease_100=str(decrease),source_and_outputs_unchanged=True,rows=rows),indent=2)+'\n')


def main():
    import driver
    with driver.guard.protocol_lock():
        (BASE/'reverification').mkdir(exist_ok=False)
        for row in json.loads((BASE/'targets.json').read_text())['contexts']:
            for method in ['native','decimal']:
                env=dict(os.environ,UAV_R2_CASE=row['case'],UAV_INNER_METHOD=method,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
                subprocess.run([sys.executable,str(Path(__file__).resolve())],env=env,check=True)
        print(json.dumps(dict(inner_solves_rechecked=4,all_gradients_at_100_digits=True)))


if __name__=='__main__':worker() if 'UAV_INNER_METHOD' in os.environ else main()
