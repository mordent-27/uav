"""Run the 13 fixed cases for the conditions of PLAN.md (4 in parallel, 600 s each)."""
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
LIB = {'N': 'speed', 'L': 'speed', 'L0': 'bridge'}
CASES = [('fig1', 0, 0)] + [(f'tau{t}-seed{s}', t, s) for t in (1, 3, 5, 7) for s in (0, 1, 2)]


def run(job):
    cond, (name, tau, seed), libdir, extra = job
    out = HERE / 'cases' / cond
    out.mkdir(parents=True, exist_ok=True)
    summary = out / f'{name}.json'
    if summary.exists():
        return
    cmd = [sys.executable, str(HERE / 'newton_al.py'), '--library', f'{libdir}/{LIB[cond[:2].rstrip("_")]}.so',
           '--backend', 'newton' if cond.startswith('N') else 'rust',
           '--inner', '300' if cond.startswith('N') else '2000', '--tau', str(tau), '--seed', str(seed),
           '--timeout', '600', '--out', str(out / f'{name}.outer.jsonl'), '--summary', str(summary)] + extra
    with open(out / f'{name}.log', 'w') as log:
        subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT)


if __name__ == '__main__':
    libdir, conds = sys.argv[1], sys.argv[2].split(',')
    extra = sys.argv[3:] or ['--rho0', '1e4', '--rho-mult', '1']
    with ThreadPoolExecutor(4) as pool:
        list(pool.map(run, [(c, case, libdir, extra) for c in conds for case in CASES]))
    for cond in conds:
        print(f'== {cond}')
        for name, _, _ in CASES:
            path = HERE / 'cases' / cond / f'{name}.json'
            if not path.exists():
                print(f'{name:<12} no output')
                continue
            d = json.loads(path.read_text())
            print(f'{name:<12} kkt {str(d["kkt_converged"]):<5} final {str(d["reached_final_stage"]):<5} '
                  f'stat {d["stat"]:.1e} feas {d["feas"]:.1e} comp {d["comp"]:.1e} viol {d["metrics"]["viol"]:.1e} '
                  f'f {d["metrics"]["objective"]:.4f} outer {d["outer_total"]:>3} evals {d["evals"]:>8} '
                  f'{d["seconds"]:6.1f}s lam_mode {d["lam_mode"]:.1e}')
