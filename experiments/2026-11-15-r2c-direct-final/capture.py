"""Freeze provenance, external human notes, and hashes of local-only inner logs."""
import hashlib
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys
import tarfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    files = sorted((ROOT/'src').glob('*.rs'))
    for name in ['2026-11-15-r2b-coarse', '2026-11-15-r2-cases', '2026-11-15-decomposed-follow',
                 '2026-11-15-stage4-inner', '2026-11-15-fidelity', '2026-11-15-library-trace',
                 '2026-11-14-restoration', '2026-11-14-reproduction', '2026-11-14-conditioning']:
        files.extend(sorted((HERE.parent/name).glob('*.py')))
    for case in sorted((HERE/'cases').iterdir()):
        for relative in ['source.json', 'result.json', 'restored/result.json']:
            path = HERE.parent/'2026-11-15-r2b-coarse/cases/G'/case.name/relative
            if path.exists():
                files.append(path)
    files.append(ROOT/'scripts/verify_solutions.py')
    notes = sorted((ROOT.parent/'human').glob('*.md'))
    with tarfile.open(HERE/'human-notes.tar.gz', 'w:gz') as archive:
        for path in notes:
            archive.add(path, arcname='human/'+path.name)
    provenance = dict(date='2026-11-15', base_commit='50b7796', plan_commit='a7beecb', runner_commit='ed5f185',
        recorded_head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        python=sys.version, executable=sys.executable,
        packages={name: importlib.metadata.version(name) for name in ['numpy', 'scipy', 'casadi', 'matplotlib']},
        source_hashes={str(p.relative_to(ROOT)): sha(p) for p in sorted(set(files))},
        evaluator_hashes={name: sha(Path(name)) for name in ['/tmp/uav-fidelity-original.so', '/tmp/uav-fidelity-speed.so']},
        execution=json.loads((HERE/'execution.json').read_text()),
        main_source_changed=False, monte_carlo_rerun=False, paper_reproduction=False,
        human_notes={p.name: sha(p) for p in notes})
    (HERE/'provenance.json').write_text(json.dumps(provenance, indent=2)+'\n')
    local = sorted((HERE/'cases').glob('*/stages/*/inner*.jsonl.gz'))
    manifest = {str(p.relative_to(HERE)): dict(bytes=p.stat().st_size, sha256=sha(p)) for p in local}
    (HERE/'local-inner-manifest.json').write_text(json.dumps(dict(git_tracked=False, logs=manifest,
        count=len(local), bytes=sum(p.stat().st_size for p in local)), indent=2)+'\n')
    paths = [p for p in sorted(HERE.rglob('*')) if p.is_file() and p not in local and p.name != 'artifact-index.json' and '__pycache__' not in p.parts]
    (HERE/'artifact-index.json').write_text(json.dumps({str(p.relative_to(HERE)):
        dict(bytes=p.stat().st_size, sha256=sha(p)) for p in paths}, indent=2)+'\n')


if __name__ == '__main__':
    main()
