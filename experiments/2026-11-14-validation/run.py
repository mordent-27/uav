"""Run the preregistered 13-case cohort with the untouched default solver.

Run from uav/: python3 experiments/2026-11-14-validation/run.py
Resume reuses completed logs/JSON; remove the experiment directory to restart elsewhere.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
spec = importlib.util.spec_from_file_location("audit", HERE / "audit.py")
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def run_case(case):
    name, flags = case
    folder = HERE / "cases" / name
    folder.mkdir(parents=True, exist_ok=True)
    result_path = folder / "raw.json"
    cmd = [str(ROOT/"target/release/uav"), "solve", *flags, "--verbose", "--out", str(result_path)]
    status_file = folder / "run.json"
    if not status_file.exists():
        status = dict(name=name, command=cmd, started_utc=datetime.now(timezone.utc).isoformat())
        try:
            with (folder/"solver.log").open("w") as log:
                out = subprocess.run(cmd, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, timeout=90)
            status.update(returncode=out.returncode, timeout=False)
        except subprocess.TimeoutExpired:
            status.update(returncode=None, timeout=True)
        dump(status_file,status)
    status = json.loads(status_file.read_text())
    if status["returncode"] != 0 or not result_path.exists():
        return dict(name=name, run=status, raw=None, polished=None)
    d = json.loads(result_path.read_text())
    raw = audit.inspect(d)
    dump(folder/"raw-audit.json",raw)
    rounded = dict(d,modes=raw["modes"])
    candidate, reason = audit.diag.polish_fixed_modes(rounded)
    polished = None
    if candidate:
        # Array-heavy artifacts stay compact; metrics/audits remain readable.
        (folder/"polished.json").write_text(json.dumps(candidate, separators=(",",":"),allow_nan=False)+"\n")
        polished = audit.inspect(candidate)
        dump(folder/"polished-audit.json",polished)
    print(name, "raw",raw["original_pass"], "battery",raw["exact_mode_battery_pass"],
          "station",raw["one_station_pass"], "polished",None if polished is None else polished["physically_usable"], flush=True)
    return dict(name=name,run=status,raw=raw,polished=polished,polish_status=reason)


def main():
    cases = [("fig1",["--fig1"])] + [
        (f"tau{tau}-seed{seed}",["--tau",str(tau),"--seed",str(seed)])
        for tau in (1,3,5,7) for seed in (0,1,2)]
    provenance = dict(head=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip(),
                      sources={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT/"src").glob("*.rs"))},
                      binary_sha256=hashlib.sha256((ROOT/"target/release/uav").read_bytes()).hexdigest(),
                      thresholds=audit.TOL, max_workers=2, per_case_timeout_seconds=90,
                      cases=[dict(name=n,flags=f) for n,f in cases])
    path=HERE/"provenance.json"
    if path.exists():
        old=json.loads(path.read_text())
        assert old["sources"]==provenance["sources"] and old["binary_sha256"]==provenance["binary_sha256"]
    else:
        dump(path,provenance)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(run_case,cases))
    summary = dict(total=len(cases), completed=sum(r["raw"] is not None for r in results))
    for variant in ("raw","polished"):
        selected=[r[variant] for r in results if r[variant] is not None]
        summary[variant]=dict(available=len(selected), original_pass=sum(r["original_pass"] for r in selected),
                             battery_pass=sum(r["exact_mode_battery_pass"] for r in selected),
                             station_pass=sum(r["one_station_pass"] for r in selected),
                             physically_usable=sum(r["physically_usable"] for r in selected),
                             charging_domain_fail=sum(not r["charging_domain_pass"] for r in selected))
    dump(HERE/"results.json",dict(summary=summary,cases=results))
    print(json.dumps(summary,indent=2))


if __name__=="__main__":
    main()
