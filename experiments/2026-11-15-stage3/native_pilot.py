"""Test the gate in an isolated Rust source copy, without changing main src."""
import difflib
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from time import monotonic

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASES = [('fig1', ['--fig1']), ('tau1-seed1', ['--tau', '1', '--seed', '1']),
         ('tau3-seed1', ['--tau', '3', '--seed', '1'])]


def write(path, value):
    path.write_text(json.dumps(value, indent=2)+'\n')


def main():
    folder = HERE/'native'
    folder.mkdir(exist_ok=False)
    source = (ROOT/'src/auglag.rs').read_text()
    needle = 'if should_increase_penalty(viol, prev_viol, o) {'
    assert source.count(needle) == 1
    candidate = source.replace(needle,
        'if res.gnorm.is_finite() && res.gnorm <= o.tol_stat && should_increase_penalty(viol, prev_viol, o) {')
    (folder/'candidate-auglag.rs').write_text(candidate)
    (folder/'candidate.patch').write_text(''.join(difflib.unified_diff(
        source.splitlines(True), candidate.splitlines(True), fromfile='src/auglag.rs', tofile='candidate/auglag.rs')))
    hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT/'src').glob('*.rs'))}
    manifest = dict(source_hashes=hashes, versions=[], main_src_changed=False)
    with tempfile.TemporaryDirectory(prefix='uav-stage3-pilot-') as tmp:
        tmp = Path(tmp)
        shutil.copytree(ROOT/'src', tmp/'src')
        for version in ['before', 'after']:
            dest = folder/version
            dest.mkdir()
            (tmp/'src/auglag.rs').write_text(candidate if version == 'after' else source)
            binary = tmp/('uav-'+version)
            command = ['rustc', '--edition=2021', '-C', 'opt-level=3', '-C', 'lto',
                       '-C', 'codegen-units=1', '-g', str(tmp/'src/main.rs'), '-o', str(binary)]
            with (dest/'build.log').open('w') as log:
                subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=60)
            build_text = (dest/'build.log').read_text().rstrip()
            (dest/'build.log').write_text(build_text+'\n' if build_text else '')
            entry = dict(version=version, build_command=command,
                binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(), cases=[])
            for name, flags in CASES:
                command = [str(binary), 'solve']+flags+['--out', str(dest/(name+'.json'))]
                start = monotonic()
                with (dest/(name+'.log')).open('w') as log:
                    try:
                        done = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=60)
                        status = 'completed' if done.returncode == 0 else 'exit '+str(done.returncode)
                    except subprocess.TimeoutExpired:
                        status = 'timeout'
                row = dict(name=name, command=command, status=status, seconds=monotonic()-start)
                if status == 'completed':
                    doc = json.loads((dest/(name+'.json')).read_text())
                    row.update(metrics=doc['metrics'], final_stage=doc['stages'][-1])
                entry['cases'].append(row)
                print(json.dumps(dict(version=version, **row)), flush=True)
            manifest['versions'].append(entry)
            write(folder/'manifest.json', manifest)
    checks = []
    for name, _ in CASES:
        a = json.loads((folder/'before'/(name+'.json')).read_text())
        b = json.loads((folder/'after'/(name+'.json')).read_text())
        assert all(a[k] == b[k] for k in ['instance', 'phys', 'init'])
        checks.append(dict(name=name, initial_input_identical=True,
            before=a['metrics'], after=b['metrics'],
            success_lost=a['metrics']['converged'] and not b['metrics']['converged'],
            original_violation_worse=b['metrics']['viol'] > a['metrics']['viol']+1e-6,
            same_trajectory=a['solution'] == b['solution']))
    assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest() == h for p, h in hashes.items())
    write(folder/'comparison.json', dict(cases=checks, unchanged_main_source=True,
        adoption_blocked=any(r['success_lost'] or r['original_violation_worse'] for r in checks)))


if __name__ == '__main__':
    main()
