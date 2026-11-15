"""Record unchanged dependencies, adopted source files, local inner logs and human notes."""
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
    old = json.loads((HERE.parent/'2026-11-15-r2c-direct-final/provenance.json').read_text())
    files = [ROOT/p for p in old['source_hashes']]
    files += sorted((HERE.parent/'2026-11-15-r2c-direct-final').glob('*.py'))
    files += [ROOT/'scripts/verify_solutions.py']
    summary = json.loads((HERE/'summary.json').read_text())
    for row in summary['regression_cases']+summary['diagnostic_holdout_cases']:
        for phase in [row['G'], row['direct']]:
            if phase is None or not phase['reused']:
                continue
            folder = ROOT/phase['path']
            for name in ['source.json', 'result.json', 'verification.json', 'steps.json',
                         'restored/result.json', 'restored/solution.json']:
                if (folder/name).exists():
                    files.append(folder/name)
    notes = sorted((ROOT.parent/'human').glob('*.md'))
    with tarfile.open(HERE/'human-notes.tar.gz', 'w:gz') as archive:
        for path in notes:
            archive.add(path, arcname='human/'+path.name)
    provenance = dict(date='2026-11-15', base_commit='033a5bb', plan_commit='0d7312f', runner_commit='fa7bcff',
        recorded_head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        python=sys.version, executable=sys.executable,
        packages={name: importlib.metadata.version(name) for name in ['numpy', 'scipy', 'casadi', 'matplotlib']},
        source_hashes={str(path.relative_to(ROOT)):sha(path) for path in sorted(set(files))},
        evaluator_hashes={path:sha(Path(path)) for path in old['evaluator_hashes']},
        execution=summary['execution'], main_source_changed=False, monte_carlo_rerun=False,
        paper_reproduction=False, human_notes={path.name:sha(path) for path in notes})
    (HERE/'provenance.json').write_text(json.dumps(provenance, indent=2)+'\n')
    local = sorted((HERE/'cases').glob('*/*/stages/*/inner*.jsonl.gz'))
    manifest = {str(path.relative_to(HERE)):dict(bytes=path.stat().st_size, sha256=sha(path)) for path in local}
    (HERE/'local-inner-manifest.json').write_text(json.dumps(dict(git_tracked=False, logs=manifest,
        count=len(local), bytes=sum(path.stat().st_size for path in local)), indent=2)+'\n')
    paths = [path for path in sorted(HERE.rglob('*')) if path.is_file() and path not in local
             and path.name != 'artifact-index.json' and '__pycache__' not in path.parts]
    (HERE/'artifact-index.json').write_text(json.dumps({str(path.relative_to(HERE)):
        dict(bytes=path.stat().st_size, sha256=sha(path)) for path in paths}, indent=2)+'\n')


if __name__ == '__main__':
    main()
