"""Audit original constraints, exact-mode battery replay, and one station per region.

Thresholds are fixed in human/validation_plan.md before running the cohort.
This does not optimize station trajectories or prove all mode assignments impossible.
"""

import importlib.util
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("diagnose", ROOT / "scripts/diagnose_solution.py")
diag = importlib.util.module_from_spec(spec)
spec.loader.exec_module(diag)

TOL = dict(distance_km=1e-3, time_h=1/3600, energy=1e-6, endpoint_km=1e-9)


def inspect(d):
    p, tr, inst = d["phys"], d["solution"], d["instance"]
    finite = all(math.isfinite(v) for k in ("s", "c", "e") for v in tr[k])
    finite &= all(math.isfinite(v) for r in tr["r"] for v in r)
    if not finite:
        return dict(finite=False, original_pass=False, exact_mode_battery_pass=False,
                    one_station_pass=False, physically_usable=False)
    dist_tol, time_tol = TOL["distance_km"], TOL["time_h"]
    modes, mode_scores = [], []
    for k, (s, c) in enumerate(zip(tr["s"], tr["c"])):
        ra, rb = tr["r"][k:k+2]
        candidates = [(-1, abs(c)/time_tol)]
        for j, reg in enumerate(inst["regions"]):
            outside = max(0., math.dist(ra, reg["o"])-reg["rho"],
                          math.dist(rb, reg["o"])-reg["rho"], math.dist(ra, rb)-p["v_c"]*s)
            candidates.append((j, max(abs(c-s)/time_tol, outside/dist_tol)))
        mode, score = min(candidates, key=lambda item: item[1])
        modes.append(mode)
        mode_scores.append(score)
    residual = diag.residuals(d)
    e_bound = max([0.] + [max(p["e_min"]-e, e-p["e_max"]) for e in tr["e"]])
    s_bound = max([0.] + [max(p["s_min"]-s, s-p["s_max"]) for s in tr["s"]])
    c_lower = max([0.] + [-c for c in tr["c"]])
    c_upper = max([0.] + [c-s for c,s in zip(tr["c"],tr["s"])])
    endpoint = max(math.dist(tr["r"][0], inst["r0"]), math.dist(tr["r"][-1], inst["rf"]))
    passed = dict(task=residual["viol_task"] <= dist_tol,
                  mode=max(mode_scores, default=0.) <= 1.,
                  dynamics=residual["viol_dyn"] <= TOL["energy"],
                  uav_speed=residual["viol_speed"] <= dist_tol,
                  energy=e_bound <= TOL["energy"], segment_time=s_bound <= time_tol,
                  charging_nonnegative=c_lower <= time_tol,
                  endpoints=endpoint <= TOL["endpoint_km"] and abs(tr["e"][0]-p["e_max"])<=1e-9)
    replay_d = dict(d, modes=modes)
    replay_e = diag.replay(replay_d)
    replay_violation = max([0.] + [max(p["e_min"]-e,e-p["e_max"]) for e in replay_e])
    pairs = []
    last = {}
    for k, mode in enumerate(modes):
        if mode < 0:
            continue
        if mode in last:
            a = last[mode]
            gap = sum(tr["s"][a+1:k])
            distance = math.dist(tr["r"][a+1], tr["r"][k])
            pairs.append(dict(region=mode, previous_segment=a, next_segment=k,
                              gap_seconds=gap*3600, distance_km=distance,
                              shortfall_km=max(0.,distance-p["v_c"]*gap),
                              missing_seconds=max(0.,distance/p["v_c"]-gap)*3600))
        last[mode] = k
    station_bad = [pair for pair in pairs if pair["shortfall_km"] > dist_tol]
    original_pass = all(passed.values())
    exact_pass = replay_violation <= TOL["energy"]
    station_pass = not station_bad
    return dict(finite=True, objective=sum(tr["s"]), original_pass=original_pass,
                original_pass_parts=passed, original_residuals=residual,
                max_mode_score=max(mode_scores, default=0.), modes=modes,
                stored_mode_disagreements=sum(a!=b for a,b in zip(modes,d["modes"])),
                charging_over_segment_seconds=c_upper*3600,
                charging_domain_pass=c_upper <= time_tol and c_lower <= time_tol,
                exact_mode_battery_pass=exact_pass, replay_min_energy=min(replay_e),
                replay_max_energy=max(replay_e), replay_violation=replay_violation,
                station_pairs=pairs, station_failed_pairs=station_bad,
                max_station_shortfall_km=max([0.] + [v["shortfall_km"] for v in pairs]),
                one_station_pass=station_pass,
                physically_usable=original_pass and exact_pass and station_pass
                                  and c_upper <= time_tol)
