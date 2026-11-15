"""Prespecified initialization screen and conditional six-case pilot/expansion."""
import json
import os
from pathlib import Path
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

HERE = Path(__file__).resolve().parent
ALL = ['fig1']+[f'tau{t}-seed{s}' for t in (1, 3, 5, 7) for s in (0, 1, 2)]
FAIL = ['tau1-seed2', 'tau5-seed0', 'tau7-seed0', 'tau7-seed1']
CONTROL = ['tau1-seed0', 'fig1']


def execute(script, name):
    env = dict(os.environ, UAV_R2_CASE=name)
    env.pop('UAV_R2_OUT', None)
    with (HERE/'logs'/f'{script}-{name}.log').open('w') as log:
        done = subprocess.run([sys.executable, str(HERE/(script+'.py'))], env=env,
            stdout=log, stderr=subprocess.STDOUT)
    print(json.dumps(dict(script=script, case=name, returncode=done.returncode)), flush=True)
    return name, done.returncode


def run_case(name):
    initial = json.loads((HERE/'initializations'/name/'result.json').read_text())
    if not initial['accepted']:
        return name, 'initialization_failed'
    assert not (HERE/'cases'/name).exists(), 'refuse to overwrite case'
    return execute('case', name)


def accepted(name):
    p = HERE/'cases'/name/'restored/result.json'
    return p.exists() and json.loads(p.read_text())['accepted']


def main():
    assert not (HERE/'initializations').exists(), 'refuse to overwrite initialization'
    (HERE/'logs').mkdir(exist_ok=False)
    for name in ALL:
        _, code = execute('initialize', name)
        assert code == 0, 'initialization script error; inspect saved outputs'
    pilot = FAIL+CONTROL
    with ThreadPoolExecutor(3) as pool:
        outcomes = list(pool.map(run_case, pilot))
    improved = [name for name in FAIL if accepted(name)]
    controls_ok = True
    for name in CONTROL:
        if not accepted(name):
            controls_ok = False
            continue
        baseline = json.loads((HERE.parent/'2026-11-15-r2b-coarse/cases/G'/name/'restored/result.json').read_text())
        changed = json.loads((HERE/'cases'/name/'restored/result.json').read_text())
        controls_ok &= (changed['objective']-baseline['objective'])*3600 <= .01
    decision = dict(pilot_outcomes=outcomes, newly_accepted_failed_cases=improved,
        controls_pass_without_time_regression=bool(controls_ok), expand=bool(improved and controls_ok))
    (HERE/'decision.json').write_text(json.dumps(decision, indent=2)+'\n')
    print(json.dumps(decision), flush=True)
    if decision['expand']:
        with ThreadPoolExecutor(3) as pool:
            list(pool.map(run_case, [name for name in ALL if name not in pilot]))


if __name__ == '__main__':
    main()
