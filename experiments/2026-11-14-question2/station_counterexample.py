"""A feasible original UAV trajectory that one station cannot serve on revisits.

Run from uav/: python3 experiments/2026-11-14-question2/station_counterexample.py
The interpretation assumes the same single station serves both charging intervals.
"""

import copy
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("diagnose_solution", ROOT / "scripts/diagnose_solution.py")
diag = importlib.util.module_from_spec(spec)
spec.loader.exec_module(diag)

p = dict(e_max=1., e_th=.7, e_min=0., v_d=36., v_c=10.8,
         kappa=4.625, zeta=2.5, s_min=30 / 3600, s_max=1.)
gap = 2. / p["v_d"]
tr = dict(r=[[-1., 0.], [-1., 0.], [1., 0.], [1., 0.]],
          s=[p["s_min"], gap, p["s_min"]], c=[p["s_min"], 0., p["s_min"]])
d = dict(instance=dict(r0=tr["r"][0], rf=tr["r"][-1],
                       regions=[dict(o=[0., 0.], rho=2.)], tasks=[[-1., 0.], [1., 0.]]),
         phys=p, solution=tr, modes=[0, -1, 0], task_stamp=[0, 2], stages=[])
tr["e"] = diag.replay(d)
d["init"] = copy.deepcopy(tr)
d["metrics"] = dict(objective=sum(tr["s"]), init_objective=sum(tr["s"]),
                    converged=False, seconds=0., stamps=4, **diag.residuals(d))
d["station_revisit"] = dict(
    interpretation="The same single station serves both charging intervals in this region.",
    distance_km=2., available_hours=gap, required_hours=2. / p["v_c"],
    shortfall_km=2. - p["v_c"] * gap,
)
assert d["metrics"]["viol"] < 1e-12
assert d["station_revisit"]["shortfall_km"] > 1.
dest = Path(__file__).resolve().with_name("station-counterexample.json")
dest.write_text(json.dumps(d, indent=2, allow_nan=False) + "\n")
print("original UAV constraint violation:", d["metrics"]["viol"])
print("available reposition time [s]:", gap * 3600)
print("required reposition time [s]:", 2. / p["v_c"] * 3600)
print("unreachable distance [km]:", d["station_revisit"]["shortfall_km"])
