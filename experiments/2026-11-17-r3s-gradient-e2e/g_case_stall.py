"""G-only wrapper; original R3s runner/budgets and all other phases unchanged."""
import importlib.util
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'experiments/2026-11-16-r2h-g-first'))
import helpers as h


def main():
    mode=os.environ['UAV_GRADIENT_MODE'];assert mode in ['original','fast']
    if mode=='fast':
        sys.path.insert(0,str(ROOT/'experiments/2026-11-17-r3s-gradient-only'))
        from fast_hessian import hessian_of_al
        h.decomposition.hessian_of_al=hessian_of_al
    path=ROOT/'experiments/2026-11-16-r3s-cohort/g_case_stall.py'
    spec=importlib.util.spec_from_file_location('unchanged_g_case',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.main()


if __name__=='__main__':main()
