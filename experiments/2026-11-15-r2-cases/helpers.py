"""Helpers of the previous experiments, with the model built for the case named in UAV_R2_CASE.

Everything else (frozen AL, decomposed Hessian, Newton, runner) is loaded unchanged from
../2026-11-15-stage4-inner, ../2026-11-15-decomposed-follow and ../2026-11-15-original-init.
"""
import importlib.util
import os
from pathlib import Path

import numpy as np

BASE = Path(__file__).resolve().parent
FOLLOW = BASE.parent/'2026-11-15-decomposed-follow'
R1 = BASE.parent/'2026-11-15-original-init'
CASE = os.environ['UAV_R2_CASE']
TAU, SEED = (0, 0) if CASE == 'fig1' else (int(CASE[3:CASE.index('-')]), int(CASE[CASE.index('seed')+4:]))
assert CASE == ('fig1' if TAU == 0 else f'tau{TAU}-seed{SEED}')
HERE = Path(os.environ.get('UAV_R2_OUT', BASE/'cases'))/CASE
SOURCE = HERE/'source.json'


def load_from(folder, name):
    """Load a script of an earlier experiment unchanged; its `import helpers` resolves to this file."""
    spec = importlib.util.spec_from_file_location(f'{folder.name}_{name}'.replace('-', '_'), folder/(name+'.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load(name):
    return load_from(FOLLOW, name)


_follow = load_from(FOLLOW, 'helpers')
ROOT, PRIOR = _follow.ROOT, _follow.PRIOR
stage4, decomposition, write, tr = _follow.stage4, _follow.decomposition, _follow.write, _follow.tr
state, assess, export = _follow.state, _follow.assess, _follow.export
fidelity = stage4.old.fidelity


class CaseVariant(fidelity.Variant):
    """The R variant of the fidelity experiment for an arbitrary (tau, seed) instead of Figure 1 only.

    The parent reads a saved Figure-1 solution as a template for the instance. Here the template is
    the case's own initial trajectory from the Rust bridge, so nothing saved enters the model.
    """
    def __init__(self, kind):
        assert kind == 'R'
        self.kind = kind
        self.native = tr.Model(TAU, SEED, fidelity.LIB['normalized'])
        self.reference = tr.Model(TAU, SEED, fidelity.LIB['original'])
        self.n, self.me, self.mi, self.stamps = (getattr(self.native, key) for key in ['n', 'me', 'mi', 'stamps'])
        self.scale = self.native.scale.copy()
        self.ratio = self.scale/self.native.scale
        ns = self.stamps-1
        self.raw_h = np.r_[np.full(ns, 1/14.4), np.ones(self.me-ns)]
        self.raw_g = np.r_[np.ones(ns), np.full(2*ns, 1/14.4), np.full(3*ns, 1/36)]
        self.wh, self.wg = self.raw_h.copy(), self.raw_g.copy()
        self.source = self.native.solution(self.native.y)
        assert self.source['phys']['v_d'] == 36 and self.source['phys']['zeta'] == 2.5  # the constants above
        self.y0 = self.native.y.copy()
        self.x0 = self.y0*self.scale
        self.h, self.g = np.zeros(self.me), np.zeros(self.mi)


fidelity.Variant = CaseVariant  # stage4.Frozen builds its model through this name
