"""Shared frozen stage-2 inputs and unchanged fidelity model."""
import gzip
import importlib.util
import json
from pathlib import Path
import sys

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PRIOR = HERE.parent/'2026-11-15-fidelity'
spec = importlib.util.spec_from_file_location('fidelity_model', PRIOR/'run.py')
fidelity = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fidelity)
sys.path.insert(0, str(HERE.parent/'2026-11-14-conditioning'))
import newton_al as newton
write = fidelity.tr.write


def source():
    with gzip.open(PRIOR/'cases/R-expanded/outer.jsonl.gz', 'rt') as handle:
        rows = [json.loads(line) for line in handle]
    index = next(i for i, row in enumerate(rows) if row['stage'] == 2 and row['outer'] == 100)
    before, after = rows[index-1], rows[index]
    assert before['stage'] == 2 and before['outer'] == 99
    return before, after


def model():
    m = fidelity.Variant('R')
    m.stage(.12, 2.4)
    return m


def state(y, lam, mu, rho, stage=2, eps=.12, p=2.4):
    return dict(y=y.tolist(), lam=lam.tolist(), mu=mu.tolist(), rho=rho, stage=stage, eps=eps, p=p)


def assess(m, y, lam, mu):
    return dict(**m.metrics(y, lam, mu), selection=fidelity.tr.describe(m, y, m.source, m.eps, m.p))
