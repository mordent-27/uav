"""R2f model/initialization/final solver unchanged; independent R2g output locations."""
import importlib.util
import os
from pathlib import Path

HERE_RETENTION=Path(__file__).resolve().parent
os.environ.setdefault('UAV_R2F_KIND','original')
spec=importlib.util.spec_from_file_location('retention_r2f_helpers',HERE_RETENTION.parent/'2026-11-15-r2f-general-init/helpers.py')
r2f=importlib.util.module_from_spec(spec);spec.loader.exec_module(r2f)
globals().update({name:getattr(r2f,name) for name in dir(r2f) if not name.startswith('_')})
R2F=r2f.BASE
BASE=HERE_RETENTION
HERE=BASE/'cases'/KIND/CASE
SOURCE=HERE/'source.json'
INIT=BASE/'initializations'/CASE
