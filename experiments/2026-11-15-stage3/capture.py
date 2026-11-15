"""Archive external notes and hash the exact dependencies and saved artifacts."""
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    dependencies = list((ROOT/'src').glob('*.rs'))
    names = ['experiments/2026-11-15-stage2/common.py',
        'experiments/2026-11-15-stage2/continue_al.py',
        'experiments/2026-11-15-stage2/follow-guarded/stage03-start.json',
        'experiments/2026-11-15-stage2/follow-guarded/outer.jsonl.gz',
        'experiments/2026-11-15-fidelity/run.py',
        'experiments/2026-11-15-library-trace/trace.py',
        'experiments/2026-11-14-conditioning/newton_al.py',
        'experiments/2026-11-14-reproduction/independent_al.py',
        'experiments/2026-11-14-reproduction/bridge.rs',
        'experiments/2026-11-14-reproduction/bridge-speed.rs',
        'experiments/2026-11-14-resume/fixed-modes/default-fig1-fixed-modes.json',
        'scripts/verify_solutions.py']
    dependencies += [ROOT/p for p in names]
    notes = sorted((ROOT.parent/'human').glob('*.md'))
    with tarfile.open(HERE/'human-notes.tar.gz', 'w:gz') as archive:
        for note in notes:
            archive.add(note, arcname='human/'+note.name)
    provenance = dict(date='2026-11-15', base_commit='713eaf1', plan_commit='303a7c1',
        native_plan_commit='fb5da5d', recorded_git_head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        main_source_change=False, monte_carlo_rerun=False, paper_reproduction=False,
        python=sys.version, executable=sys.executable,
        packages={name: importlib.metadata.version(name) for name in ['numpy', 'scipy', 'matplotlib']},
        rustc=subprocess.check_output(['rustc', '--version'], text=True).strip(),
        environment={key: os.environ.get(key) for key in ['OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'PYTHONPATH', 'PYTHONDONTWRITEBYTECODE']},
        source_hashes={str(p.relative_to(ROOT)): digest(p) for p in sorted(dependencies)},
        library_hashes={name: digest(Path(name)) for name in ['/tmp/uav-fidelity-original.so', '/tmp/uav-fidelity-speed.so']},
        library_note='Built at 5581585; model evaluator unchanged; AL updates are Python. Rebuild with the two recorded bridge.rs files.',
        paper_sha256=digest(ROOT.parent/'2609.40201v1.pdf'),
        human_notes={note.name: digest(note) for note in notes})
    (HERE/'provenance.json').write_text(json.dumps(provenance, indent=2)+'\n')
    artifacts = {str(p.relative_to(HERE)): dict(sha256=digest(p), bytes=p.stat().st_size)
        for p in sorted(HERE.rglob('*')) if p.is_file() and p.name != 'artifact-index.json' and '__pycache__' not in p.parts}
    (HERE/'artifact-index.json').write_text(json.dumps(artifacts, indent=2)+'\n')


if __name__ == '__main__':
    main()
