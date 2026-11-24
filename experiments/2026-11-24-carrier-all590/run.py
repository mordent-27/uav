"""Solve base and (R)-only fixed-assignment NLPs on the 590 points (resumable, never overwrites).
usage (from uav/):  python experiments/2026-11-24-carrier-all590/run.py [--workers 8] [--pilot] [--limit N]
  --pilot : only the six earlier cases, into pilot/ (compared with the earlier experiments)
"""
import argparse, json, multiprocessing as mp, os, platform, shutil, sys, time
from datetime import datetime, timezone
from common import HERE, ROOT, PILOT, targets, load, classify, write_gz, check, carriers

_old = _model = None


def init():
    global _old, _model
    import importlib.util
    sys.path.insert(0, str(ROOT/'experiments/2026-11-20-carrier-followup'))
    import model as m  # ReducedBranch, and the frozen 2026-11-18 Branch as m.old
    _model, _old = m, m.old


def solve_one(row):
    reference = load(row)
    out = dict(case=row['case'], tau=row['tau'], route=row['route'], selected=row['selected'], jump=row['jump'],
               returned_hours=row['returned_hours'], excess_km=row['excess_km'], input_sha256=row['sha256'])
    solutions = {}
    bounds = (reference['phys']['e_min'], reference['phys']['e_max'])
    for method in ('base', 'R'):
        start = time.monotonic()
        try:
            branch = _old.Branch(reference, False) if method == 'base' else _model.ReducedBranch(reference)
            d, res, _ = branch.solve()
            if method == 'R':
                d['carrier_positions'] = carriers(d)
            audit = check(d, reference)
            cls = classify(method, res['solver_success'], res['max_roundoff_time_correction_hours'], audit, bounds)
            out[method] = dict(cls=cls, objective_hours=res['objective_hours'], solver_status=res['solver_status'],
                               solver_success=res['solver_success'], iterations=res['iterations'],
                               correction_hours=res['max_roundoff_time_correction_hours'], kkt=res['kkt'],
                               R_excess_km=audit['R_excess_km'], original_residual=audit['original_residual'],
                               min_energy=audit['min_energy'], seconds=time.monotonic()-start)
            solutions[method] = d['solution']
        except Exception as e:  # recorded, not fatal: counts as rejected with the error text
            out[method] = dict(cls='rejected', error=repr(e)[:500], seconds=time.monotonic()-start)
    return out, solutions


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--workers', type=int, default=8)
    ap.add_argument('--pilot', action='store_true'); ap.add_argument('--limit', type=int)
    a = ap.parse_args()
    assert all(os.environ.get(k) == '1' for k in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS')), 'set BLAS threads to 1'
    base = HERE/('pilot' if a.pilot else 'runs')
    rows = targets(); assert len(rows) == 590
    if a.pilot:
        rows = [r for r in rows if r['case'] in PILOT]
    base.mkdir(exist_ok=True)
    for folder in sorted(p for p in base.iterdir() if p.is_dir() and not (p/'result.json').exists()):
        dest = HERE/'aborted'/f"{folder.name}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}"
        dest.parent.mkdir(exist_ok=True); shutil.move(str(folder), str(dest)); print('moved unfinished', folder.name, '->', dest.name, flush=True)
    todo = [r for r in rows if not (base/r['case']/'result.json').exists()]
    if a.limit:
        todo = todo[:a.limit]
    print(f'{len(rows)-len(todo)} done, {len(todo)} to solve, workers={a.workers}', flush=True)
    log = HERE/('pilot-launches.jsonl' if a.pilot else 'launches.jsonl')
    with open(log, 'a') as f:
        f.write(json.dumps(dict(utc=datetime.now(timezone.utc).isoformat(), todo=len(todo), workers=a.workers,
                                python=platform.python_version(), argv=sys.argv))+'\n')
    t0 = time.monotonic(); n = 0
    with mp.get_context('spawn').Pool(a.workers, initializer=init) as pool:
        for out, sols in pool.imap_unordered(solve_one, todo):
            folder = base/out['case']; folder.mkdir(exist_ok=False)
            for method, sol in sols.items():
                write_gz(folder/f'{method}.json.gz', sol)
            (folder/'result.json').write_text(json.dumps(out, indent=1, allow_nan=False)+'\n')
            n += 1
            print(f"[{n}/{len(todo)} {time.monotonic()-t0:.0f}s] {out['case']} base={out['base']['cls']} R={out['R']['cls']}", flush=True)


if __name__ == '__main__':
    main()
