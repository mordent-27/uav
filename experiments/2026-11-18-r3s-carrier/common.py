"""Shared paths and pure helpers (no carrier logic here: verify.py must stay independent)."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
COHORT = ROOT/'experiments/2026-11-16-r3s-cohort'


def read(path): return json.loads(Path(path).read_text())
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def tau(case): return int(case.split('-')[0][3:])


def revisits(modes):
    """Regions whose charging segments are not one contiguous block (another segment in between)."""
    out = []
    for j in sorted({m for m in modes if m >= 0}):
        ks = [k for k, m in enumerate(modes) if m == j]
        if any(b != a+1 for a, b in zip(ks, ks[1:])):
            out.append(j)
    return out


def choose(rows):
    """Experiment-2 targets fixed in PLAN.md: rows = [(max_excess_km, case)] of infeasible points."""
    rows = sorted(rows)
    m = len(rows)
    if m <= 6:
        return [c for _, c in rows]
    picks = []
    for q in (0, .2, .4, .6, .8, 1.):
        c = rows[round(q*(m-1))][1]
        if c not in picks:
            picks.append(c)
    return picks
