"""R2b helpers (rules of condition G) with the nearest-order initial trajectory as the start point."""
import importlib.util
import os
from pathlib import Path

import numpy as np

HERE_ORDER = Path(__file__).resolve().parent
os.environ['UAV_R2B_COND'] = 'G'
os.environ.setdefault('UAV_R2_OUT', str(HERE_ORDER/'cases'))

_spec = importlib.util.spec_from_file_location('r2b_helpers', HERE_ORDER.parent/'2026-11-15-r2b-coarse/helpers.py')
_r2b = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_r2b)
globals().update({name: getattr(_r2b, name) for name in dir(_r2b) if not name.startswith('_')})
R2B = _r2b.BASE
BASE = HERE_ORDER
NEAREST_LIB = '/tmp/uav-r2c-nearest.so'  # rustc --edition=2021 --crate-type cdylib -O bridge-nearest.rs -o <this>


def nearest_start(m):
    """Initial trajectory of Order::Nearest in the variables of model m (full precision)."""
    other = tr.Model(TAU, SEED, NEAREST_LIB)  # noqa: F821 (names come from the R2b helpers)
    try:
        assert (other.n, other.me, other.mi, other.stamps) == (m.n, m.me, m.mi, m.stamps)
        np.testing.assert_array_equal(other.scale, m.native.scale)
        assert other.solution(other.y)['instance'] == m.source['instance']
        return other.y.copy()
    finally:
        other.close()
