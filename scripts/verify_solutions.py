"""Cross-check solution JSON using the existing Rust evaluator (requires rustc).

    python3 scripts/verify_solutions.py out/fig1.json experiments/.../*.json

Temporary Rust source and executable are created outside the repository. Diagnostic
witnesses must also satisfy energy bounds at dense samples and exact endpoint/mode bounds.
"""

import argparse
import json
from pathlib import Path
import subprocess
import tempfile


def literal(value):
    if isinstance(value, list):
        return "[" + ",".join(literal(v) for v in value) + "]"
    return repr(float(value))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("sources", type=Path, nargs="+")
    args = ap.parse_args()
    root = Path(__file__).resolve().parents[1]
    source = ["#![allow(dead_code)]"]
    for name in ("params", "rng", "battery", "model", "instance", "metrics"):
        source.append(f'#[path = {json.dumps(str(root / "src" / (name + ".rs")))}] mod {name};')
    source.append("fn main() { let ph = params::Phys::default(); "
                  "let sm = *params::Homotopy::default().schedule().last().unwrap();")
    for path in args.sources:
        d = json.loads(path.read_text())
        inst, tr = d["instance"], d["solution"]
        # Phys::default is deliberately used below; refuse unrelated physical models.
        expected = dict(e_max=1., e_min=0., e_th=.7, v_d=36., v_c=10.8,
                        kappa=4.625, zeta=2.5, s_min=30 / 3600, s_max=1.)
        assert all(abs(d["phys"][k] - v) < 1e-14 for k, v in expected.items())
        regions = ",".join("params::Region {o: " + literal(r["o"]) +
                           ", rho: " + literal(r["rho"]) + "}" for r in inst["regions"])
        source.append("let inst = params::Instance { r0: " + literal(inst["r0"]) +
                      ", rf: " + literal(inst["rf"]) + ", tasks: vec!" + literal(inst["tasks"]) +
                      ", regions: vec![" + regions + "] };")
        source.append("let tr = instance::Traj { " + ",".join(
            k + ": vec!" + literal(tr[k]) for k in ("r", "e", "s", "c")) + " };")
        source.append("let m = metrics::evaluate(&inst, &ph, &tr, sm);")
        source.append("assert!((m.viol - " + literal(d["metrics"]["viol"]) + ").abs() < 1e-8);")
        source.append("assert!((m.objective - " + literal(d["metrics"]["objective"]) + ").abs() < 1e-8);")
        source.append("println!(\"{} objective {:.12} original_violation {:.3e}\", " +
                      json.dumps(str(path)) + ", m.objective, m.viol);")
        if "diagnostic" in d:
            source.extend([
                "assert!(m.viol < 1e-10);",
                "assert!(tr.r[0] == inst.r0 && *tr.r.last().unwrap() == inst.rf);",
                "assert!(tr.e[0] == ph.e_max && tr.c.iter().all(|c| *c >= 0.0));",
                "assert!(tr.e.iter().all(|e| *e >= 0.0 && *e <= ph.e_max));",
                "assert!(tr.c.iter().zip(&tr.s).all(|(c,s)| *c == 0.0 || c == s));",
                "assert!(metrics::history(&inst, &ph, &tr, &m.modes, 60).e.iter()"
                ".all(|e| *e >= -1e-10 && *e <= ph.e_max));",
            ])
    source.append("}")
    with tempfile.TemporaryDirectory(prefix="uav-verify-") as directory:
        rs, binary = Path(directory) / "verify.rs", Path(directory) / "verify"
        rs.write_text("\n".join(source))
        subprocess.run(["rustc", "--edition=2021", str(rs), "-o", str(binary)], check=True)
        subprocess.run([str(binary)], check=True)


if __name__ == "__main__":
    main()
