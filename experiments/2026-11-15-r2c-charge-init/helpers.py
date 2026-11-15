"""Condition G unchanged; only the supplied initial e/s/c will differ."""
import importlib.util
import os
from pathlib import Path

HERE_CHARGE = Path(__file__).resolve().parent
os.environ['UAV_R2B_COND'] = 'G'
os.environ.setdefault('UAV_R2_OUT', str(HERE_CHARGE/'cases'))
spec = importlib.util.spec_from_file_location('charge_r2b_helpers', HERE_CHARGE.parent/'2026-11-15-r2b-coarse/helpers.py')
r2b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r2b)
globals().update({name: getattr(r2b, name) for name in dir(r2b) if not name.startswith('_')})
R2B = r2b.BASE
BASE = HERE_CHARGE
INIT = BASE/'initializations'/CASE
