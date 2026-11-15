"""Audit the saved initial geometry and battery without changing or solving it."""
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    cases = []
    for tau in [1, 3, 5, 7]:
        case = f'tau{tau}-seed3'
        folder = HERE/'cases/G'/case
        document = json.loads((folder/'solution.json').read_text())
        source = json.loads((folder/'source.json').read_text())
        tr, phys = document['init'], document['phys']
        capacity = phys['v_d']*(phys['e_max']-phys['e_min'])/phys['zeta']
        legs = []
        for k, mode in enumerate(source['selection']['modes']):
            if mode['winner'] != -1:
                continue
            distance = math.dist(tr['r'][k], tr['r'][k+1])
            if distance > capacity:
                legs.append(dict(segment=k, distance_km=distance, capacity_km=capacity,
                    required_flight_energy=phys['zeta']*distance/phys['v_d'],
                    initial_start_energy=tr['e'][k], initial_end_energy=tr['e'][k+1]))
        cases.append(dict(case=case, initial_hours=sum(tr['s']), min_initial_energy=min(tr['e']),
            original_audit=source['selection']['audit'], flight_legs_exceeding_full_capacity=legs,
            fixed_initial_geometry_infeasible=bool(legs),
            caveat='changing battery and duration alone cannot fix an over-range flight leg; positions or modes must change'))
    (HERE/'initialization-audit.json').write_text(json.dumps(cases, indent=2)+'\n')
    for case in cases:
        print(case['case'],case['min_initial_energy'],case['flight_legs_exceeding_full_capacity'])


if __name__ == '__main__':
    main()
