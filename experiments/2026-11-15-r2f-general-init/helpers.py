"""Unchanged R model and final-stage solver, arbitrary case and independent outputs."""
import importlib.util
import os
from pathlib import Path

HERE_GENERAL=Path(__file__).resolve().parent
KIND=os.environ.get('UAV_R2F_KIND','original')
assert KIND in ('original','repaired')
os.environ['UAV_R2B_COND']='G'
os.environ['UAV_R2_OUT']=str(HERE_GENERAL/'cases'/KIND)
spec=importlib.util.spec_from_file_location('general_r2b_helpers',HERE_GENERAL.parent/'2026-11-15-r2b-coarse/helpers.py')
r2b=importlib.util.module_from_spec(spec);spec.loader.exec_module(r2b)
globals().update({name:getattr(r2b,name) for name in dir(r2b) if not name.startswith('_')})
R2B=r2b.BASE
R2E=HERE_GENERAL.parent/'2026-11-15-r2e-position-init'
DIRECT=HERE_GENERAL.parent/'2026-11-15-r2c-direct-final'
BASE=HERE_GENERAL
INIT=BASE/'initializations'/CASE
