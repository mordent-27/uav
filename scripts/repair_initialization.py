"""Construct a physical starting trajectory while preserving its assigned branch.

This is an input-only heuristic, not an optimizer or a proof that unsupported
inputs are infeasible. No case names or waypoint indices enter the algorithm.
"""
import copy
import math

import diagnose_solution as diag


def audit(data, tolerance=1e-6):
    tr, phys = data['solution'], data['phys']
    residual = diag.residuals(data)
    replay = diag.replay(data)
    tasks = all(tr['r'][stamp] == task for stamp, task in zip(data['task_stamp'], data['instance']['tasks']))
    modes = True
    for k, mode in enumerate(data['modes']):
        if mode < 0:
            modes &= tr['c'][k] == 0.
        else:
            region = data['instance']['regions'][mode]
            modes &= tr['c'][k] == tr['s'][k]
            modes &= all(math.dist(point, region['o']) <= region['rho']+tolerance for point in tr['r'][k:k+2])
            modes &= math.dist(tr['r'][k],tr['r'][k+1]) <= phys['v_c']*tr['s'][k]+tolerance
    dense = [diag.charge(phys, replay[k], fraction*duration) if mode >= 0 else
             replay[k]-phys['zeta']*fraction*duration
             for k,(duration,mode) in enumerate(zip(tr['s'],data['modes'])) for fraction in [i/60 for i in range(61)]]
    energy = (min(tr['e']) >= phys['e_min'] and max(tr['e']) <= phys['e_max'] and
              min(dense) >= phys['e_min'] and max(dense) <= phys['e_max'])
    gap = max(abs(a-b) for a,b in zip(tr['e'],replay))
    return dict(accepted=bool(residual['viol'] <= tolerance and tasks and modes and energy and gap <= tolerance),
        original_residuals=residual, min_energy=min(replay), max_energy=max(replay),
        dense_min_energy=min(dense), dense_max_energy=max(dense),
        stored_replay_gap=gap, tasks_exact=tasks, assigned_modes_valid=bool(modes))


def _project_inside(point, region, margin):
    radius = region['rho']-margin
    if radius <= 0:
        raise ValueError('region_too_small_for_margin')
    distance = math.dist(point,region['o'])
    if distance <= radius:
        return list(point)
    return [o+radius*(p-o)/distance for p,o in zip(point,region['o'])]


def _charge_time(phys, before, target):
    if before >= target:
        return 0.
    if target <= phys['e_th']:
        return (target-before)/phys['kappa']
    sigma = (phys['e_max']-phys['e_th'])/phys['kappa']
    if before < phys['e_th']:
        return ((phys['e_th']-before)/phys['kappa']+
                sigma*math.log((phys['e_max']-phys['e_th'])/(phys['e_max']-target)))
    return sigma*math.log((phys['e_max']-before)/(phys['e_max']-target))


def repair(data, charge_fraction=.99, interior_margin=.001, energy_buffer=1e-8):
    """Return (trajectory document or None, report); never mutate the caller's data."""
    original = audit(data)
    report = dict(accepted=False, action='repair', original_audit=original,
        charge_fraction=charge_fraction, interior_margin=interior_margin, energy_buffer=energy_buffer,
        changes=[], unrestricted_infeasibility_proven=False)
    if original['accepted']:
        return copy.deepcopy(data), dict(report,accepted=True,action='keep_original',
            final_audit=original,same_full_trajectory=True)
    output = copy.deepcopy(data)
    output.pop('experiment',None)
    output.pop('diagnostic',None)
    output.pop('history',None)
    tr,phys,modes = output['solution'],output['phys'],output['modes']
    r = tr['r']
    anchors = {0,len(r)-1,*output['task_stamp']}
    target = phys['e_min']+charge_fraction*(phys['e_max']-phys['e_min'])
    budget = phys['v_d']*(target-phys['e_min']-energy_buffer)/phys['zeta']
    capacity = phys['v_d']*(phys['e_max']-phys['e_min'])/phys['zeta']
    assert 0 < charge_fraction < 1 and budget > 0
    try:
        for k,mode in enumerate(modes):
            if mode >= 0 or math.dist(r[k],r[k+1]) <= budget:
                continue
            before = math.dist(r[k],r[k+1])
            if k > 0 and modes[k-1] >= 0 and k not in anchors:
                point = _project_inside(r[k+1],output['instance']['regions'][modes[k-1]],interior_margin)
                report['changes'].append(dict(stamp=k,region=modes[k-1],before=list(r[k]),after=point))
                r[k] = point
            if (math.dist(r[k],r[k+1]) > budget and k+1 < len(modes) and
                    modes[k+1] >= 0 and k+1 not in anchors):
                point = _project_inside(r[k],output['instance']['regions'][modes[k+1]],interior_margin)
                report['changes'].append(dict(stamp=k+1,region=modes[k+1],before=list(r[k+1]),after=point))
                r[k+1] = point
            distance = math.dist(r[k],r[k+1])
            if distance > budget:
                return None,dict(report,reason='overlong_flight_remains',segment=k,distance_km=distance,
                    before_distance_km=before,target_range_km=budget,full_range_km=capacity,
                    fixed_endpoints_over_full_range=k in anchors and k+1 in anchors and distance > capacity)
        durations,energy = [],[phys['e_max']]
        for k,mode in enumerate(modes):
            speed = phys['v_c'] if mode >= 0 else phys['v_d']
            duration = max(phys['s_min'],math.dist(r[k],r[k+1])/speed)
            if mode >= 0:
                duration = max(duration,_charge_time(phys,energy[-1],target))
            if duration > phys['s_max']:
                return None,dict(report,reason='duration_upper_bound',segment=k,duration_hours=duration)
            after = diag.charge(phys,energy[-1],duration) if mode >= 0 else energy[-1]-phys['zeta']*duration
            if not phys['e_min'] <= after <= phys['e_max']:
                return None,dict(report,reason='insufficient_energy_between_charges',segment=k,energy=after)
            durations.append(duration);energy.append(after)
        tr.update(e=energy,s=durations,c=[duration if mode >= 0 else 0. for duration,mode in zip(durations,modes)])
        checked = audit(output)
        report.update(accepted=checked['accepted'],final_audit=checked,
            objective_hours=sum(durations),same_modes=modes==data['modes'],
            same_task_stamps=output['task_stamp']==data['task_stamp'],same_stamps=len(r)==len(data['solution']['r']))
        if not checked['accepted']:
            report['reason']='constructed_physical_checks'
            return None,report
        return output,report
    except (ValueError,OverflowError) as error:
        return None,dict(report,reason=str(error))
