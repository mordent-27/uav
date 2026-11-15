"""Reuse condition G's model; solve only its unchanged final-stage runner."""
import importlib.util
import os
from pathlib import Path

HERE_POSITION = Path(__file__).resolve().parent
KIND = os.environ['UAV_R2E_KIND']
assert KIND in ('original', 'repaired')
os.environ['UAV_R2B_COND'] = 'G'
os.environ['UAV_R2_OUT'] = str(HERE_POSITION/'cases'/KIND)
spec = importlib.util.spec_from_file_location('position_r2b_helpers', HERE_POSITION.parent/'2026-11-15-r2b-coarse/helpers.py')
r2b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r2b)
globals().update({name:getattr(r2b,name) for name in dir(r2b) if not name.startswith('_')})
R2B = r2b.BASE
R2D = HERE_POSITION.parent/'2026-11-15-r2d-fallback'
DIRECT = HERE_POSITION.parent/'2026-11-15-r2c-direct-final'
BASE = HERE_POSITION
INIT = BASE/'initializations'/CASE
