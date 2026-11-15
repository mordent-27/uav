"""Small paired native CLI regression; no claim about the 900-instance distribution."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
from time import monotonic

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASES = [('tau1', ['--tau', '1', '--seed', '0']), ('tau3', ['--tau', '3', '--seed', '0']), ('fig1', ['--fig1'])]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('version', choices=['before', 'after'])
    args = parser.parse_args()
    folder = HERE/'native'/args.version
    folder.mkdir(parents=True, exist_ok=False)
    binary = Path('/tmp')/('uav-stage2-'+args.version)
    shutil.copy2(ROOT/'target/release/uav', binary)
    manifest = dict(version=args.version, binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
        auglag_source_sha256=hashlib.sha256((ROOT/'src/auglag.rs').read_bytes()).hexdigest(), cases=[])
    for name, flags in CASES:
        output = folder/(name+'.json')
        command = [str(binary), 'solve']+flags+['--out', str(output)]
        start = monotonic()
        with (folder/(name+'.log')).open('w') as log:
            try:
                done = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=60)
                status = 'completed' if done.returncode == 0 else 'exit '+str(done.returncode)
            except subprocess.TimeoutExpired:
                status = 'timeout'
        row = dict(name=name, command=command, status=status, wall_seconds=monotonic()-start)
        if status == 'completed':
            data = json.loads(output.read_text())
            row.update(metrics=data['metrics'], final_stage=data['stages'][-1])
        manifest['cases'].append(row)
        print(json.dumps(row), flush=True)
    (folder/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')


if __name__ == '__main__':
    main()
