"""Run one condition of PLAN.md once per case. Usage: python run_all.py <python> <S|G|T> <workers>"""
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
ALL = ['fig1']+[f'tau{t}-seed{s}' for t in (1, 3, 5, 7) for s in (0, 1, 2)]
CASES = dict(S=['tau5-seed2', 'tau7-seed0', 'tau7-seed1'], G=ALL, T=ALL)


def run(job):
    condition, name = job
    if (HERE/'cases'/condition/name).exists():
        return name, 'exists; not run again'
    env = dict(os.environ, UAV_R2_CASE=name, UAV_R2B_COND=condition)
    env.pop('UAV_R2_OUT', None)
    with open(HERE/'logs'/f'{condition}-{name}.log', 'w') as log:
        code = subprocess.run([sys.argv[1], str(HERE/'case.py')], stdout=log, stderr=subprocess.STDOUT, env=env).returncode
    return name, code


if __name__ == '__main__':
    condition, workers = sys.argv[2], int(sys.argv[3])
    assert (condition, workers) in [('S', 1), ('G', 3), ('T', 3)]
    (HERE/'logs').mkdir(exist_ok=True)
    with ThreadPoolExecutor(workers) as pool:
        for name, code in pool.map(run, [(condition, name) for name in CASES[condition]]):
            print(condition, name, code, flush=True)
