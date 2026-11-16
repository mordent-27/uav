"""Read back failed input NLPs and their feasible starts; no optimizer is launched."""
import json
import os
from pathlib import Path
import sys
import numpy as np
import helpers as h
import driver

BASE=Path(__file__).resolve().parent
OUT=BASE/'batches'/os.environ.get('UAV_R3_BATCH','001')
sys.path.insert(0,str(h.ROOT/'scripts'))
import repair_initialization as repair


def read(path):return json.loads(path.read_text())
def snapshot(folder):return {str(p.relative_to(folder)):driver.sha(p) for p in folder.rglob('*') if p.is_file()}


def main():
    with driver.protocol_lock():
        target=OUT/'initialization-diagnosis.json';assert not target.exists()
        rest=h.load_from(h.R2A,'restore');reports=[]
        cases=list(dict.fromkeys(n for p in OUT.glob('attempt*.json') for n in read(p)['cases']))
        for case in cases:
            folder=BASE/'initializations'/case
            if not (folder/'result.json').exists():continue
            result=read(folder/'result.json')
            if result['accepted']:continue
            before=snapshot(folder);data=read(folder/'input.json');model=rest.fb.FixedBranch(data,moving=True)
            start=read(folder/'starting-point.json');point0=np.array(start['point'])
            _,constraints,_,_=model.evaluate(point0);constraints=np.array(constraints).ravel()
            violation=float(max(0.,max(abs(constraints[:model.me])),max(constraints[model.me:],default=-np.inf),
                max(model.lb-point0),max(point0-model.ub)))
            np.testing.assert_allclose(violation,start['constraint_violation'],atol=1e-10,rtol=1e-8)
            assert violation<=1e-6
            saved=read(folder/'solver.json');point,lam,lam_x=(np.array(saved[k]) for k in ['point','lam','lam_x'])
            measured=model.kkt(point,lam,lam_x)
            np.testing.assert_allclose(list(measured.values()),list(result['raw_kkt'].values()),atol=1e-10,rtol=1e-8)
            audit=repair.audit(read(folder/'witness.json'));assert audit['accepted']
            unchanged=before==snapshot(folder);assert unchanged
            reports.append(dict(case=case,solver_status=result['solver_status'],iterations=result['iterations'],
                numerically_feasible_start_confirmed=True,recomputed_start_violation=violation,
                returned_point_KKT=measured,witness_audit=audit,source_files_unchanged=unchanged,
                fixed_assignment_infeasibility_proven=False,
                interpretation='The input NLP start meets its bounds and constraints within 1e-6. Its failed solver point does not prove infeasibility.'))
        driver.write(target,dict(optimizer_launched=False,outputs_changed=False,cases=reports))
        print(json.dumps(dict(failed_initializations=len(reports),feasible_starts_recomputed=sum(r['numerically_feasible_start_confirmed'] for r in reports))))


if __name__=='__main__':main()
