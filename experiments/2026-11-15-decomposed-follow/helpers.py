"""Reuse the frozen model and decomposed Hessian from the stage-4 diagnosis."""
import importlib.util
import json
from pathlib import Path
import sys

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PRIOR = HERE.parent/'2026-11-15-stage4-inner'
sys.path.insert(0, str(PRIOR))
import support as stage4

spec = importlib.util.spec_from_file_location('follow_decomposition', PRIOR/'decomposition.py')
decomposition = importlib.util.module_from_spec(spec)
spec.loader.exec_module(decomposition)
SOURCE = PRIOR/'cases/stalled/newton-decomposed/one-update-state.json'
write = stage4.write
tr = stage4.old.fidelity.tr


def state(y, lam, mu, rho, stage):
    return dict(y=y.tolist(), lam=lam.tolist(), mu=mu.tolist(), rho=rho, stage=stage,
        eps=max(.0005, .2*.6**(stage-1)), p=min(12., 2.*1.2**(stage-1)))


def assess(frozen, y, lam, mu):
    m = frozen.m
    return dict(**m.metrics(y, lam, mu), selection=tr.describe(m, y, m.source, m.eps, m.p))


def export(folder, frozen, saved, initial, elapsed, final_pass=False):
    m = frozen.m
    y = np.array(saved['y'])
    q = np.ascontiguousarray(y*m.scale/m.reference.scale)
    doc = m.reference.solution(q)
    doc['init'] = tr.decode(m, np.array(initial['y']), m.source)
    doc['metrics'].update(converged=bool(final_pass), seconds=elapsed, init_objective=sum(doc['init']['s']))
    doc['experiment'] = dict(name='decomposed-Newton-follow', paper_algorithm=False,
        stage=saved['stage'], y_full_precision=q.tolist(), variant_y=y.tolist(),
        common_kkt=saved['common_kkt'], paper_units_kkt=saved['paper_units_kkt'])
    write(folder/'solution.json', doc)
    return doc
