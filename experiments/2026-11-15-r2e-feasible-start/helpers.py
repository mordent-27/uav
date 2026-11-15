"""Same R2e modules and parameters, with an independent output location."""
import importlib.util
import os
from pathlib import Path

HERE_FEASIBLE=Path(__file__).resolve().parent
os.environ['UAV_R2E_KIND']='repaired'
spec=importlib.util.spec_from_file_location('feasible_position_helpers',HERE_FEASIBLE.parent/'2026-11-15-r2e-position-init/helpers.py')
position=importlib.util.module_from_spec(spec)
spec.loader.exec_module(position)
globals().update({name:getattr(position,name) for name in dir(position) if not name.startswith('_')})
R2E=position.BASE
BASE=HERE_FEASIBLE
HERE=BASE/'cases/repaired'/CASE
SOURCE=HERE/'source.json'
INIT=BASE/'initializations'/CASE
