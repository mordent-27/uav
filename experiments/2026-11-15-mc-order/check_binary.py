"""Before solving: the current binary reproduces saved index-order outputs of mc-rho1e4 (run 0 of each tau)."""
import json
import subprocess
import tarfile
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OLD = HERE.parent/'2026-11-14-conditioning/mc-rho1e4'


def strip(d):
    d = json.loads(json.dumps(d))
    d['metrics'].pop('seconds', None)
    return d


def main():
    assert not (HERE/'binary-check.json').exists()
    rows = []
    with tempfile.TemporaryDirectory() as folder, tarfile.open(OLD/'cases.tar.gz') as archive:
        for tau in range(1, 10):
            member = f'cases/tau{tau}/run000/raw.json'
            saved = json.load(archive.extractfile(member))
            out = f'{folder}/tau{tau}.json'
            subprocess.run([str(ROOT/'target/release/uav'), 'solve', '--tau', str(tau), '--seed', str(tau*10000),
                            '--rho0', '1e4', '--rho-mult', '1', '--out', out], check=True, capture_output=True)
            new = json.load(open(out))
            same = strip(saved) == strip(new)
            rows.append(dict(tau=tau, seed=tau*10000, identical_output=same, objective=new['metrics']['objective'],
                             saved_objective=saved['metrics']['objective']))
            print(rows[-1], flush=True)
    (HERE/'binary-check.json').write_text(json.dumps(dict(all_identical=all(r['identical_output'] for r in rows),
        note='all fields of raw.json except metrics.seconds', cases=rows), indent=2)+'\n')
    assert all(r['identical_output'] for r in rows)


if __name__ == '__main__':
    main()
