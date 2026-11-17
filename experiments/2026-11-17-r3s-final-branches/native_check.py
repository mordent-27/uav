"""Cross-check all final constraint rows against the frozen Rust evaluator; no solver."""
import csv
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

BASE=Path(__file__).resolve().parent;ROOT=BASE.parents[1]
CASES=['tau8-seed8000006','tau8-seed8000062']


def read(p):return json.loads(p.read_text())


def main():
    libraries=read(ROOT/'experiments/2026-11-17-r3s-step-profile/library-index.json')
    for name,digest in libraries.items():assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==digest
    if '--case' not in sys.argv:
        assert not (BASE/'native-model-check.json').exists()
        results=[]
        for case in CASES:
            result=subprocess.run([sys.executable,__file__,'--case',case],check=True,capture_output=True,text=True)
            results.append(json.loads(result.stdout))
        (BASE/'native-model-check.json').write_text(json.dumps(dict(results=results,libraries=libraries,new_solves=0,stationarity_recomputed=False),indent=2)+'\n')
        print(json.dumps(results));return
    case=sys.argv[sys.argv.index('--case')+1]
    import numpy as np
    os.environ['UAV_R2_CASE']=case;os.environ['UAV_R2B_COND']='G'
    sys.path.insert(0,str(ROOT/'experiments/2026-11-15-r2b-coarse'))
    import helpers as h
    raw=read(ROOT/'experiments/2026-11-17-r3s-gradient-e2e/fast/cases/G'/case/'result.json')
    m=h.fidelity.Variant('R');m.stage(raw['eps'],raw['p'])
    q=np.ascontiguousarray(np.array(raw['y'])*m.scale/m.reference.scale)
    m.reference.eval(q,np.zeros(m.me),np.zeros(m.mi),0.)
    with (BASE/'final-constraints.csv').open() as stream:rows=[r for r in csv.DictReader(stream) if r['case']==case]
    eq=np.array([float(r['value']) for r in rows if r['row_type']=='equality'])
    iq=np.array([float(r['value']) for r in rows if r['row_type']=='inequality'])
    np.testing.assert_allclose(eq,m.reference.h,atol=2e-8,rtol=2e-8)
    np.testing.assert_allclose(iq,m.reference.g,atol=2e-8,rtol=2e-8)
    print(json.dumps(dict(case=case,equalities=len(eq),inequalities=len(iq),
         max_eq_absolute_error=float(max(abs(eq-m.reference.h))),max_ineq_absolute_error=float(max(abs(iq-m.reference.g))),passed=True)))
    m.close()


if __name__=='__main__':main()
