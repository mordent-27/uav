"""Part 2: count coordinates whose old-Hessian stencil can cross a battery CC/CV switch at one saved checkpoint. No optimizer."""
import json
import os
from pathlib import Path
import numpy as np
import helpers as h
import fixh

BASE=Path(__file__).resolve().parent


def count(case):
    targets=json.loads((BASE/'targets.json').read_text());S=targets['switch']
    row=next(r for r in S['states'] if r['case']==case);state=json.loads((h.ROOT/row['checkpoint']).read_text())
    frozen=h.stage4.Frozen(state);scale=frozen.m.scale.tolist();ns=frozen.m.stamps-1;phys=dict(frozen.m.source['phys']);frozen.close()
    y=np.array(state['y']);rows=fixh.margins(y,scale,phys,ns);J,reasons=fixh.straddling(rows,scale,phys,ns,S['old_hessian_step'])
    nearest=sorted(rows,key=lambda r:abs(r['margin']))[:3]
    return dict(case=case,stage=row['stage'],rho=state['rho'],segments=ns,applicable_segments=len(rows),straddling=len(J),
        straddling_coordinates=reasons,straddling_segments=sorted({r['segment'] for r in reasons}),
        nearest_margins=[dict(segment=r['segment'],margin=float(r['margin'])) for r in nearest],optimizer_launched=False)


def main():
    case=os.environ['UAV_R2_CASE'];result=count(case)
    (BASE/'switch'/f'{case}.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ['case','rho','straddling','straddling_segments']}),flush=True)


if __name__=='__main__':main()
