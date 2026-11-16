"""Verification only: import the unchanged R2h model with the fresh-run output root."""
import importlib.util
import os
from pathlib import Path

OUTPUT_I=Path(__file__).resolve().parent
os.environ['UAV_R2H_OUT']=str(OUTPUT_I)
spec=importlib.util.spec_from_file_location('r3s_r2h_helpers',OUTPUT_I.parent/'2026-11-16-r2h-g-first/helpers.py')
prior=importlib.util.module_from_spec(spec);spec.loader.exec_module(prior)
globals().update({name:getattr(prior,name) for name in dir(prior) if not name.startswith('_')})
