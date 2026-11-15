"""A necessary-distance certificate for the failed direct branch; no numerical solve."""
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent


def read(path):
    return json.loads(path.read_text())


def main():
    case = 'tau7-seed3'
    folder = HERE/'cases/direct'/case
    result, source = read(folder/'result.json'), read(folder/'source.json')
    assert not result['final_common_pass']
    instance = read(HERE/'cases/G'/case/'preflight.json')['instance']
    phys = read(folder/'solution.json')['phys']
    capacity = phys['v_d']*(phys['e_max']-phys['e_min'])/phys['zeta']
    modes = [m['winner'] for m in result['selection']['modes']]
    stamps = [t['stamp'] for t in result['selection']['tasks']]
    initial_modes = [m['winner'] for m in source['selection']['modes']]
    charging = [k for k, mode in enumerate(modes) if mode >= 0]
    bounds = []
    for before, after in zip(charging, charging[1:]):
        assert all(mode == -1 for mode in modes[before+1:after])
        for task_index, stamp in enumerate(stamps):
            if not before+1 <= stamp <= after:
                continue
            task = instance['tasks'][task_index]
            terms = [max(0., math.dist(task, instance['regions'][region]['o'])-
                         instance['regions'][region]['rho']) for region in [modes[before], modes[after]]]
            # Rust exports coordinates to 9 decimal places. This buffer exceeds the
            # propagated coordinate/radius rounding bound and leaves the conclusion unchanged.
            buffer = 1e-7
            bound = sum(terms)-buffer
            bounds.append(dict(previous_charge_segment=before, next_charge_segment=after,
                previous_region=modes[before], next_region=modes[after], task_index=task_index,
                task_stamp=stamp, task_position=task, distances_to_regions_km=terms,
                rounding_buffer_km=buffer, conservative_distance_lower_bound_km=bound,
                capacity_km=capacity, exceeds_capacity=bound > capacity))
    violations = [b for b in bounds if b['exceeds_capacity']]
    assert violations, 'no distance certificate found; do not label branch infeasible'
    changed = [dict(segment=k, before=a, after=b) for k,(a,b) in enumerate(zip(initial_modes,modes)) if a != b]
    proof = dict(case=case, direct_stop=result['stop'], direct_common_kkt=result['common_kkt'],
        initial_charges=sum(mode >= 0 for mode in initial_modes), final_charges=len(charging),
        changed_modes=changed, necessary_distance_bounds=bounds, violated_bounds=violations,
        fixed_assignment_infeasible=True, unrestricted_NLP_infeasibility_proven=False,
        assumptions=['modes, regions and task stamps fixed to the failed direct point',
            'battery at previous charge end is at most e_max',
            'intervening segments are pure flight with c=0',
            's >= distance/v_d and energy drains at rate zeta during flight',
            'travel via task must be at least distance(task, previous disk)+distance(task, next disk)'],
        explanation='zeta*distance_lower_bound/v_d > e_max-e_min, even starting with a full battery')
    (HERE/'branch-distance-bound.json').write_text(json.dumps(proof, indent=2)+'\n')
    for bound in violations:
        print('Task',bound['task_index'],'regions',bound['previous_region'],bound['next_region'],
              'lower bound',bound['conservative_distance_lower_bound_km'],'capacity',capacity)


if __name__ == '__main__':
    main()
