"""Independent readback against saved dense matrices and original evaluation kernels."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import numpy as np

BASE=Path(__file__).resolve().parent


def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def worker():
    import helpers as h
    from curvature_operator import DirectionalCurvature
    case=os.environ['UAV_R2_CASE'];stage=int(os.environ['UAV_PROFILE_STAGE'])
    folder=BASE/'states'/f'{case}-stage{stage:02d}';before={p.name:sha(p) for p in folder.iterdir() if p.is_file()}
    result=read(folder/'result.json');source=h.ROOT/result['source'];assert sha(source)==result['source_sha256']
    state=read(source);f=h.stage4.Frozen(state);y=np.array(state['y'])
    data=np.load(folder/'vectors.npz');H,_=h.decomposition.hessian_of_al(f,y,1e-7)
    half,_=h.decomposition.hessian_of_al(f,y,5e-8)
    np.testing.assert_allclose(H,data['H'],atol=1e-9,rtol=1e-9)
    np.testing.assert_allclose(half,data['Hhalf'],atol=1e-9,rtol=1e-9)
    op=DirectionalCurvature(f,y);directions=data['directions'];products=np.array([op.matvec(v) for v in directions])
    np.testing.assert_allclose(products,data['products'],atol=1e-9,rtol=1e-9)
    # Match the measurement's matrix-matrix reduction order. Matrix-vector
    # products differ at cancellation-dominated near-null directions for rho=1e8.
    reference=directions@H.T
    alternate=np.array([H@v for v in directions])
    rounding_difference=float(np.max(np.abs(reference-alternate)))
    np.testing.assert_allclose(reference,data['reference'],atol=1e-9,rtol=1e-9)
    errors=[float(np.linalg.norm(p-r))/max(1.,float(np.linalg.norm(r))) for p,r in zip(products,reference)]
    np.testing.assert_allclose(errors,[r['normalized_error'] for r in result['rows']],atol=1e-10,rtol=1e-6)
    f.close();assert before=={p.name:sha(p) for p in folder.iterdir() if p.is_file()}
    out=BASE/'reverification-02'/f'{case}-stage{stage:02d}.json';assert not out.exists()
    out.write_text(json.dumps(dict(case=case,stage=stage,dense_reproduced=True,products_reproduced=True,
        source_and_outputs_unchanged=True,max_normalized_error=max(errors),
        alternate_matvec_max_absolute_difference=rounding_difference,optimizer_launched=False),indent=2)+'\n')


def main():
    import driver
    with driver.guard.protocol_lock():
        (BASE/'reverification-02').mkdir(exist_ok=False)
        for row in read(BASE/'targets.json')['contexts']:
            env=dict(os.environ,UAV_R2_CASE=row['case'],UAV_PROFILE_STAGE=str(row['stage']),
                OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
            subprocess.run([sys.executable,str(Path(__file__).resolve())],env=env,check=True)
        print(json.dumps(dict(contexts_rechecked=4,directions_rechecked=16,optimizer_launched=False)))


if __name__=='__main__':worker() if 'UAV_PROFILE_STAGE' in os.environ else main()
