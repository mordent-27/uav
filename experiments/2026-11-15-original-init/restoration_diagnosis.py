"""Which acceptance check of the planned restoration failed. Reads restored/solver.json; solves nothing."""
import copy
import importlib.util
import json
import math

import numpy as np
import helpers as h

spec = importlib.util.spec_from_file_location('fixed_branch', h.HERE.parent/'2026-11-14-restoration/fixed_branch.py')
fb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fb)
data = fb.restore_source(json.loads((h.HERE/'solution.json').read_text()))
saved = json.loads((h.HERE/'restored/solver.json').read_text())
model = fb.FixedBranch(data, moving=True)
point = np.array(saved['point'])
positions, durations = model.decode(point)
before = durations.copy()
needed = []
for k, mode in enumerate(model.modes):
    speed = model.p['v_c'] if mode >= 0 else model.p['v_d']
    lower = max(model.p['s_min'], math.dist(positions[k], positions[k+1])/speed)
    needed.append(lower-durations[k])
    durations[k] = max(durations[k], lower)
correction = float(max(abs(durations-before)))
output = copy.deepcopy(data)
output.pop('experiment', None)
output['solution'] = dict(r=positions.tolist(), s=durations.tolist(),
    c=[float(t) if mode >= 0 else 0. for t, mode in zip(durations, model.modes)])
energy = fb.diag.replay(output)
output['solution']['e'] = energy
check = fb.diag.residuals(output)
report = dict(solver_status=saved['solver_status'], iterations=saved['iterations'], raw_kkt=saved['raw_kkt'],
    solver_objective_hours=float(sum(before)), corrected_objective_hours=float(sum(durations)),
    duration_correction_hours=correction, duration_correction_limit=1e-10,
    duration_check_passed=correction < 1e-10,
    segments_needing_correction=[dict(segment=k, seconds=float(v*3600)) for k, v in enumerate(needed) if v > 1e-10],
    corrected_original_violation=check['viol'], corrected_min_energy=float(min(energy)),
    corrected_max_energy=float(max(energy)), modes=model.modes, task_stamp=data['task_stamp'],
    note='diagnosis of the single planned restoration; this corrected point was not accepted and is not a result')
h.write(h.HERE/'restoration-diagnosis.json', report)
print(json.dumps(report, indent=1))
