"""R2a helpers plus the stage rules of the condition named in UAV_R2B_COND (see PLAN.md).

B and S: tolerance 1e-6, 200 outer iterations, never advance without the tolerance (the R2a rules).
G: stages 1-12 advance after 10 outer iterations even without the tolerance.
T: stages 1-12 use the tolerance max(1e-6, 1e-3*eps).
Stage 13 is the same in every condition.
"""
import importlib.util
import os
from pathlib import Path

HERE_R2B = Path(__file__).resolve().parent
CONDITION = os.environ['UAV_R2B_COND']
assert CONDITION in ('B', 'S', 'G', 'T')
os.environ.setdefault('UAV_R2_OUT', str(HERE_R2B/'cases'/CONDITION))

_spec = importlib.util.spec_from_file_location('r2a_helpers', HERE_R2B.parent/'2026-11-15-r2-cases/helpers.py')
_r2a = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_r2a)
globals().update({name: getattr(_r2a, name) for name in dir(_r2a) if not name.startswith('_')})
R2A = _r2a.BASE
BASE = HERE_R2B


def tolerance(stage):
    """Common-KKT tolerance for leaving a stage and for the penalty rule."""
    if CONDITION == 'T' and stage < 13:
        return max(1e-6, 1e-3*max(.0005, .2*.6**(stage-1)))
    return 1e-6


def outer_cap(stage):
    if stage == 13:
        return 600
    return 10 if CONDITION == 'G' else 200


def advance_anyway(stage, stop):
    """Whether a stage that ended without its tolerance still hands its point to the next stage."""
    return CONDITION == 'G' and stage < 13 and stop == 'outer_limit'
