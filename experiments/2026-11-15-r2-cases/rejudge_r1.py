"""Judge the saved R1 restoration point with the acceptance rule of PLAN.md. No solve. UAV_R2_CASE=fig1."""
import json

import numpy as np
import helpers as h

restore = h.load_from(h.BASE, 'restore')


def main():
    assert h.CASE == 'fig1' and not (h.BASE/'r1-rejudged.json').exists()
    data = restore.fb.restore_source(json.loads((h.R1/'solution.json').read_text()))
    saved = json.loads((h.R1/'restored/solver.json').read_text())
    old = json.loads((h.R1/'restored/result.json').read_text())
    model = restore.fb.FixedBranch(data, moving=True)
    accepted, report, output = restore.accept(model, data, *(np.array(saved[k]) for k in ['point', 'lam', 'lam_x']))
    h.write(h.BASE/'r1-rejudged.json', dict(source='../2026-11-15-original-init/restored/solver.json', solved_again=False,
        accepted_under_R1_plan=old['accepted'], accepted_under_R2a_rule=accepted,
        limits=dict(residual=restore.RESIDUAL_LIMIT, correction=restore.CORRECTION_LIMIT, kkt=restore.KKT_LIMIT),
        solver_status=saved['solver_status'], iterations=saved['iterations'], raw_kkt=saved['raw_kkt'],
        modes=model.modes, task_stamp=data['task_stamp'], **report))
    if accepted:
        output['stages'] = []
        output['metrics'] = dict(objective=report['objective'], init_objective=sum(output['init']['s']),
            converged=False, stamps=model.n, seconds=0., **report['original_residuals'])
        output['diagnostic'] = dict(method='R1 restoration point judged again with the R2a rule; not solved again',
            paper_algorithm=False, branch_kkt=report['final_kkt'], branch_kkt_pass=True,
            source='../2026-11-15-original-init/solution.json', energy_buffer=restore.fb.ENERGY_BUFFER)
        h.write(h.BASE/'r1-rejudged-solution.json', output)
    print(json.dumps(dict(accepted=accepted, objective=report['objective'], checks=report.get('checks'),
        residual=report['original_residuals']['viol'], min_energy=report['min_energy'])), flush=True)


if __name__ == '__main__':
    main()
