"""Separate-process recheck: part 1 decision gradients at 100 digits, part 2 Hessians rebuilt and compared."""
from decimal import Decimal as D
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


def side():
    import helpers as h
    import kink
    targets=json.loads((BASE/'targets.json').read_text());S=targets['side'];ctx=S['context']
    metadata=json.loads((h.ROOT/ctx['metadata_source']).read_text())['metadata'];result=json.loads((BASE/'side'/'result.json').read_text())
    arrays=np.load(BASE/'side'/'arrays.npz');before={p.name:sha(p) for p in (BASE/'side').iterdir()};checks={}
    for mode in S['modes']:
        piece=result['pieces'][mode];point=[D(v) for v in piece['point']];deadline=monotonic()+600
        pg,tg=kink.central_pair(lambda q:kink.reference.evaluate(q,metadata,S['reference_digits']),
            [lambda q:kink.piece_al(q,metadata,S['reference_digits'],S['index'],mode),lambda q:kink.piece_al(q,metadata,S['reference_digits'])],
            point,S['reference_digits'],S['reference_step'],deadline)
        pg=np.array([float(v) for v in pg]);tg=np.array([float(v) for v in tg])
        dp=float(abs(pg-arrays[f'{mode}_piece_gradient']).max());dt=float(abs(tg-arrays[f'{mode}_true_gradient']).max())
        s=kink.shifted_values(kink.reference.evaluate(point,metadata,S['reference_digits']),metadata,S['reference_digits'])[S['index']]
        verdict,reasons=kink.piece_verdict(float(abs(pg).max()),mode,s,piece['rows'][-1]['other_switches'],S['gradient_inf_target'])
        checks[mode]=dict(piece_gradient_inf_100=float(abs(pg).max()),true_gradient_inf_100=float(abs(tg).max()),
            piece_difference_inf=dp,true_difference_inf=dt,agrees=max(dp,dt)<=S['gradient_agreement_inf'],
            s_100=str(s),verdict_100=verdict,reasons_100=reasons,verdict_reproduced=(verdict,reasons)==(piece['verdict'],piece['reasons']))
    arrays.close();assert before=={p.name:sha(p) for p in (BASE/'side').iterdir()}
    assert all(c['agrees'] and c['verdict_reproduced'] for c in checks.values())
    (BASE/'reverification'/'side.json').write_text(json.dumps(dict(checks=checks,found_reproduced=not any(c['verdict_100']=='valid' for c in checks.values())==(not result['found']),
        outputs_unchanged=True,optimizer_launched=False),indent=2)+'\n');print(json.dumps(checks),flush=True)


def floor():
    import worker_floor as w
    case=os.environ['UAV_R2_CASE'];stored=json.loads((BASE/'floors'/f'{case}.json').read_text())
    targets,row,state,y,g,H,asymmetry=w.build(case);digest=hashlib.sha256(np.ascontiguousarray(H).tobytes()).hexdigest()
    floors=w.kink.lowcurv.rounding_floors(H,y);same=digest==stored['hessian_sha256'] and floors==stored['floors']
    assert same,case
    (BASE/'reverification'/f'floor-{case}.json').write_text(json.dumps(dict(case=case,hessian_identical=True,floors_identical=True),indent=2)+'\n')


def main():
    import driver
    with driver.guard.protocol_lock():
        targets=driver.guard.read(BASE/'targets.json');driver.check_inputs(targets);(BASE/'reverification').mkdir(exist_ok=False)
        base=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1')
        subprocess.run([sys.executable,str(Path(__file__).resolve()),'--side'],env=dict(base,UAV_R2_CASE=targets['side']['context']['case']),check=True)
        for r in targets['floors']['states']:
            subprocess.run([sys.executable,str(Path(__file__).resolve()),'--floor'],env=dict(base,UAV_R2_CASE=r['case']),check=True)
        driver.check_inputs(targets);print(json.dumps(dict(side_rechecked=True,floors_rechecked=len(targets['floors']['states']),inputs_unchanged=True)))


if __name__=='__main__':
    if '--side' in sys.argv:side()
    elif '--floor' in sys.argv:floor()
    else:main()
