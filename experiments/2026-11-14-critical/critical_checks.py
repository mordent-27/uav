"""Small counterexamples/identities for the critical reading; no solver tuning.

Run from uav/: python3 experiments/2026-11-14-critical/critical_checks.py
The generated mode example satisfies the *smoothed* model at eps=.2, p=2,
but has c>s. Rust Model::eval independently checks its constraint residuals.
"""

import copy
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
DEST = Path(__file__).resolve().parent


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


diag = module("diag", ROOT / "scripts/diagnose_solution.py")
verify = module("verify", ROOT / "scripts/verify_solutions.py")


def smooth_min(z, p):
    m = min(z)
    return m * sum((m / v) ** p for v in z) ** (-1 / p)


def mode_value(c, s, scale=1.):
    # Stationary UAV at (0,0), circle center (3,0), radius 1.
    # Two violated spatial components = 2 km each; station-speed component < 0.
    return smooth_min([math.hypot(c, .2), math.sqrt((c - s)**2 + 8 * scale**2 + .2**2)], 2.)


def mode_root(s, scale=1.):
    lo, hi = 0., 1.
    for _ in range(100):
        mid = (lo + hi) / 2
        if mode_value(mid, s, scale) < .2:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def make_duration_example():
    p = dict(e_max=1., e_min=0., e_th=.7, v_d=36., v_c=10.8,
             kappa=4.625, zeta=2.5, s_min=30 / 3600, s_max=1.)
    s = [.1, p["s_min"]]
    c = [mode_root(t) for t in s]
    e = [1.]
    for duration, charging in zip(s, c):
        e.append(diag.charge(p, e[-1], charging) - p["zeta"] * (duration - charging))
    tr = dict(r=[[0., 0.]] * 3, s=s, c=c, e=e)
    d = dict(instance=dict(r0=[0., 0.], rf=[0., 0.],
                           regions=[dict(o=[3., 0.], rho=1.)], tasks=[[.2 * math.sqrt(2), 0.]]),
             phys=p, solution=tr, init=copy.deepcopy(tr), modes=[-1, -1],
             task_stamp=[0], stages=[], smoothing=dict(eps=.2, p=2., delta=.001))
    d["metrics"] = dict(objective=sum(s), init_objective=sum(s), seconds=0.,
                        converged=False, stamps=3, **diag.residuals(d))
    assert c[1] > s[1] and all(0 <= v <= 1 for v in e)
    (DEST / "duration-example.json").write_text(json.dumps(d, indent=2) + "\n")
    return d


def rust_check(d):
    lit = verify.literal
    source = ["#![allow(dead_code)]"]
    for name in ("params", "rng", "battery", "model", "instance", "metrics"):
        source.append(f'#[path = {json.dumps(str(ROOT / "src" / (name + ".rs")))}] mod {name};')
    source.append('fn main() { let ph = params::Phys::default();')
    source.append('let inst = params::Instance {r0: [0.,0.], rf: [0.,0.], '
                  'regions: vec![params::Region {o: [3.,0.], rho: 1.}], tasks: vec!'
                  + lit(d['instance']['tasks']) + '};')
    source.append('let tr = instance::Traj {' + ','.join(
        key + ': vec!' + lit(d['solution'][key]) for key in ('r', 'e', 's', 'c')) + '};')
    source.append('let sm = params::Smooth {eps: 0.2, p: 2., delta: 0.001}; '
                  'let model = model::Model::new(&inst, &ph, 3, sm); '
                  'let x = tr.to_x(&model.lay); '
                  'let we = vec![0.; model.lay.n_eq()]; let wi = vec![0.; model.lay.n_ineq()]; '
                  'let mut rec = model::Recorder::new(&we, &wi); '
                  'let mut grad = vec![0.; x.len()]; model.eval(&x, &mut rec, &mut grad); '
                  'let eq = rec.h.iter().map(|v| v.abs()).fold(0., f64::max); '
                  'let ineq = rec.g.iter().copied().fold(0., f64::max); '
                  'println!("smooth equality residual {:.3e}, inequality violation {:.3e}", eq, ineq); '
                  'println!("second segment seconds {:.9}, charging seconds {:.9}", tr.s[1]*3600., tr.c[1]*3600.); '
                  'assert!(eq < 1e-12 && ineq < 1e-12 && tr.c[1] > tr.s[1]); }')
    with tempfile.TemporaryDirectory(prefix="uav-critical-") as td:
        rs, binary = Path(td) / "check.rs", Path(td) / "check"
        rs.write_text("\n".join(source))
        subprocess.run(["rustc", "--edition=2021", str(rs), "-o", str(binary)], check=True)
        result = subprocess.run([str(binary)], check=True, text=True, capture_output=True)
    return result.stdout


def main():
    d = make_duration_example()
    rust_log = rust_check(d)
    c_km, c_m = mode_root(1 / 120), mode_root(1 / 120, 1000.)
    # Semigroup failure despite identity at zero, differentiability, monotonicity,
    # and preservation of admissible battery levels.
    fd = lambda e, t: e * math.exp(-t * t)
    flow = {str(n): fd(1., 1 / n) ** n for n in (1, 2, 10, 100)}
    assert flow["100"] > flow["10"] > flow["2"] > flow["1"]
    eps, p = .2, 2.
    duplicate = dict(single=smooth_min([eps], p), double=smooth_min([eps, eps], p),
                     both_z_for_equality=eps * 2 ** (1 / p))
    assert duplicate["double"] < duplicate["single"]
    # A smooth nonnegative hinge with exactly the original zero set.
    def exact_zero_hinge(y, delta):
        return 0. if y <= 0 else (y*y / (2*delta) if y <= delta else y - delta/2)
    assert exact_zero_hinge(0., .001) == 0.
    assert exact_zero_hinge(.0002, .001) > 0.
    # Both formulas represent the same soft minimum; the shifted one avoids
    # exponentiating huge negative numbers directly.
    z, tau = [1000., 1001.], .001
    naive_sum = sum(math.exp(-v / tau) for v in z)
    stable = min(z) - tau * math.log(sum(math.exp(-(v - min(z)) / tau) for v in z))
    assert naive_sum == 0. and stable == 1000.
    # Exact task visits imply phi < eps in real arithmetic whenever N>1.
    exact_visit_phi = smooth_min([.2, 1.], 2.)
    assert exact_visit_phi < .2
    # Original-model necessary time/energy bound when no charging is accessible.
    mesh = {str(n): dict(minimum_seconds=(n-1)*30,
                        best_final_e=1. - 2.5*(n-1)/120) for n in (49, 50)}
    assert mesh["49"]["best_final_e"] == 0. and mesh["50"]["best_final_e"] < 0.
    result = dict(
        duration=dict(segment_seconds=d["solution"]["s"][1]*3600,
                      charging_seconds=d["solution"]["c"][1]*3600,
                      negative_discharge_seconds=(d["solution"]["s"][1]-d["solution"]["c"][1])*3600,
                      battery=d["solution"]["e"], original_residual=d["metrics"]["viol"]),
        unit_change=dict(km_charge_seconds=c_km*3600, m_charge_seconds=c_m*3600,
                         description="Spatial g and delta converted together; time remains in hours. No component normalization."),
        battery_partition=dict(fd="e*exp(-t^2)", same_total_duration=1., final_energy=flow),
        duplication=duplicate, mesh=mesh,
        exact_visit=dict(phi=exact_visit_phi, target=.2),
        hinge=dict(paper_at_zero=.001/4, alternative_at_zero=exact_zero_hinge(0., .001)),
        logsumexp=dict(naive_exponential_sum=naive_sum, shifted_softmin=stable),
    )
    (DEST / "checks.json").write_text(json.dumps(result, indent=2) + "\n")
    (DEST / "rust-smooth-validation.log").write_text(rust_log)
    print(rust_log, end="")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
