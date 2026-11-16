"""Re-evaluate failed restoration certificates and initial branch identity; never optimize."""
import json
import os
from pathlib import Path
import sys
import numpy as np
import helpers as h
import driver

BASE=Path(__file__).resolve().parent
OUT=BASE/'batches'/os.environ.get('UAV_R3_BATCH','000')
sys.path.insert(0,str(h.ROOT/'scripts'))
import feasible_incumbent as incumbent
import repair_initialization as repair


def read(path):return json.loads(path.read_text())


def main():
    with driver.protocol_lock():
        target=OUT/'restoration-diagnosis.json';assert not target.exists()
        cases=list(dict.fromkeys(n for p in OUT.glob('attempt*.json') for n in read(p)['cases']))
        reports=[];rest=h.load_from(h.R2A,'restore')
        for case in cases:
            raw=read(BASE/'runs'/case/'result.json');outcome=raw.get('outcome')
            if not outcome or outcome['selected_same_final_branch_kkt']:continue
            source=h.ROOT/outcome['solver_source'] if outcome['solver_source'] else None
            report=dict(case=case,selected=outcome['selected'],fixed_branch_infeasibility_proven=False)
            initial=read(BASE/'inputs'/case/'input.json')
            report['initial_audit']=repair.audit(initial)
            if source and (source/'restored/solver.json').exists():
                data=rest.fb.restore_source(read(source/'solution.json'))
                report['same_branch_as_original_with_problem_tolerance_1e_9']=incumbent.same_branch(data,initial)
                report['same_modes_exact']=data['modes']==initial['modes']
                report['same_task_stamps_exact']=data['task_stamp']==initial['task_stamp']
                model=rest.fb.FixedBranch(data,moving=True);saved=read(source/'restored/solver.json')
                point,lam,lam_x=(np.array(saved[k]) for k in ['point','lam','lam_x'])
                measured=model.kkt(point,lam,lam_x);recorded=read(source/'restored/result.json')
                np.testing.assert_allclose(list(measured.values()),list(recorded['raw_kkt'].values()),atol=1e-10,rtol=1e-8)
                report.update(solver_status=recorded['solver_status'],solver_success=recorded['solver_success'],
                    iterations=recorded['iterations'],reason=recorded['reason'],recomputed_raw_kkt=measured)
                if recorded['solver_success'] and max(measured.values())<=1e-6:
                    accepted,checks,_=rest.accept(model,data,point,lam,lam_x)
                    assert not accepted
                    for key in ['min_energy','max_energy']:
                        np.testing.assert_allclose(checks[key],recorded[key],atol=1e-12,rtol=1e-12)
                    report.update(recomputed_acceptance=bool(accepted),recomputed_checks=checks,
                        energy_buffer=rest.fb.ENERGY_BUFFER,
                        observation='KKT/residual tolerance does not by itself imply strict nonnegative replay energy')
            reports.append(report)
        driver.write(target,dict(optimizer_launched=False,outputs_changed=False,cases=reports))
        print(json.dumps(dict(failed_certificates=len(reports),raw_kkt_recomputed=sum('recomputed_raw_kkt' in r for r in reports),
            strict_acceptance_recomputed=sum('recomputed_acceptance' in r for r in reports))))


if __name__=='__main__':main()
