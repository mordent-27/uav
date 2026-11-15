"""Recompute stored certificates and keep physical outputs; never launch an optimizer."""
import copy
import hashlib
import json
from pathlib import Path
import sys
from time import monotonic
import numpy as np
import helpers as h

sys.path.insert(0,str(h.ROOT/'scripts'))
import feasible_incumbent as incumbent


def read(path):return json.loads(path.read_text())


def certificate(rest,data,saved,solver_accepted):
    report=dict(accepted=False,additional_optimization=False)
    try:
        model=rest.fb.FixedBranch(data,moving=True)
        point,lam,lam_x=(np.array(saved[k]) for k in ['point','lam','lam_x'])
        if len(point)!=int(model.v.numel()) or len(lam)!=model.me+model.mi or len(lam_x)!=len(point):
            return None,dict(report,reason='certificate_dimensions_mismatch')
        raw=model.kkt(point,lam,lam_x)
        report['raw_kkt']=raw
        if not solver_accepted or max(raw.values())>1e-6:
            return None,dict(report,reason='source_solver_flag_or_recomputed_KKT')
        accepted,checks,output=rest.accept(model,data,point,lam,lam_x)
        report.update(accepted=bool(accepted),checks=checks)
        if not accepted:return None,report
        output=copy.deepcopy(output)
        output['metrics']=dict(objective=checks['objective'],init_objective=sum(output['init']['s']),
            converged=False,stamps=model.n,seconds=0.,**checks['original_residuals'])
        output['diagnostic']=dict(method='stored fixed-branch certificate re-evaluated without optimization',
            paper_algorithm=False,branch_kkt=checks['final_kkt'],branch_kkt_pass=True)
        output['stages']=[]
        return output,report
    except (AssertionError,ValueError,RuntimeError,KeyError) as error:
        return None,dict(report,reason=repr(error))


def finalize(case,solver_folder,init_folder,destination,allow_repair_backups):
    start=monotonic();destination.mkdir(parents=True,exist_ok=False)
    reference=read(init_folder/'input.json');candidates={'original':reference}
    if allow_repair_backups:
        for label,name in [('constructed','witness.json'),('initialization','solution.json')]:
            path=init_folder/name
            if path.exists():candidates[label]=read(path)
    raw=read(solver_folder/'result.json') if solver_folder else None
    final_data=None;restoration=dict(accepted=False);restored_recheck=dict(accepted=False,reason='not_available')
    init_recheck=dict(accepted=False,reason='not_available')
    rest=h.load_from(h.R2A,'restore')
    if solver_folder:
        final_data=rest.fb.restore_source(read(solver_folder/'solution.json'))
        restored_folder=solver_folder/'restored'
        if (restored_folder/'result.json').exists():restoration=read(restored_folder/'result.json')
        if restoration['accepted']:
            checked,restored_recheck=certificate(rest,final_data,read(restored_folder/'solver.json'),
                restoration.get('solver_success',False))
            assert restored_recheck['accepted'],'accepted restoration certificate failed independent readback'
            original=read(restored_folder/'solution.json')
            for key in ['r','e','s','c']:
                np.testing.assert_allclose(checked['solution'][key],original['solution'][key],atol=1e-12,rtol=1e-12)
            candidates['restoration']=original
        if allow_repair_backups and (init_folder/'result.json').exists():
            initialization=read(init_folder/'result.json')
            if initialization['accepted'] and 'initialization' in candidates:
                same=incumbent.same_branch(final_data,candidates['initialization'])
                if same:
                    checked,init_recheck=certificate(rest,final_data,read(init_folder/'solver.json'),
                        initialization.get('solver_success',False))
                    if init_recheck['accepted']:
                        candidates['certificate']=checked
                        h.write(destination/'certificate.json',checked)
                else:init_recheck=dict(accepted=False,reason='different_problem_or_final_assignment')
    selected,selection=incumbent.select(reference,candidates)
    chosen=selection['selected']
    final_certificate=bool((chosen=='restoration' and restored_recheck['accepted']) or
                           (chosen=='certificate' and init_recheck['accepted']))
    preserved=None
    if selected is not None:
        h.write(destination/'selected.json',selected)
        if chosen=='restoration':
            preserved=(destination/'selected.json').read_bytes()==(solver_folder/'restored/solution.json').read_bytes()
            assert preserved,'successful output must be preserved exactly'
    common=bool(raw and raw['final_common_pass']);physical=bool(raw and raw['final_both_scales_pass'])
    result=dict(case=case,final_common_kkt=common,final_both_scales_kkt=physical,
        last_restoration_solver_accepted=restoration['accepted'],
        restoration_attempted=bool(solver_folder and (solver_folder/'restored/result.json').exists()),
        physical_point_available=selection['feasible_available'],selected=chosen,
        selected_hours=None if selected is None else float(sum(selected['solution']['s'])),
        selected_same_final_branch_kkt=final_certificate,
        common_kkt_and_final_certificate=common and final_certificate,
        both_scales_kkt_and_final_certificate=physical and final_certificate,
        successful_restoration_preserved_exactly=preserved,
        initialization_certificate_valid=init_recheck['accepted'],
        solver_source=None if solver_folder is None else str(solver_folder.relative_to(h.ROOT)),
        initialization_source=str(init_folder.relative_to(h.ROOT)),
        allow_repair_backups=allow_repair_backups,seconds=monotonic()-start,
        selected_sha256=None if selected is None else hashlib.sha256((destination/'selected.json').read_bytes()).hexdigest(),
        returned_point_smoothing_kkt_not_inferred=True,paper_reproduction=False)
    h.write(destination/'validation.json',dict(selection=selection,restoration_certificate=restored_recheck,
        initialization_certificate=init_recheck))
    h.write(destination/'result.json',result)
    return result
