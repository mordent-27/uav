"""Load the unchanged condition-G model and set only the output location."""
import importlib.util
import os
from pathlib import Path

HERE_R2D = Path(__file__).resolve().parent
PHASE = os.environ['UAV_R2D_PHASE']
assert PHASE in ('G', 'direct')
os.environ['UAV_R2B_COND'] = 'G'
os.environ['UAV_R2_OUT'] = str(HERE_R2D/'cases'/PHASE)
spec = importlib.util.spec_from_file_location('fallback_r2b_helpers', HERE_R2D.parent/'2026-11-15-r2b-coarse/helpers.py')
r2b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r2b)
globals().update({name: getattr(r2b, name) for name in dir(r2b) if not name.startswith('_')})
R2B = r2b.BASE
DIRECT = HERE_R2D.parent/'2026-11-15-r2c-direct-final'
BASE = HERE_R2D
