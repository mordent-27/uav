# /// script
# requires-python = ">=3.10"
# dependencies = ["matplotlib"]
# ///
"""Draw the counterparts of Fig. 1 and Fig. 2 from a `uav solve --out` JSON file.

    uv run scripts/plot_solution.py out/fig1.json out/fig1.png
"""
import json
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle


def main(src: str, dst: str) -> None:
    d = json.load(open(src))
    inst, sol, modes = d["instance"], d["solution"], d["modes"]
    r = sol["r"]
    fig = plt.figure(figsize=(13, 6.2))
    gs = fig.add_gridspec(2, 2, width_ratios=[1.15, 1])

    ax = fig.add_subplot(gs[:, 0])
    for reg in inst["regions"]:
        ax.add_patch(Circle(reg["o"], reg["rho"], color="#dceefb", zorder=0))
    if "reference" in d:
        ref = d["reference"]["path"]
        ax.plot(*zip(*ref), color="0.6", lw=1.0, ls="--", zorder=1,
                label=f"paper, Fig. 1 ({d['reference']['objective']:.4f} h)")
    ini = d["init"]["r"]
    ax.plot(*zip(*ini), color="#e0a040", lw=0.7, alpha=0.7, zorder=1,
            label=f"warm start ({d['metrics']['init_objective']:.4f} h)")
    first = {"fly": True, "charge": True}
    for k in range(len(r) - 1):
        charging = modes[k] >= 0
        key = "charge" if charging else "fly"
        label = None
        if first[key]:
            first[key] = False
            method = "fixed-mode timing" if "diagnostic" in d else "this code"
            label = "charging on a station" if charging else f"{method} ({d['metrics']['objective']:.4f} h)"
        ax.plot([r[k][0], r[k + 1][0]], [r[k][1], r[k + 1][1]],
                color="#0040d9" if charging else "k", ls=":" if charging else "-",
                lw=2.4 if charging else 1.3, zorder=3, label=label)
    ax.plot(*zip(*r), ".", color="k", ms=4, zorder=4)
    ax.plot(*zip(*inst["tasks"]), "*", color="red", ms=11, zorder=5, label="tasks")
    for i, a in enumerate(inst["tasks"]):
        ax.annotate(str(i + 1), a, textcoords="offset points", xytext=(6, 5), color="red", fontsize=9)
    ax.plot(*inst["r0"], "o", color="k", ms=5, zorder=5)
    ax.plot(*inst["rf"], "s", color="k", ms=5, zorder=5)
    ax.annotate("start", inst["r0"], textcoords="offset points", xytext=(5, -11), fontsize=9)
    ax.annotate("goal", inst["rf"], textcoords="offset points", xytext=(5, -11), fontsize=9)
    ax.set_aspect("equal")
    ax.set_xlabel("X (km)")
    ax.set_ylabel("Y (km)")
    ax.legend(loc="lower right", fontsize=8, framealpha=0.9)
    ax.set_title(f"Trajectory ({len(r)} time stamps)", fontsize=10)

    h = d["history"]
    stamps = h["stamps"]
    task_t = [stamps[k] for k in d["task_stamp"]]
    spans = [(stamps[k], stamps[k + 1]) for k in range(len(modes)) if modes[k] >= 0]

    def shade(a):
        for t0, t1 in spans:
            a.axvspan(t0, t1, color="0.85", lw=0)

    a1 = fig.add_subplot(gs[0, 1])
    shade(a1)
    a1.plot(h["t"], h["e"], "k", lw=1.3)
    a1.plot(task_t, [sol["e"][k] for k in d["task_stamp"]], "*", color="red", ms=8)
    a1.set_ylabel("UAV battery level")
    a1.set_ylim(-0.03, 1.05)
    a1.set_title("Battery level (shaded: charging)", fontsize=10)

    a2 = fig.add_subplot(gs[1, 1], sharex=a1)
    shade(a2)
    a2.plot(h["t"], h["d"], "k", lw=1.3)
    dist_at = {round(t, 9): v for t, v in zip(h["t"], h["d"])}
    a2.plot(task_t, [dist_at.get(round(t, 9), 0.0) for t in task_t], "*", color="red", ms=8)
    a2.set_ylabel("Distance to closest region (km)")
    a2.set_xlabel("Time (h)")
    a2.set_xlim(0, max(h["t"]) * 1.02)

    m = d["metrics"]
    timing_label = "diagnostic time" if "diagnostic" in d else "solve time"
    fig.suptitle(
        f"objective {m['objective']:.4f} h   constraint violation {m['viol']:.1e}   "
        f"{timing_label} {m['seconds']:.2f} s",
        fontsize=11,
    )
    fig.tight_layout()
    fig.savefig(dst, dpi=130)
    print("wrote", dst)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
