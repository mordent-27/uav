"""Save the four physical starting points and hashes, without optimizing."""
import hashlib
import json
from pathlib import Path
import numpy as np
import helpers as h

BASE=Path(__file__).resolve().parent


def main():
    assert not (BASE/'targets.json').exists()
    cases={};rest=h.load_from(h.R2A,'restore')
    for case in json.loads((BASE/'screening.json').read_text())['selected']:
        folder=BASE/'initializations'/case;guard=json.loads((folder/'guard.json').read_text())
        if guard['accepted']:
            data=json.loads((folder/'input.json').read_text());w=json.loads((folder/'witness.json').read_text())
            m=rest.fb.FixedBranch(data,moving=True);tr=w['solution']
            point=np.r_[np.array(tr['r'])[m.free].ravel(),np.array(tr['e'][1:])*m.range,np.array(tr['s'])*m.p['v_d']]
            from observe import violation
            v=violation(m,point);assert v<=1e-6
            (folder/'starting-point.json').write_text(json.dumps(dict(point=point.tolist(),constraint_violation=v),indent=2)+'\n')
        cases[case]=dict(source=str(folder.relative_to(h.ROOT)),stratum='new_original_negative',construction_accepted=guard['accepted'],
            hashes={str(p.relative_to(h.ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.glob('*.json')})
    (BASE/'targets.json').write_text(json.dumps(dict(cases=cases,arms=['baseline','small_push'],conditional_retry=True),indent=2)+'\n')
    print(json.dumps(dict(cases=list(cases),construction_accepted=sum(r['construction_accepted'] for r in cases.values()))))


if __name__=='__main__':main()
