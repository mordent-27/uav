import importlib.util
import os
from pathlib import Path

OUT_DIAG=Path(__file__).resolve().parent
os.environ.setdefault('UAV_R2_CASE','fig1')
os.environ['UAV_R2H_OUT']=str(OUT_DIAG)
spec=importlib.util.spec_from_file_location('bound_push_r2h',OUT_DIAG.parent/'2026-11-16-r2h-g-first/helpers.py')
previous=importlib.util.module_from_spec(spec);spec.loader.exec_module(previous)
globals().update({name:getattr(previous,name) for name in dir(previous) if not name.startswith('_')})
