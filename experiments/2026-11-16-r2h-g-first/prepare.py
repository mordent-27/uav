"""Export the original input state without repairing it or optimizing anything."""
import copy
import json
import os
import numpy as np
import helpers as h


def main():
    h.INPUT.mkdir(parents=True,exist_ok=False)
    m=h.fidelity.Variant('R');y=m.native.y.copy();data=copy.deepcopy(m.source)
    tr=h.tr.decode(m,y,m.source);data['solution']=copy.deepcopy(tr);data['init']=copy.deepcopy(tr)
    full=[tr['r'][stamp] for stamp in data['task_stamp']]
    assert max(np.linalg.norm(np.array(a)-b) for a,b in zip(full,data['instance']['tasks']))<=1e-9
    data['instance']['tasks']=full
    h.write(h.INPUT/'input.json',data);h.write(h.INPUT/'original-state.json',dict(y=y.tolist(),scale=m.scale.tolist()))
    cached=os.environ.get('UAV_R2H_CANONICAL_INPUT')
    if cached:
        prior=h.ROOT/cached
        np.testing.assert_array_equal(y,json.loads((prior/'original-state.json').read_text())['y'])
        old=json.loads((prior/'input.json').read_text())
        for key in ['solution','instance','phys','modes','task_stamp']:assert data[key]==old[key],key
    m.close()


if __name__=='__main__':main()
