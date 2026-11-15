"""Aggregate the saved R2g outputs. Reads only; solves nothing; standard library only.

Three strata are kept apart and never added together:
  (i)   regression, unchanged outputs: the 21 replayed R2f cases without tau5-seed3 (20, all seen before);
  (ii)  the design case tau5-seed3 (in no denominator and no success count);
  (iii) the negative-battery cohort: 4 screened inputs, control and repaired phase each (a sample
        conditioned on a negative initial battery; not a population rate).
Writes summary.json and comparison.md (derived files of this script; re-running regenerates them).
"""
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
from time import monotonic

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
R2F = HERE.parent/'2026-11-15-r2f-general-init'
DESIGN = 'tau5-seed3'
INDICATORS = ['final_common_kkt', 'final_both_scales_kkt', 'last_restoration_solver_accepted',
    'physical_point_available', 'selected_same_final_branch_kkt', 'both_scales_kkt_and_final_certificate']
DEFINITIONS = dict(
    final_common_kkt='final smoothed AL point, common scale, max KKT <= 1e-6',
    final_both_scales_kkt='same final AL point, also physical-variable scale <= 1e-6',
    last_restoration_solver_accepted='the last fixed-branch Ipopt restoration was accepted',
    physical_point_available='a returnable original-feasible point exists (original residual <= 1e-6, battery strictly in [0,1], assigned stamps and modes)',
    selected_same_final_branch_kkt='fixed-branch KKT <= 1e-6 at the returned point; km-scaled measure of fixed_branch.py with a 1e-8 battery margin, a different measure from the two AL KKT columns',
    both_scales_kkt_and_final_certificate='conjunction of two different points: smoothed KKT at the final AL point (not original-feasible) and the fixed-branch certificate at the returned point')


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path):
    return str(path.relative_to(ROOT))


def git(*args):
    return subprocess.run(['git', *args], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def positions(document):
    """Full-precision positions of a smoothed AL point (experiment.y_full_precision), else the stored ones."""
    tr = document['solution']
    n = len(tr['r'])
    y = document.get('experiment', {}).get('y_full_precision')
    if y is None:
        return tr['r']
    return [document['instance']['r0']]+[[y[2*i], y[2*i+1]] for i in range(n-2)]+[document['instance']['rf']]


def evaluation(folder, stratum, kind):
    result, validation = read(folder/'result.json'), read(folder/'validation.json')
    source = ROOT/result['solver_source']
    raw, restored = read(source/'result.json'), read(source/'restored/result.json')
    selected = read(folder/'selected.json')
    final = read(source/'solution.json')
    distance = [math.dist(a, b) for a, b in zip(positions(final), selected['solution']['r'])]
    coordinate = [abs(u-v) for a, b in zip(positions(final), selected['solution']['r']) for u, v in zip(a, b)]
    selected_sha = sha(folder/'selected.json')
    restored_path = source/'restored/solution.json'
    init_reason = validation['initialization_certificate'].get('reason')
    row = dict(case=result['case'], stratum=stratum, kind=kind, folder=rel(folder),
        **{key: result[key] for key in INDICATORS},
        initialization_certificate_valid=result['initialization_certificate_valid'],
        restoration_attempted=result['restoration_attempted'], selected=result['selected'],
        selected_hours=result['selected_hours'], selected_sha256=selected_sha,
        selected_sha256_matches_result=selected_sha == result['selected_sha256'],
        restored_solution_exists=restored_path.exists(),
        selected_equals_restored_solution_sha256=restored_path.exists() and sha(restored_path) == selected_sha,
        certificate_file_written=(folder/'certificate.json').exists(),
        initialization_certificate_reason=init_reason,
        restoration_certificate_reason=validation['restoration_certificate'].get('reason'),
        candidates={name: dict(accepted=c['accepted'], objective_hours=c.get('objective_hours'),
            reason=c.get('reason')) for name, c in validation['selection']['candidates'].items()},
        solver_source=result['solver_source'], initialization_source=result['initialization_source'],
        final_al=dict(objective_hours=raw['objective'], common_kkt_max=max(raw['common_kkt'].values()),
            physical_kkt_max=max(raw['paper_units_kkt'].values()), stop=raw['stop'], total_outer=raw['total_outer'],
            elapsed_seconds=raw['elapsed'], original_residual=raw['selection']['audit']['original_residuals']['viol'],
            pure_mode_min_energy=raw['selection']['audit'].get('pure_mode_min_energy')),
        last_restoration=dict(accepted=restored['accepted'], solver_status=restored.get('solver_status'),
            iterations=restored.get('iterations'), objective_hours=restored.get('objective'),
            seconds=restored.get('seconds'), reason=restored.get('reason')),
        final_al_to_returned_point=dict(max_position_distance_km=max(distance), max_coordinate_difference_km=max(coordinate),
            returned_minus_final_al_seconds=3600*(result['selected_hours']-raw['objective'])),
        retention_seconds=result['seconds'])
    return row


def returned_points(control, repaired, initialization):
    gap = lambda a, b: max(math.dist(p, q) for p, q in zip(a['solution']['r'], b['solution']['r']))
    return dict(control_and_repaired_same_modes=control['modes'] == repaired['modes'],
        control_and_repaired_same_task_stamps=control['task_stamp'] == repaired['task_stamp'],
        control_charging_segments=sum(m >= 0 for m in control['modes']),
        repaired_charging_segments=sum(m >= 0 for m in repaired['modes']),
        control_to_repaired_max_position_distance_km=gap(control, repaired),
        repaired_and_initialization_same_modes=repaired['modes'] == initialization['modes'],
        repaired_to_initialization_nlp_max_position_distance_km=gap(repaired, initialization))


def count(rows):
    return {key: sum(bool(r[key]) for r in rows) for key in INDICATORS}


def firings(rows, missing):
    return dict(evaluations=len(rows),
        accepted_restoration_returned_unchanged=sum(r['selected'] == 'restoration' for r in rows),
        returned_by_reevaluated_certificate=sum(r['selected'] == 'certificate' for r in rows),
        physical_point_fallback_minimum_time=sum(r['selected'] in ('original', 'constructed', 'initialization') for r in rows),
        no_returnable_point=sum(r['selected'] is None for r in rows),
        certificate_refused_for_different_branch=sum(r['initialization_certificate_reason'] == 'different_problem_or_final_assignment' for r in rows),
        missing_route=missing,
        byproduct_initialization_certificate_valid=sum(bool(r['initialization_certificate_valid']) for r in rows),
        byproduct_certificate_files_written=sum(r['certificate_file_written'] for r in rows))


def tasks_of(path):
    return read(path)['instance']['tasks']


def relation(a, b):
    shared = sum(any(math.dist(p, q) <= 1e-9 for q in b) for p in a)
    prefix = 0
    for p, q in zip(a, b):
        if math.dist(p, q) > 1e-9:
            break
        prefix += 1
    return shared, prefix


def fmt(value, digits=9):
    return '—' if value is None else f'{value:.{digits}f}'


def mark(flag):
    return '○' if flag else '×'


def main():
    start = monotonic()
    execution, screening = read(HERE/'execution.json'), read(HERE/'screening.json')
    old = read(R2F/'summary.json')
    old_rows = {row['case']: row for row in old['cases']}
    jobs = {job['case']: job for job in execution['jobs']}
    assert len(jobs) == len(execution['jobs'])
    regression_cases = [job['case'] for job in execution['jobs'] if job['group'] == 'regression']
    new_cases = [job['case'] for job in execution['jobs'] if job['group'] == 'negative_holdout']
    assert sorted(regression_cases) == sorted(old_rows) and new_cases == screening['selected']
    assert sorted(p.name for p in (HERE/'regression').iterdir()) == sorted(regression_cases)
    for kind in ['original', 'repaired']:
        assert sorted(p.name for p in (HERE/'evaluations'/kind).iterdir()) == sorted(new_cases)
        assert sorted(p.name for p in (HERE/'cases'/kind).iterdir()) == sorted(new_cases)

    regression = [evaluation(HERE/'regression'/case, 'design' if case == DESIGN else 'regression_unchanged', 'replay')
        for case in regression_cases]
    unchanged = [r for r in regression if r['case'] != DESIGN]
    design = next(r for r in regression if r['case'] == DESIGN)
    control = [evaluation(HERE/'evaluations/original'/case, 'negative_battery_cohort', 'control') for case in new_cases]
    repaired = [evaluation(HERE/'evaluations/repaired'/case, 'negative_battery_cohort', 'repaired') for case in new_cases]
    missing_new = sum(any(step['script'] == 'missing' for step in jobs[case]['steps']) for case in new_cases)
    steps_ok = sum(read(folder/'steps.json') == dict(run='ok', restore='ok', verify='ok') for folder in (HERE/'cases').glob('*/*'))

    # PLAN.md:26 -- outputs whose last restoration was accepted are returned byte-for-byte.
    accepted_regression = [r for r in regression if r['last_restoration_solver_accepted']]
    preservation = dict(
        regression_outputs_with_accepted_restoration=len(accepted_regression),
        regression_selected_sha256_equals_source_restored_solution=sum(r['selected_equals_restored_solution_sha256'] for r in accepted_regression),
        # same file; the two numbers are sum(s) by Python and by NumPy, so they may differ in the last bits
        regression_max_abs_selected_hours_minus_r2f_candidate_hours=max(abs(r['selected_hours']-old_rows[r['case']]['candidate']['hours']) for r in accepted_regression),
        new_phases_with_accepted_restoration=sum(r['last_restoration_solver_accepted'] for r in control+repaired),
        new_phase_selected_sha256_equals_restored_solution=sum(r['selected_equals_restored_solution_sha256'] for r in control+repaired),
        all_selected_sha256_match_result_json=sum(r['selected_sha256_matches_result'] for r in regression+control+repaired),
        not_preserved=[r['case'] for r in regression if not r['selected_equals_restored_solution_sha256']])

    # PLAN.md:28 -- the saved output keeps only the reference; reason and hash are supplied here, after the run.
    refused = R2F/'cases/repaired'/DESIGN/'restored/result.json'
    refused_result = read(refused)
    tracked = git('ls-files', '--error-unmatch', rel(refused)).returncode == 0
    unmodified = git('diff', '--quiet', 'HEAD', '--', rel(refused)).returncode == 0
    plan28 = dict(supplemented_after_the_run_by='analyze.py', saved_outputs_changed=False,
        plan_line='PLAN.md:28 asks for reason/reference/hash of the unaccepted R2f result in the adopted result',
        saved_reference=design['solver_source'],
        saved_validation_restoration_certificate=read(HERE/'regression'/DESIGN/'validation.json')['restoration_certificate'],
        saved_reason_is_misleading='not_available is the initial value in retain.py; the restoration was attempted and not accepted',
        source=rel(refused), source_sha256=sha(refused),
        source_solver_json_sha256=sha(refused.parent/'solver.json'),
        source_git_tracked=tracked, source_git_unmodified_vs_head=unmodified,
        source_git_blob=git('hash-object', rel(refused)).stdout.strip(),
        head_git_blob=git('rev-parse', 'HEAD:'+rel(refused)).stdout.strip(),
        accepted=refused_result['accepted'], solver_status=refused_result['solver_status'],
        solver_success=refused_result['solver_success'], iterations=refused_result['iterations'],
        raw_kkt=refused_result['raw_kkt'], reason=refused_result['reason'], seconds=refused_result['seconds'])

    # PLAN.md:37 -- every audited input and the denominators of the stopping rule.
    audited = [dict(order=i+1, case=row['case'], tau=row['tau'], seed=row['seed'],
        original_residual=row['audit']['original_residuals']['viol'], minimum_battery=row['audit']['min_energy'],
        minimum_stored_battery=row['minimum_stored_energy'], negative_battery=row['negative_battery'],
        selected=row['selected'], initial_y_sha256=row['initial_y_sha256']) for i, row in enumerate(screening['rows'])]
    y_checks = []
    for case in new_cases:
        state = read(HERE/'screened-inputs'/case/'state.json')
        digest = hashlib.sha256(json.dumps(state['y']).encode()).hexdigest()
        recorded = next(row['initial_y_sha256'] for row in screening['rows'] if row['case'] == case)
        y_checks.append(dict(case=case, screened_state_hash_matches_screening=digest == recorded,
            same_y_in_initializations=state['y'] == read(HERE/'initializations'/case/'original-state.json')['y'],
            same_y_in_control_source=state['y'] == read(HERE/'cases/original'/case/'source.json')['y'],
            same_input_document=read(HERE/'screened-inputs'/case/'input.json') == read(HERE/'initializations'/case/'input.json')))
    ranges = []
    for item in screening['ranges']:
        rows = [a for a in audited if a['tau'] == item['tau']]
        ranges.append(dict(tau=item['tau'], seed_start=item['start'], seed_end=item['end'],
            seeds_in_range=item['end']-item['start']+1, audited=len(rows), audited_seeds=[a['seed'] for a in rows],
            negative_battery=sum(a['negative_battery'] for a in rows), selected=sum(a['selected'] for a in rows),
            stopped_at_second_negative=sum(a['negative_battery'] for a in rows) == 2 and rows[-1]['negative_battery']))
    screening_summary = dict(rule=screening['rule'], audited=len(audited), selected=len(new_cases),
        negative_frequency_not_estimable='the scan stops at the second negative-battery input of each range, so 4 of 8 is produced by the stopping rule',
        ranges=ranges, rows=audited, selected_input_checks=y_checks, seconds=screening['seconds'])

    # Objective (mission time).
    new_objective = []
    for c, r in zip(control, repaired):
        case = c['case']
        init = read(HERE/'initializations'/case/'result.json')
        guard = read(HERE/'initializations'/case/'guard.json')
        new_objective.append(dict(case=case, original_minimum_battery=init['initial_min_energy'],
            original_initial_hours_infeasible=init['initial_objective'], constructed_witness_hours=guard['objective_hours'],
            construction_position_changes=len(guard['changes']),
            initialization_nlp_accepted=init['accepted'], initialization_nlp_hours=init['objective'],
            initialization_nlp_iterations=init['iterations'],
            control_selected=c['selected'], control_hours=c['selected_hours'], control_final_al_hours=c['final_al']['objective_hours'],
            repaired_selected=r['selected'], repaired_hours=r['selected_hours'], repaired_final_al_hours=r['final_al']['objective_hours'],
            repaired_minus_control_hours=r['selected_hours']-c['selected_hours'],
            repaired_minus_control_seconds=3600*(r['selected_hours']-c['selected_hours']),
            repaired_minus_initialization_nlp_seconds=3600*(r['selected_hours']-init['objective']),
            control_minus_initialization_nlp_seconds=3600*(c['selected_hours']-init['objective']),
            control_and_repaired_selected_sha256_equal=c['selected_sha256'] == r['selected_sha256'],
            **returned_points(read(HERE/'evaluations/original'/case/'selected.json'),
                read(HERE/'evaluations/repaired'/case/'selected.json'), read(HERE/'initializations'/case/'solution.json')),
            control_inner_accepted=read(HERE/'cases/original'/case/'verification.json')['accepted_inner_points'],
            repaired_inner_accepted=read(HERE/'cases/repaired'/case/'verification.json')['accepted_inner_points']))
    regression_objective = []
    for r in regression:
        before = old_rows[r['case']]
        base, cand = before['baseline']['hours'], before['candidate']['hours']
        regression_objective.append(dict(case=r['case'], r2f_group=before['group'], r2f_action=before['action'],
            selected=r['selected'], r2g_hours=r['selected_hours'], r2f_control_hours=base, r2f_candidate_hours=cand,
            r2g_minus_r2f_control_seconds=None if base is None else 3600*(r['selected_hours']-base),
            r2g_minus_r2f_candidate_seconds=None if cand is None else 3600*(r['selected_hours']-cand),
            r2f_candidate_minus_control_seconds=before['change_seconds']))
    design_init = read(R2F/'initializations'/DESIGN/'result.json')
    # differences below 1e-6 s are the two summation orders of the same file, not a change of the output
    worse = [o for o in regression_objective if o['r2g_minus_r2f_control_seconds'] is not None and o['r2g_minus_r2f_control_seconds'] > 1e-6]
    objective = dict(new_cohort=new_objective, regression=regression_objective,
        regression_longer_than_r2f_control=[dict(case=o['case'], seconds=o['r2g_minus_r2f_control_seconds']) for o in worse],
        new_cohort_repaired_longer_than_control=[dict(case=o['case'], seconds=o['repaired_minus_control_seconds'])
            for o in new_objective if o['repaired_minus_control_seconds'] > 1e-6],
        design_case=dict(case=DESIGN, r2g_hours=design['selected_hours'], source='re-evaluated initialization NLP point (preprocessing), not a result of the final AL',
            r2f_initialization_nlp_hours=design_init['objective'],
            equals_r2f_initialization_nlp_hours=design['selected_hours'] == design_init['objective'],
            r2f_control_hours=old_rows[DESIGN]['baseline']['hours'],
            minus_r2f_control_seconds=3600*(design['selected_hours']-old_rows[DESIGN]['baseline']['hours'])))

    # Cost. This run and the reused past solves are separate; they are never added.
    def step(case, script, kind):
        return next(s['seconds'] for s in jobs[case]['steps'] if s['script'] == script and s['kind'] == kind)
    per_input = []
    for c, r in zip(control, repaired):
        case = c['case']
        guard, init = read(HERE/'initializations'/case/'guard.json'), read(HERE/'initializations'/case/'result.json')
        entry = dict(case=case, job_wall=jobs[case]['seconds'],
            guard_step_wall=step(case, 'guard', 'original'), guard_internal_audit_and_construction=guard['seconds'],
            initialize_step_wall=step(case, 'initialize', 'repaired'), initialization_nlp_internal=init['seconds'],
            control_phase_step_wall=step(case, 'phase', 'original'), control_direct_start_al=c['final_al']['elapsed_seconds'],
            control_restoration=c['last_restoration']['seconds'], control_retention_check=c['retention_seconds'],
            repaired_phase_step_wall=step(case, 'phase', 'repaired'), repaired_direct_start_al=r['final_al']['elapsed_seconds'],
            repaired_restoration=r['last_restoration']['seconds'], repaired_retention_check=r['retention_seconds'])
        entry['control_phase_unitemized'] = entry['control_phase_step_wall']-entry['control_direct_start_al']-entry['control_restoration']-entry['control_retention_check']
        entry['repaired_phase_unitemized'] = entry['repaired_phase_step_wall']-entry['repaired_direct_start_al']-entry['repaired_restoration']-entry['repaired_retention_check']
        per_input.append(entry)
    total = lambda key: sum(e[key] for e in per_input)
    reused = []
    for r in regression:
        source = ROOT/r['solver_source']
        init_folder = ROOT/r['initialization_source']
        init = read(init_folder/'result.json') if (init_folder/'result.json').exists() else None
        reused.append(dict(case=r['case'], solver_source=r['solver_source'], direct_start_al=r['final_al']['elapsed_seconds'],
            restoration=r['last_restoration']['seconds'], guard_internal=read(init_folder/'guard.json')['seconds'],
            initialization_nlp_internal=None if init is None else init['seconds']))
    verification_files = {name: read(HERE/name) if (HERE/name).exists() else None
        for name in ['reverification.json', 'output-verification.json', 'retention-recheck.json']}
    unit_log = (HERE/'unit-test-feasible-incumbent.log').read_text() if (HERE/'unit-test-feasible-incumbent.log').exists() else ''
    ran = re.search(r'Ran (\d+) tests? in ([0-9.]+)s', unit_log)
    unit = dict(log='unit-test-feasible-incumbent.log', tests=int(ran.group(1)) if ran else None,
        unittest_seconds=float(ran.group(2)) if ran else None, ok=bool(re.search(r'^OK$', unit_log, re.M)),
        returncode_zero='returncode=0' in unit_log,
        independent=False, note='the tests are built on the tau5-seed3 data (the design case); not an independent validation')
    cost = dict(
        this_run=dict(note='wall-clock of driver.py; the 21 regression jobs only replay saved results',
            driver_wall=execution['seconds'], workers=execution['workers'], blas_threads=execution['blas_threads'],
            job_wall_sum_new_inputs=sum(jobs[c]['seconds'] for c in new_cases),
            job_wall_sum_regression_replay=sum(jobs[c]['seconds'] for c in regression_cases),
            input_audit_internal=dict(seconds=screening['seconds'], inputs=len(audited), process_wall='not recorded'),
            construction=dict(guard_step_wall=total('guard_step_wall'), guard_internal_audit_and_construction=total('guard_internal_audit_and_construction'),
                note='guard.json seconds covers the audit of the original input and the construction together'),
            initialization=dict(initialize_step_wall=total('initialize_step_wall'), nlp_internal=total('initialization_nlp_internal')),
            direct_start=dict(control_al=total('control_direct_start_al'), repaired_al=total('repaired_direct_start_al'),
                control_phase_step_wall=total('control_phase_step_wall'), repaired_phase_step_wall=total('repaired_phase_step_wall')),
            restoration=dict(control=total('control_restoration'), repaired=total('repaired_restoration')),
            retention_check=dict(new_control=total('control_retention_check'), new_repaired=total('repaired_retention_check'),
                regression_internal=sum(r['retention_seconds'] for r in regression),
                regression_replay_step_wall=sum(jobs[c]['seconds'] for c in regression_cases)),
            unitemized_in_phase_steps=dict(control=total('control_phase_unitemized'), repaired=total('repaired_phase_unitemized'),
                note='process start, model build, preflight, existing verifier and file output; no separate record'),
            not_recorded=['precheck.py (reuse-preflight.json has no time)', 'screen.py process wall-clock',
                'existing verifier and preflight inside each phase step'],
            per_input=per_input),
        reused_past_not_in_this_wall_clock=dict(note='read from the reused sources; not added to this run',
            cases=len(reused), direct_start_al=sum(e['direct_start_al'] for e in reused),
            restoration=sum(e['restoration'] for e in reused),
            guard_internal=sum(e['guard_internal'] for e in reused),
            initialization_nlp_internal=sum(e['initialization_nlp_internal'] or 0. for e in reused),
            initialization_nlp_cases=sum(e['initialization_nlp_internal'] is not None for e in reused), per_case=reused),
        post_run_verification=dict(note='this verification, separate from the solve cost; script-internal times',
            reverification_wall=verification_files['reverification.json'] and verification_files['reverification.json']['seconds'],
            rust_check=verification_files['output-verification.json'] and verification_files['output-verification.json']['seconds'],
            retention_recheck=verification_files['retention-recheck.json'] and verification_files['retention-recheck.json']['seconds'],
            unit_test=unit['unittest_seconds'], analyze=None))

    # Input relations: do the new inputs share task points with each other or with the regression inputs?
    new_tasks = {case: tasks_of(HERE/'screened-inputs'/case/'input.json') for case in new_cases}
    old_tasks = {case: tasks_of(R2F/'initializations'/case/'input.json') for case in regression_cases}
    pairs = []
    names = list(new_tasks)
    for i, a in enumerate(names):
        for b in names[i+1:]:
            shared, prefix = relation(new_tasks[a], new_tasks[b])
            pairs.append(dict(a=a, b=b, shared_task_points=shared, common_prefix=prefix))
        for b in old_tasks:
            shared, prefix = relation(new_tasks[a], old_tasks[b])
            pairs.append(dict(a=a, b=b, shared_task_points=shared, common_prefix=prefix))
    environment = [json.dumps({k: read(path)['instance'][k] for k in ['regions', 'r0', 'rf']}, sort_keys=True)
        for path in [HERE/'screened-inputs'/c/'input.json' for c in new_cases]+[R2F/'initializations'/c/'input.json' for c in regression_cases]]
    relations = dict(new_inputs=new_cases, regression_inputs=len(old_tasks), pairs_compared=len(pairs),
        pairs_sharing_a_task_point=sum(p['shared_task_points'] > 0 for p in pairs),
        max_common_prefix=max(p['common_prefix'] for p in pairs), tolerance_km=1e-9,
        same_regions_and_endpoints_in_all_inputs=len(set(environment)) == 1,
        task_counts={case: len(t) for case, t in new_tasks.items()},
        not_checked='the 4 audited but unselected inputs (tau5 seeds 200, 201, 202, 204) were not saved as input files',
        sharing_pairs=[p for p in pairs if p['shared_task_points']],
        r2f_regression_note=read(R2F/'input-relations.json'))

    summary = dict(
        note='diagnostic path (R-scale direct final stage, fixed-branch Ipopt restoration); not the 900-run measurement and not a reproduction of the paper',
        paper_reproduction=False, main_source_changed=False, solves_launched_by_this_analysis=False,
        commits=dict(base='d56963d', plan='a044da9', implementation='aec1831', screened_targets='30d3095',
            head_at_analysis=git('rev-parse', 'HEAD').stdout.strip()),
        execution=dict(jobs=len(jobs), errors=sum(job['error'] is not None for job in jobs.values()),
            nonzero_returncodes=sum(s['returncode'] != 0 for job in jobs.values() for s in job['steps']),
            regression_replay_jobs=len(regression_cases), new_input_jobs=len(new_cases),
            new_phases=len(control)+len(repaired), new_phase_steps_all_ok=steps_ok,
            evaluations=len(regression)+len(control)+len(repaired)),
        indicator_definitions=DEFINITIONS, strata_are_not_added=True,
        strata=dict(
            regression_unchanged=dict(evaluations=len(unchanged), independent=False,
                note='all seen before; includes the 4 R2f holdout inputs (seeds 101, 103, 105, 107), which are not independent here; replay only, no solve',
                indicators=count(unchanged), retention_rule=firings(unchanged, 0)),
            design_case=dict(case=DESIGN, in_any_denominator=False,
                note='the retention rule was designed on this case (PLAN.md:27)',
                indicators={key: design[key] for key in INDICATORS}, retention_rule=firings([design], 0),
                final_al_to_returned_point=design['final_al_to_returned_point'],
                returned_point_satisfies_smoothed_kkt='not evaluated and not implied; the smoothed KKT holds at the final AL point, the certificate at the returned point'),
            negative_battery_cohort=dict(inputs=len(new_cases), conditional_sample=True,
                note='inputs selected because the initial battery is negative; counts, not a population rate',
                control=dict(evaluations=len(control), indicators=count(control), retention_rule=firings(control, 0)),
                repaired=dict(evaluations=len(repaired), indicators=count(repaired), retention_rule=firings(repaired, missing_new)),
                guard_accepted=sum(read(HERE/'initializations'/c/'guard.json')['accepted'] for c in new_cases),
                initialization_nlp_accepted=sum(read(HERE/'initializations'/c/'result.json')['accepted'] for c in new_cases),
                restoration_gained_by_repair=sum(not c['last_restoration_solver_accepted'] and r['last_restoration_solver_accepted'] for c, r in zip(control, repaired)),
                restoration_lost_by_repair=sum(c['last_restoration_solver_accepted'] and not r['last_restoration_solver_accepted'] for c, r in zip(control, repaired)))),
        final_al_point_versus_returned_point=dict(
            note='the returned point is never the final AL point: it is the output of the fixed-branch restoration, or for the design case the re-evaluated initialization point; the conjunction column therefore joins judgments about two points in every evaluation',
            evaluations=len(regression)+len(control)+len(repaired),
            min_max_position_distance_km=min(r['final_al_to_returned_point']['max_position_distance_km'] for r in regression+control+repaired),
            max_max_position_distance_km=max(r['final_al_to_returned_point']['max_position_distance_km'] for r in regression+control+repaired),
            design_case_max_position_distance_km=design['final_al_to_returned_point']['max_position_distance_km'],
            design_case_max_coordinate_difference_km=design['final_al_to_returned_point']['max_coordinate_difference_km'],
            evaluations_farther_than_design_case=sum(r['final_al_to_returned_point']['max_position_distance_km'] >
                design['final_al_to_returned_point']['max_position_distance_km'] for r in regression+control+repaired),
            final_al_points_original_feasible_at_1e_6=sum(r['final_al']['original_residual'] <= 1e-6 for r in regression+control+repaired)),
        preservation=preservation, plan28_supplement=plan28, screening=screening_summary, objective=objective,
        cost=cost, input_relations=relations,
        verification=dict(
            reverification=verification_files['reverification.json'] and {k: v for k, v in verification_files['reverification.json'].items() if k not in ['runs']},
            rust=verification_files['output-verification.json'] and {k: v for k, v in verification_files['output-verification.json'].items() if k != 'paths'},
            retention_recheck=verification_files['retention-recheck.json'] and {k: v for k, v in verification_files['retention-recheck.json'].items() if k != 'rows'},
            unit_test=unit),
        rows=regression+control+repaired)
    summary['cost']['post_run_verification']['analyze'] = monotonic()-start
    (HERE/'summary.json').write_text(json.dumps(summary, indent=2, allow_nan=False)+'\n')

    lines = ['# R2g：区分ごとの集計（analyze.py が summary.json と同時に生成）', '',
        '3区分は合算しない。全件、診断経路（R尺度の直接最終段と固定分岐のIpopt復元）の結果で、900本の測定とは別。', '',
        '## 6指標（区分ごとの件数）', '',
        '最終ALの点の2列と、返却点の固定分岐KKTは別の尺度。右端は別々の点についての判定の論理積。', '',
        '| 区分 | 件数 | 最終共通KKT | 物理変数も合格 | 最後の復元を受理 | 返却できる原実行可能点 | 返却点の固定分岐KKT | 両尺度KKT∧同分岐証明 |',
        '|---|---:|---:|---:|---:|---:|---:|---:|']
    for label, rows in [('(i) 回帰の無変更確認（既見、再求解なし）', unchanged), ('(iii) 新規の負電池群・対照', control), ('(iii) 新規の負電池群・修復側', repaired)]:
        c = count(rows)
        lines.append(f"| {label} | {len(rows)} | "+' | '.join(str(c[key]) for key in INDICATORS)+' |')
    lines += [f"| (ii) 設計例 {DESIGN}（分母に入れない） | 別記 | "+' | '.join(mark(design[key]) for key in INDICATORS)+' |', '',
        '## 保持規則の発動数', '',
        '| 区分 | 評価数 | 受理済み復元をそのまま採用 | 再評価した証明で採用 | 物理点を時間最小で退避 | 返却点なし | 分岐不一致で証明を拒否 | missing経路 | 副産物：初期化証明が有効 |',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for label, rows, missing in [('(i) 回帰の無変更確認', unchanged, 0), ('(ii) 設計例', [design], 0), ('(iii) 対照', control, 0), ('(iii) 修復側', repaired, missing_new)]:
        f = firings(rows, missing)
        lines.append(f"| {label} | {f['evaluations']} | {f['accepted_restoration_returned_unchanged']} | {f['returned_by_reevaluated_certificate']} | "
            f"{f['physical_point_fallback_minimum_time']} | {f['no_returnable_point']} | {f['certificate_refused_for_different_branch']} | {f['missing_route']} | {f['byproduct_initialization_certificate_valid']} |")
    lines += ['', '## (i) 回帰の無変更確認20件と (ii) 設計例：採用時間', '',
        '| 入力 | 採用 | R2g採用 h | R2f対照 h | R2f候補 h | R2g−R2f対照 秒 | R2g−R2f候補 秒 |', '|---|---|---:|---:|---:|---:|---:|']
    for o in regression_objective:
        d = lambda v: '—' if v is None else '0.00' if abs(v) < 5e-3 else f'{v:+.2f}'
        name = o['case']+('（設計例）' if o['case'] == DESIGN else '')
        lines.append(f"| {name} | {o['selected']} | {fmt(o['r2g_hours'])} | {fmt(o['r2f_control_hours']) if o['r2f_control_hours'] is not None else '未受理'} | "
            f"{fmt(o['r2f_candidate_hours']) if o['r2f_candidate_hours'] is not None else '未受理'} | {d(o['r2g_minus_r2f_control_seconds'])} | {d(o['r2g_minus_r2f_candidate_seconds'])} |")
    lines += ['', '## (iii) 新規の負電池群4入力：対照と修復側', '',
        '修復側の採用時間は初期化NLPの解とほぼ同じで、最終ALの探索の成果ではない。', '',
        '| 入力 | 元の最小電池 | 対照の採用 h | 修復側の採用 h | 修復側−対照 h | 修復側−対照 秒 | 初期化NLPの解 h | 修復側−初期化NLP 秒 |',
        '|---|---:|---:|---:|---:|---:|---:|---:|']
    for o in new_objective:
        lines.append(f"| {o['case']} | {o['original_minimum_battery']:.6f} | {fmt(o['control_hours'])} | {fmt(o['repaired_hours'])} | "
            f"{o['repaired_minus_control_hours']:+.3e} | {o['repaired_minus_control_seconds']:+.3e} | {fmt(o['initialization_nlp_hours'])} | {o['repaired_minus_initialization_nlp_seconds']:+.2e} |")
    lines += ['', '## 監査した全入力（選択規則の分母）', '',
        '各範囲を昇順に監査し、負電池が2例見つかった時点で止めた結果。負電池の頻度の推定には使えない。', '',
        '| 順 | 入力 | tau | seed | 原制約残差 | 電池最小 | 負電池 | 対象 |', '|---:|---|---:|---:|---:|---:|---|---|']
    for a in audited:
        lines.append(f"| {a['order']} | {a['case']} | {a['tau']} | {a['seed']} | {a['original_residual']:.3e} | {a['minimum_battery']:+.6f} | "
            f"{'負' if a['negative_battery'] else '—'} | {'選択' if a['selected'] else '—'} |")
    lines.append('')
    for r in ranges:
        lines.append(f"- tau={r['tau']}：seed {r['seed_start']}..{r['seed_end']}（{r['seeds_in_range']}個）のうち {r['audited']} 個を監査、負電池 {r['negative_battery']}、選択 {r['selected']}。")
    lines.append('')
    (HERE/'comparison.md').write_text('\n'.join(lines))
    brief = dict(strata={k: (v['indicators'] if 'indicators' in v else dict(control=v['control']['indicators'], repaired=v['repaired']['indicators']))
        for k, v in summary['strata'].items()}, preservation=preservation, seconds=monotonic()-start)
    print(json.dumps(brief, indent=1))


if __name__ == '__main__':
    main()
