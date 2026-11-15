"""Run the 12 cases of PLAN.md once each, three at a time. Usage: python run_all.py <python> [case ...]"""
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASES = [f'tau{t}-seed{s}' for t in (1, 3, 5, 7) for s in (0, 1, 2)]


def run(name):
    folder = HERE/'cases'/name
    if folder.exists():
        return name, 'exists; not run again'
    env = dict(os.environ, UAV_R2_CASE=name)
    with open(HERE/'logs'/f'{name}.log', 'w') as log:
        code = subprocess.run([sys.argv[1], str(HERE/'case.py')], stdout=log, stderr=subprocess.STDOUT, env=env).returncode
    return name, code


if __name__ == '__main__':
    (HERE/'logs').mkdir(exist_ok=True)
    cases = sys.argv[2:] or CASES
    assert all(c in CASES for c in cases)
    with ThreadPoolExecutor(3) as pool:
        for name, code in pool.map(run, cases):
            print(name, code, flush=True)
