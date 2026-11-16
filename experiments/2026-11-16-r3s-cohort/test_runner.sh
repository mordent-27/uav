#!/usr/bin/env bash
# No solver: the batch loop stops on STOP before launching anything. usage: experiments/2026-11-16-r3s-cohort/test_runner.sh
set -euo pipefail
cd "$(dirname "$0")"
grep -q 'if \[ -e $D/STOP \]' run_batches.sh
grep -q '^catch_up$' run_batches.sh
bash -n run_batches.sh
echo "runner checks ok"
