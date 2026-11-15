"""Re-evaluate an already accepted initialization certificate on the failed final branch; no solve."""
import copy
import json
import numpy as np
import helpers as h


def read(path):return json.loads(path.read_text())


def main():
    assert h.CASE=='tau5-seed3'
    rest=h.load_from(h.R2A,'restore');fb=rest.fb
    failed=read(h.HERE/'restored/result.json');assert not failed['accepted']
    final=fb.restore_source(read(h.HERE/'solution.json'));initial=read(h.INIT/'solution.json')
    same=all(final[k]==initial[k] for k in ['modes','task_stamp'])
    report=dict(case=h.CASE,final_restoration_accepted=False,same_assignments=same,
        additional_optimization=False,initialization_accepted=read(h.INIT/'result.json')['accepted'])
    if same:
        model=fb.FixedBranch(final,moving=True)
        saved=read(h.INIT/'solver.json');point,lam,lam_x=(np.array(saved[k]) for k in ['point','lam','lam_x'])
        raw=model.kkt(point,lam,lam_x)
        accepted,checks,output=rest.accept(model,final,point,lam,lam_x)
        valid=bool(report['initialization_accepted'] and max(raw.values())<=1e-6 and accepted)
        report.update(raw_kkt_on_final_branch=raw,acceptance_checks=checks,certificate_valid=valid,
            task_coordinate_difference_km=float(np.max(np.linalg.norm(np.array(final['instance']['tasks'])-
                np.array(initial['instance']['tasks']),axis=1))))
        if valid:
            folder=h.BASE/'diagnostics'/h.CASE;folder.mkdir(parents=True,exist_ok=False)
            output=copy.deepcopy(output)
            output['metrics']=dict(objective=checks['objective'],init_objective=sum(output['init']['s']),
                converged=False,stamps=model.n,seconds=0.,**checks['original_residuals'])
            output['diagnostic']=dict(method='readback of accepted initialization certificate on final branch; no new solve',
                paper_algorithm=False,branch_kkt=checks['final_kkt'],branch_kkt_pass=True)
            output['stages']=[];h.write(folder/'incumbent.json',output)
    h.write(h.BASE/'restore-certificate-recheck.json',report)
    print(json.dumps(report),flush=True)


if __name__=='__main__':main()
