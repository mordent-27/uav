"""Condition G and its original initial trajectory, unchanged for direct starts."""
import importlib.util
import os
from pathlib import Path

HERE_DIRECT = Path(__file__).resolve().parent
os.environ['UAV_R2B_COND'] = 'G'
os.environ.setdefault('UAV_R2_OUT', str(HERE_DIRECT/'cases'))
spec = importlib.util.spec_from_file_location('direct_r2b_helpers', HERE_DIRECT.parent/'2026-11-15-r2b-coarse/helpers.py')
r2b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r2b)
globals().update({name: getattr(r2b, name) for name in dir(r2b) if not name.startswith('_')})
R2B = r2b.BASE
BASE = HERE_DIRECT
