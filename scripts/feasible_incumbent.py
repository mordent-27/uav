"""Keep validated physical trajectories from one execution history.

This module does not certify optimization convergence or trust stored KKT flags.
The caller must independently recompute any certificate it labels as such.
"""
import copy
import math

import repair_initialization as repair


def same_problem(a,b,coordinate_tolerance=1e-9):
    try:
        if a['phys']!=b['phys']:
            return False
        ia,ib=a['instance'],b['instance']
        if any(ia[k]!=ib[k] for k in ['regions','r0','rf']):
            return False
        return len(ia['tasks'])==len(ib['tasks']) and all(
            math.dist(x,y)<=coordinate_tolerance for x,y in zip(ia['tasks'],ib['tasks']))
    except (KeyError,TypeError,ValueError):
        return False


def same_branch(a,b):
    try:
        return (same_problem(a,b) and len(a['solution']['r'])==len(b['solution']['r']) and
                a['modes']==b['modes'] and a['task_stamp']==b['task_stamp'])
    except (KeyError,TypeError):
        return False


def validate(reference,candidate):
    if not same_problem(reference,candidate):
        return dict(accepted=False,reason='different_problem')
    try:
        tr=candidate['solution'];ns=len(tr['s'])
        valid_shape=(len(tr['r'])==len(tr['e'])==ns+1 and len(tr['c'])==len(candidate['modes'])==ns and
            len(candidate['task_stamp'])==len(candidate['instance']['tasks']))
        if not valid_shape:
            return dict(accepted=False,reason='inconsistent_shape')
        checked=repair.audit(candidate)
        checked['objective_hours']=sum(tr['s'])
        checked['max_task_coordinate_difference_km']=max((math.dist(a,b) for a,b in
            zip(reference['instance']['tasks'],candidate['instance']['tasks'])),default=0.)
        return checked
    except (ValueError,KeyError,IndexError,TypeError,OverflowError) as error:
        return dict(accepted=False,reason='physical_validation: '+str(error))


def select(reference,candidates,preferred=('restoration','certificate')):
    """Prefer accepted final output/certificate; otherwise keep the fastest own feasible point."""
    checked={name:validate(reference,data) for name,data in candidates.items()}
    valid=[name for name,result in checked.items() if result['accepted']]
    selected=next((name for name in preferred if name in valid),None)
    if selected is None and valid:
        selected=min(valid,key=lambda name:(checked[name]['objective_hours'],name))
    report=dict(feasible_available=selected is not None,selected=selected,candidates=checked,
        optimization_convergence_not_inferred=True)
    return (copy.deepcopy(candidates[selected]) if selected is not None else None),report
