"""Inspect stored solutions and optionally shorten charging with the route/modes fixed.

No third-party dependencies. This is a diagnostic experiment, not the paper's solver.
Run from uav/: python3 scripts/diagnose_solution.py out/*.json --out summary.json
Use --polish-dir DIR to also save feasible fixed-mode witnesses (when possible).
"""

import argparse
import copy
import csv
import json
import math
from pathlib import Path
from time import perf_counter


def charge(p, e, c):
    """Paper (26), only used with nonnegative physical charging durations."""
    if c < 0:
        raise ValueError("physical charging duration must be nonnegative")
    span = p["e_max"] - p["e_th"]
    sigma = span / p["kappa"]
    if e < p["e_th"]:
        tau = (p["e_th"] - e) / p["kappa"]
        if c <= tau:
            return e + p["kappa"] * c
        return p["e_max"] - span * math.exp(-(c - tau) / sigma)
    return p["e_max"] - (p["e_max"] - e) * math.exp(-c / sigma)


def replay(d, durations=None):
    p, tr = d["phys"], d["solution"]
    e = [p["e_max"]]
    for s, mode in zip(tr["s"] if durations is None else durations, d["modes"]):
        e.append(charge(p, e[-1], s) if mode >= 0 else e[-1] - p["zeta"] * s)
    return e


def signed_charge(p, e, c):
    """Match the solver's extension at infeasible negative-c trial points."""
    if c >= 0:
        return charge(p, e, c)
    if e <= p["e_th"]:
        return e + p["kappa"] * c
    span = p["e_max"] - p["e_th"]
    sigma = span / p["kappa"]
    back = sigma * math.log(span / (p["e_max"] - e)) if e < p["e_max"] else math.inf
    if -c <= back:
        return p["e_max"] - (p["e_max"] - e) * math.exp(min(60., -c / sigma))
    return p["e_th"] + p["kappa"] * (c + back)


def residuals(d):
    """Original constraints in their original units; reject nonfinite values."""
    p, tr, inst = d["phys"], d["solution"], d["instance"]
    if any(not math.isfinite(v) for key in ("e", "s", "c") for v in tr[key]):
        raise ValueError("nonfinite trajectory")
    if any(not math.isfinite(v) for r in tr["r"] for v in r):
        raise ValueError("nonfinite position")
    task = max((min(max(abs(r[j] - a[j]) for j in (0, 1)) for r in tr["r"])
                for a in inst["tasks"]), default=0.)
    mode = dyn = speed = bounds = 0.
    for k, (s, c) in enumerate(zip(tr["s"], tr["c"])):
        ra, rb = tr["r"][k:k + 2]
        v = abs(c)
        for reg in inst["regions"]:
            v = min(v, max(abs(c - s), math.dist(ra, reg["o"]) - reg["rho"],
                           math.dist(rb, reg["o"]) - reg["rho"],
                           math.dist(ra, rb) - p["v_c"] * s))
        mode = max(mode, v)
        fc = signed_charge(p, tr["e"][k], c)
        dyn = max(dyn, abs(tr["e"][k + 1] - fc + p["zeta"] * (s - c)))
        speed = max(speed, math.dist(ra, rb) - p["v_d"] * s)
        bounds = max(bounds, p["s_min"] - s, s - p["s_max"], -c,
                     p["e_min"] - tr["e"][k + 1], tr["e"][k + 1] - p["e_max"])
    endpoint = max(math.dist(tr["r"][0], inst["r0"]),
                   math.dist(tr["r"][-1], inst["rf"]), abs(tr["e"][0] - p["e_max"]))
    parts = dict(viol_task=task, viol_mode=mode, viol_dyn=dyn,
                 viol_speed=speed, viol_bounds=bounds, viol_endpoint=endpoint)
    return dict(viol=max(parts.values()), **parts)


def inspect(d, source, segments_path):
    p, tr = d["phys"], d["solution"]
    physical = replay(d)
    flight_gain = 0.
    rows = []
    for k, (s, c, mode) in enumerate(zip(tr["s"], tr["c"], d["modes"])):
        fc = signed_charge(p, tr["e"][k], c)
        gain = fc - tr["e"][k] + p["zeta"] * c if mode < 0 else 0.
        flight_gain += gain
        rows.append(dict(segment=k, mode=mode, distance=math.dist(*tr["r"][k:k + 2]),
                         seconds=s * 3600, charge_seconds=c * 3600,
                         stored_e=tr["e"][k + 1], replay_e=physical[k + 1],
                         flight_energy_gain=gain))
    if segments_path:
        with segments_path.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    return dict(source=str(source), objective=sum(tr["s"]),
                original_residuals=residuals(d), kkt_converged=d["metrics"]["converged"],
                final_stage=d["stages"][-1] if d["stages"] else None,
                task_stamps=d["task_stamp"], charging_segments=sum(m >= 0 for m in d["modes"]),
                charging_hours=sum(s for s, m in zip(tr["s"], d["modes"]) if m >= 0),
                replay_min_e=min(physical), replay_final_e=physical[-1],
                flight_energy_gain=flight_gain,
                max_stored_replay_gap=max(abs(a - b) for a, b in zip(tr["e"], physical)))


def polish_fixed_modes(original):
    """Construct a witness to time waste, preserving task assignment and segment modes.

    Snap task visits and region endpoints to remove tiny numerical residuals. Recompute
    minimum durations from speed limits. Reduce each charging duration by bisection,
    accepting only changes with nonnegative battery over the *whole* trajectory.
    This does not search task orders, charge modes, or improve the route topology.
    """
    started = perf_counter()
    d = copy.deepcopy(original)
    p, tr, inst = d["phys"], d["solution"], d["instance"]
    for a, k in zip(inst["tasks"], d["task_stamp"]):
        tr["r"][k] = list(a)
    for k, mode in enumerate(d["modes"]):
        if mode < 0:
            continue
        reg = inst["regions"][mode]
        for at in (k, k + 1):
            r = tr["r"][at]
            dist = math.dist(r, reg["o"])
            if dist > reg["rho"] - 1e-10:
                scale = (reg["rho"] - 1e-10) / dist
                tr["r"][at] = [o + scale * (v - o) for v, o in zip(r, reg["o"])]
    for k, mode in enumerate(d["modes"]):
        if mode >= 0:
            reg = inst["regions"][mode]
            if any(math.dist(r, reg["o"]) > reg["rho"] for r in tr["r"][k:k + 2]):
                return None, "Conflicting charging regions prevent preserving the selected modes."
    lower = [max(p["s_min"], math.dist(*tr["r"][k:k + 2]) /
                 (p["v_c"] if mode >= 0 else p["v_d"]) + 1e-12)
             for k, mode in enumerate(d["modes"])]
    s = [max(a, b) if mode >= 0 else a
         for a, b, mode in zip(lower, tr["s"], d["modes"])]
    if any(t > p["s_max"] for t in s) or min(replay(d, s)) < p["e_min"]:
        return None, "Rounded modes are battery-infeasible; reducing charging cannot repair them."
    for k, mode in enumerate(d["modes"]):
        if mode < 0:
            continue
        lo, hi = lower[k], s[k]
        for _ in range(60):
            mid = (lo + hi) / 2
            trial = list(s)
            trial[k] = mid
            if min(replay(d, trial)) >= p["e_min"] + 1e-10:
                hi = mid
            else:
                lo = mid
        s[k] = hi
    tr["s"] = s
    tr["c"] = [t if mode >= 0 else 0. for t, mode in zip(s, d["modes"])]
    tr["e"] = replay(d)
    checked = residuals(d)
    if checked["viol"] > 1e-8:
        return None, f"Geometry/task conflicts prevent a feasible witness: {checked}"
    h = dict(t=[], e=[], d=[], stamps=[0.])
    t0 = 0.
    for k, (duration, mode) in enumerate(zip(tr["s"], d["modes"])):
        for i in range(61):
            a = i / 60
            r = [u + a * (v - u) for u, v in zip(*tr["r"][k:k + 2])]
            e = charge(p, tr["e"][k], a * duration) if mode >= 0 else tr["e"][k] - p["zeta"] * a * duration
            h["t"].append(t0 + a * duration)
            h["e"].append(e)
            h["d"].append(max(0., min(math.dist(r, reg["o"]) - reg["rho"] for reg in inst["regions"])))
        t0 += duration
        h["stamps"].append(t0)
    d["history"] = h
    d["stages"] = []
    d["metrics"] = dict(objective=sum(tr["s"]), init_objective=sum(d["init"]["s"]),
                        converged=False, seconds=perf_counter() - started, stamps=len(tr["r"]), **checked)
    d["diagnostic"] = dict(method="fixed route/modes, exact battery replay, coordinate charge reduction",
                           source_objective=original["metrics"]["objective"],
                           source_solve_seconds=original["metrics"]["seconds"],
                           segment_time_lower_bound=sum(lower),
                           max_segment_time_slack=max(s - bound for s, bound in zip(tr["s"], lower)),
                           max_position_change=max(math.dist(a, b) for a, b in
                                                   zip(tr["r"], original["solution"]["r"])))
    return d, "feasible witness; no KKT or optimality claim"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("sources", type=Path, nargs="+")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--segments-dir", type=Path)
    ap.add_argument("--polish-dir", type=Path)
    args = ap.parse_args()
    for directory in (args.segments_dir, args.polish_dir):
        if directory:
            directory.mkdir(parents=True, exist_ok=True)
    summaries = []
    for src in args.sources:
        d = json.loads(src.read_text())
        summary = inspect(d, src, args.segments_dir / (src.stem + ".csv") if args.segments_dir else None)
        if args.polish_dir:
            candidate, status = polish_fixed_modes(d)
            summary["fixed_modes_status"] = status
            if candidate:
                dest = args.polish_dir / (src.stem + "-fixed-modes.json")
                dest.write_text(json.dumps(candidate, indent=2, allow_nan=False) + "\n")
                summary["fixed_modes"] = dict(path=str(dest), **candidate["metrics"], **candidate["diagnostic"])
        summaries.append(summary)
    result = json.dumps(summaries, indent=2, allow_nan=False) + "\n"
    if args.out:
        args.out.write_text(result)
    else:
        print(result, end="")


if __name__ == "__main__":
    main()
