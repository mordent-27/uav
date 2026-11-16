import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import numpy as np
from ledger import decompose

BASE=Path(__file__).resolve().parent


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def worker():
    import helpers as h
    case=os.environ['UAV_R2_CASE'];folder=BASE/'states'/case
    before={p.name:sha(p) for p in folder.iterdir()}
    result=json.loads((folder/'result.json').read_text());data=np.load(folder/'samples.npz')
    source=h.ROOT/result['source'];point=h.ROOT/result['point_source']
    assert sha(source)==result['source_sha256'] and sha(point)==result['point_sha256']
    state=dict(json.loads(source.read_text()),y=json.loads(point.read_text())['y'])
    f=h.stage4.Frozen(state);y=np.array(state['y']);np.testing.assert_array_equal(y,data['y'])
    H,_=h.decomposition.hessian_of_al(f,y,1e-7)
    np.testing.assert_allclose(H,data['H'],atol=1e-9,rtol=1e-9)
    jac=f.m.jacobian(y);np.testing.assert_allclose(jac,data['jac'],atol=1e-12,rtol=1e-12)
    for row in result['rows']:
        for sign in ['plus','minus']:
            item=row[sign];i=item['point_index'];p=data['points'][i]
            value,gradient=f.eval(p);hn,gn=f.m.h.copy(),f.m.g.copy()
            stable,_=f.eval(p,stable=True)
            np.testing.assert_allclose(gradient,data['gradients'][i],atol=1e-10,rtol=1e-9)
            np.testing.assert_allclose(hn,data['hs'][i],atol=1e-15,rtol=1e-12)
            np.testing.assert_allclose(gn,data['gs'][i],atol=1e-15,rtol=1e-12)
            np.testing.assert_allclose(value,item['value'],atol=1e-15,rtol=1e-12)
            np.testing.assert_allclose(stable,item['stable'],atol=1e-22,rtol=1e-10)
            parts=decompose(p-y,data['h0'],data['g0'],hn,gn,f.lam,f.mu,f.rho,f.gf,jac)
            np.testing.assert_allclose(parts['stable'],stable,atol=1e-22,rtol=1e-10)
            for key in ['equalities','inequalities','weighted_equality_residual','weighted_inequality_residual']:
                np.testing.assert_allclose(parts[key],item['ledger'][key],atol=1e-25,rtol=1e-10)
    f.close();data.close();assert before=={p.name:sha(p) for p in folder.iterdir()}
    out=BASE/'reverification'/f'{case}.json';assert not out.exists()
    out.write_text(json.dumps(dict(case=case,samples_recomputed=result['samples'],
        native_values_gradients_constraints_and_ledger_reproduced=True,source_and_outputs_unchanged=True,
        optimizer_launched=False),indent=2)+'\n')


def main():
    import driver
    with driver.guard.protocol_lock():
        (BASE/'reverification').mkdir(exist_ok=False)
        for target in json.loads((BASE/'targets.json').read_text())['contexts']:
            env=dict(os.environ,UAV_R2_CASE=target['case'],OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
            subprocess.run([sys.executable,str(Path(__file__).resolve())],env=env,check=True)
        print(json.dumps(dict(samples_recomputed=260,optimizer_launched=False)))


if __name__=='__main__':worker() if 'UAV_R2_CASE' in os.environ else main()
