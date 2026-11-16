"""Part 2: native Hessian and rounding-floor estimates at one saved final checkpoint. No optimizer is called."""
import hashlib
import json
import os
from pathlib import Path
from time import monotonic
import numpy as np
import helpers as h
import kink

BASE=Path(__file__).resolve().parent


def build(case):
    targets=json.loads((BASE/'targets.json').read_text());F=targets['floors']
    row=next(r for r in F['states'] if r['case']==case);state=json.loads((h.ROOT/row['checkpoint']).read_text())
    frozen=h.stage4.Frozen(state);y=np.array(state['y'])
    _,g=frozen.eval(y);g=g.copy();H,asymmetry=h.decomposition.hessian_of_al(frozen,y,F['hessian_step']);frozen.close()
    return targets,row,state,y,g,H,asymmetry


def main():
    case=os.environ['UAV_R2_CASE'];start=monotonic();targets,row,state,y,g,H,asymmetry=build(case)
    stage=json.loads((h.ROOT/row['result']).read_text());w=np.linalg.eigvalsh(H);floors=kink.lowcurv.rounding_floors(H,y)
    threshold=targets['floors']['threshold']
    result=dict(case=case,stage=row['stage'],variables=len(y),rho=state['rho'],stop=stage.get('stop'),
        common_kkt=stage.get('common_kkt'),native_gradient_inf=float(abs(g).max()),eigen_min=float(w[0]),eigen_max=float(w[-1]),
        floors=floors,uniform_rms_over_threshold=floors['uniform_rms']/threshold,uniform_rms_exceeds=floors['uniform_rms']>threshold,
        hessian_sha256=hashlib.sha256(np.ascontiguousarray(H).tobytes()).hexdigest(),raw_asymmetry=asymmetry,
        seconds=monotonic()-start,optimizer_launched=False)
    (BASE/'floors'/f'{case}.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ['case','rho','variables','eigen_max','uniform_rms_over_threshold','stop']}),flush=True)


if __name__=='__main__':main()
