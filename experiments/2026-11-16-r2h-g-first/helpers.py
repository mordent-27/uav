"""Reuse numerical modules unchanged, with phase-specific R2h output paths."""
import importlib.util
import os
from pathlib import Path

CODE_H=Path(__file__).resolve().parent
PHASE=os.environ.get('UAV_R2H_PHASE','G')
assert PHASE in ('G','fallback')
os.environ.setdefault('UAV_R2F_KIND','original')
spec=importlib.util.spec_from_file_location('g_first_r2g_helpers',CODE_H.parent/'2026-11-15-r2g-incumbent/helpers.py')
r2g=importlib.util.module_from_spec(spec);spec.loader.exec_module(r2g)
globals().update({name:getattr(r2g,name) for name in dir(r2g) if not name.startswith('_')})
R2G=r2g.BASE
R2D=CODE_H.parent/'2026-11-15-r2d-fallback'
BASE=CODE_H
OUT=Path(os.environ.get('UAV_R2H_OUT',BASE)).resolve()
HERE=OUT/'cases'/PHASE/CASE
SOURCE=HERE/'source.json'
INIT=OUT/'initializations'/CASE
INPUT=OUT/'inputs'/CASE
