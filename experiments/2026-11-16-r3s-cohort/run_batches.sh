#!/usr/bin/env bash
# usage: experiments/2026-11-16-r3s-cohort/run_batches.sh [N]   (run from anywhere; N = number of batches, default 1)
# Each batch: restore missing evaluators (hash-checked) -> driver.py (next pending batch, <=8 inputs, 8 threads)
#             -> reverify.py -> audit_outputs.py -> aggregate.py.
# Stops at the first failing step. Already finished inputs are never re-run; partial outputs block all launches (see USAGE.md).
# Launch records and logs are never overwritten: a repeated attempt for the same batch gets an -attemptNN suffix.
set -euo pipefail
N=${1:-1}
cd "$(dirname "$0")/../.."
D=experiments/2026-11-16-r3s-cohort
PY=${UAV_PYTHON:-/home/mordent/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/bin/python}
export PYTHONPATH=${UAV_PYTHONPATH:-/home/mordent/.cache/uv/archive-v0/IH8olt7ky0AxR5WV:/home/mordent/.cache/uv/environments-v2/sys-id-chirp-1714f8f5f4d59f0e/lib/python3.12/site-packages}
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1

fresh() {  # fresh <path-without-ext> <ext>: first free name, never an existing file
  local f="$1$2" k=0
  while [ -e "$f" ]; do k=$((k+1)); f="$1-attempt$(printf %02d $k)$2"; done
  echo "$f"
}

for i in $(seq 1 "$N"); do
  "$PY" $D/restore_evaluators.py
  NEXT=$("$PY" -c "import sys;sys.path.insert(0,'$D');import driver as d;t=d.read(d.BASE/'targets.json');s=d.case_states(d.BASE,t['cases'],d.CARRY);b,n=d.choose_batch(t['cases'],s);print('' if b is None else f'{b:03d}')")
  if [ -z "$NEXT" ]; then echo "no pending batch"; break; fi
  echo "== batch $NEXT start $(date -Iseconds)"
  mkdir -p $D/batches/$NEXT
  RECORD=$(fresh $D/batches/$NEXT/launch-record .json)
  "$PY" -c "import json,subprocess,sys;json.dump(dict(date=sys.argv[1],cwd=sys.argv[2],head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),command='run_batches.sh: driver.py --batch '+sys.argv[3]+' -> reverify.py -> audit_outputs.py -> aggregate.py',python=sys.argv[4],pythonpath=sys.argv[5],recorded_before_completion=True,retry_allowed=False,cached_solves=0),open(sys.argv[6],'x'),indent=2)" "$(date -Iseconds)" "$PWD" "$((10#$NEXT))" "$PY" "$PYTHONPATH" "$RECORD"
  "$PY" $D/driver.py --batch $((10#$NEXT)) > "$(fresh $D/batch$NEXT .log)" 2>&1
  UAV_R3_BATCH=$NEXT "$PY" $D/reverify.py > "$(fresh $D/batches/$NEXT/reverify .log)" 2>&1
  UAV_R3_BATCH=$NEXT "$PY" $D/audit_outputs.py > "$(fresh $D/batches/$NEXT/audit .log)" 2>&1
  "$PY" $D/aggregate.py > "$(fresh $D/batches/$NEXT/aggregate .log)" 2>&1
  echo "== batch $NEXT done $(date -Iseconds)"
done
