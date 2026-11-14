"""Construct one carrier trajectory per circular region for a fixed exact mode plan.

This checks carrier motion only. It does not infer modes, repair the UAV plan,
check its battery, or solve the joint trajectory optimization problem.
Initial carrier positions are free unless supplied explicitly.

    python3 scripts/carrier_certificate.py solution.json --output certificate.json
"""

import argparse
import json
import math
from pathlib import Path


DIST_TOL = 1e-9  # km; numerical allowance, not the earlier 1 m audit tolerance
MODE_TOL = 1e-12  # hours; only exact-mode plans, apart from roundoff


def certify(d, initial_positions=None, distance_tol=DIST_TOL):
    """Eliminate carrier positions by checking consecutive forced contact anchors.

    A successful result contains positions at every UAV stamp. Linear interpolation
    gives a continuous trajectory in each convex disk. Speed is bounded on every
    segment and the carrier follows the UAV during its assigned charging segments.
    """
    tr, regions = d['solution'], d['instance']['regions']
    r, s, c, modes = tr['r'], tr['s'], tr['c'], d['modes']
    n, vc = len(r), d['phys']['v_c']
    initial_positions = {} if initial_positions is None else initial_positions
    if n < 2 or len(s) != n-1 or len(c) != n-1 or len(modes) != n-1:
        raise ValueError('inconsistent trajectory dimensions')
    if not math.isfinite(distance_tol) or distance_tol < 0:
        raise ValueError('invalid distance tolerance')
    if not math.isfinite(vc) or vc <= 0:
        raise ValueError('invalid carrier speed')
    points = list(r) + [reg['o'] for reg in regions] + list(initial_positions.values())
    if any(len(p) != 2 or any(not math.isfinite(x) for x in p) for p in points):
        raise ValueError('nonfinite or nonplanar position')
    if any(not math.isfinite(x) for x in s+c) or any(x <= 0 for x in s):
        raise ValueError('nonfinite or nonpositive duration')
    if any(not math.isfinite(reg['rho']) or reg['rho'] < 0 for reg in regions):
        raise ValueError('invalid disk radius')
    if any(not isinstance(j, int) or j < 0 or j >= len(regions) for j in initial_positions):
        raise ValueError('unknown initial-position region')
    for k, mode in enumerate(modes):
        if not isinstance(mode, int) or not -1 <= mode < len(regions):
            raise ValueError('unknown mode')
        expected = 0. if mode == -1 else s[k]
        if abs(c[k]-expected) > MODE_TOL:
            raise ValueError('certificate requires fixed exact charging/discharging modes')
    t = [0.]
    for duration in s:
        t.append(t[-1]+duration)
    if any(not math.isfinite(x) for x in t):
        raise ValueError('nonfinite cumulative time')

    results = []
    for j, reg in enumerate(regions):
        anchors = {}
        failures = []
        for k, mode in enumerate(modes):
            if mode == j:
                anchors[k], anchors[k+1] = list(r[k]), list(r[k+1])
        if j in initial_positions:
            initial = list(initial_positions[j])
            if 0 in anchors and math.dist(initial, anchors[0]) > distance_tol:
                failures.append(dict(kind='initial_contact', stamp=0,
                                     excess_km=math.dist(initial, anchors[0])))
            else:
                anchors[0] = initial
        if not anchors:
            anchors[0] = list(reg['o'])
        for k, point in sorted(anchors.items()):
            outside = max(0., math.dist(point, reg['o'])-reg['rho'])
            if outside > distance_tol:
                failures.append(dict(kind='outside_region', stamp=k, excess_km=outside))
        indices = sorted(anchors)
        pairs = []
        for a, b in zip(indices, indices[1:]):
            gap = t[b]-t[a]
            distance = math.dist(anchors[a], anchors[b])
            excess = max(0., distance-vc*gap)
            pair = dict(start_stamp=a, end_stamp=b, available_seconds=gap*3600,
                        required_seconds=distance/vc*3600, excess_km=excess)
            pairs.append(pair)
            if excess > distance_tol:
                failures.append(dict(kind='unreachable', **pair))
        positions = None
        if not failures:
            # Before/after the first/last forced contact, staying put is sufficient.
            positions = [list(anchors[indices[0]]) for _ in range(n)]
            for a, b in zip(indices, indices[1:]):
                for k in range(a, b+1):
                    fraction = (t[k]-t[a])/(t[b]-t[a])
                    positions[k] = [(1-fraction)*x+fraction*y
                                    for x, y in zip(anchors[a], anchors[b])]
            for k in range(indices[-1], n):
                positions[k] = list(anchors[indices[-1]])
        results.append(dict(region=j, initial_position_fixed=j in initial_positions,
                            anchors=[dict(stamp=k, position=anchors[k]) for k in indices],
                            anchor_pairs=pairs, failures=failures, positions=positions,
                            feasible=not failures))
    return dict(feasible=all(item['feasible'] for item in results),
                scope='carrier motion for supplied fixed modes only',
                assumptions=['one independent carrier per disk', 'convex obstacle-free disks',
                             'piecewise linear UAV and carrier motion',
                             'speed limits only; no acceleration or carrier energy limit'],
                distance_tolerance_km=distance_tol, mode_tolerance_hours=MODE_TOL,
                times_hours=t, carriers=results)


def check_constructed(d, certificate):
    """Independently check each constructed segment, rather than anchor inequalities."""
    if not certificate['feasible']:
        raise ValueError('no feasible certificate to check')
    tr, vc = d['solution'], d['phys']['v_c']
    maxima = dict(speed_excess_km=0., region_excess_km=0., contact_error_km=0.,
                  initial_error_km=0.)
    for item, reg in zip(certificate['carriers'], d['instance']['regions']):
        q = item['positions']
        if len(q) != len(tr['r']) or any(not math.isfinite(x) for p in q for x in p):
            raise ValueError('invalid constructed positions')
        if item['initial_position_fixed']:
            maxima['initial_error_km'] = max(maxima['initial_error_km'],
                                             math.dist(q[0], item['anchors'][0]['position']))
        for point in q:
            maxima['region_excess_km'] = max(maxima['region_excess_km'],
                                            math.dist(point, reg['o'])-reg['rho'])
        for k, duration in enumerate(tr['s']):
            maxima['speed_excess_km'] = max(maxima['speed_excess_km'],
                                           math.dist(q[k], q[k+1])-vc*duration)
            if d['modes'][k] == item['region']:
                maxima['contact_error_km'] = max(maxima['contact_error_km'],
                    math.dist(q[k], tr['r'][k]), math.dist(q[k+1], tr['r'][k+1]))
    if max(maxima.values()) > certificate['distance_tolerance_km']:
        raise AssertionError(maxima)
    return maxima


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--initial', type=Path,
                        help='JSON mapping region indices to known initial positions [x,y]')
    args = parser.parse_args()
    initial = None
    if args.initial:
        initial = {int(j): point for j, point in json.loads(args.initial.read_text()).items()}
    d = json.loads(args.source.read_text())
    result = certify(d, initial)
    if result['feasible']:
        result['independent_check'] = check_constructed(d, result)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    print(f"carrier feasible: {result['feasible']} (fixed modes; UAV battery checked separately)")


if __name__ == '__main__':
    main()
