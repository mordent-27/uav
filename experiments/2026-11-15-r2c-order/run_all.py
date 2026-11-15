"""Run condition O of PLAN.md once per case whose start differs from the index order, three at a time.

Usage: python run_all.py <python>
"""
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
ALL = ['fig1']+[f'tau{t}-seed{s}' for t in (1, 3, 5, 7) for s in (0, 1, 2)]


def run(name):
    if json.loads((HERE/'preflight'/f'{name}.json').read_text())['identical_start']:
        return name, 'same start as the index order; the saved G result is used'
    if (HERE/'cases'/name).exists():
        return name, 'exists; not run again'
    env = dict(os.environ, UAV_R2_CASE=name)
    env.pop('UAV_R2_OUT', None)
    with open(HERE/'logs'/f'{name}.log', 'w') as log:
        code = subprocess.run([sys.argv[1], str(HERE/'case.py')], stdout=log, stderr=subprocess.STDOUT, env=env).returncode
    return name, code


if __name__ == '__main__':
    (HERE/'logs').mkdir(exist_ok=True)
    with ThreadPoolExecutor(3) as pool:
        for name, code in pool.map(run, ALL):
            print(name, code, flush=True)
