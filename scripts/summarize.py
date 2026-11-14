"""Summarise a `uav mc` CSV per number of tasks (no dependencies).

    python3 scripts/summarize.py out/mc.csv [--feasible-tol 1e-3]
"""
import csv
import statistics
import sys


def main() -> None:
    path = sys.argv[1]
    tol = float(sys.argv[sys.argv.index("--feasible-tol") + 1]) if "--feasible-tol" in sys.argv else 1e-3
    rows = list(csv.DictReader(open(path)))
    taus = sorted({int(r["tau"]) for r in rows})
    med = statistics.median
    print(f"{'tau':>3} {'runs':>4} {'N':>3} {'time med':>9} {'time max':>9} {'obj med':>8} {'init med':>8} "
          f"{'viol med':>9} {'viol max':>9} {'viol>tol':>8} {'reorder':>7} {'charges':>7}")
    for tau in taus + [None]:
        sel = [r for r in rows if tau is None or int(r["tau"]) == tau]
        f = lambda k: [float(r[k]) for r in sel]
        print(f"{'all' if tau is None else tau:>3} {len(sel):>4} {int(med(f('stamps'))):>3} "
              f"{med(f('seconds')):>8.2f}s {max(f('seconds')):>8.2f}s {med(f('objective')):>8.4f} "
              f"{med(f('init_objective')):>8.4f} {med(f('viol')):>9.1e} {max(f('viol')):>9.1e} "
              f"{sum(v > tol for v in f('viol')):>8} {sum(int(r['order_changed']) for r in sel):>7} "
              f"{med(f('charges')):>7.1f}")


if __name__ == "__main__":
    main()
