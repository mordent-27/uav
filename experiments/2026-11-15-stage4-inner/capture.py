"""Archive external notes and identify exact model, optimizer and helper sources."""
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
    dependencies = sorted((ROOT/'src').glob('*.rs'))
    dependencies += [ROOT/name for name in [
        'experiments/2026-11-15-stage3/follow/stage04/outer.jsonl.gz',
        'experiments/2026-11-15-stage3/follow/stage04/result.json',
        'experiments/2026-11-15-stage2/common.py',
        'experiments/2026-11-15-fidelity/run.py',
        'experiments/2026-11-15-library-trace/trace.py',
        'experiments/2026-11-14-conditioning/newton_al.py',
        'experiments/2026-11-14-reproduction/independent_al.py',
        'experiments/2026-11-14-reproduction/bridge.rs',
        'experiments/2026-11-14-reproduction/bridge-speed.rs',
        'experiments/2026-11-14-reproduction/speed-model.rs',
        'experiments/2026-11-14-resume/fixed-modes/default-fig1-fixed-modes.json',
        'scripts/verify_solutions.py']]
    notes = sorted((ROOT.parent/'human').glob('*.md'))
    with tarfile.open(HERE/'human-notes.tar.gz', 'w:gz') as archive:
        for note in notes:
            archive.add(note, arcname='human/'+note.name)
    provenance = dict(date='2026-11-15', base_commit='f6fc84a', plan_commit='039eec5',
        curvature_plan_commit='41e3142', recorded_head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        main_source_changed=False, paper_reproduction=False, monte_carlo_rerun=False,
        python=sys.version, executable=sys.executable,
        packages={name: importlib.metadata.version(name) for name in ['numpy', 'scipy', 'matplotlib']},
        rustc=subprocess.check_output(['rustc', '--version'], text=True).strip(),
        environment={k: os.environ.get(k) for k in ['OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'PYTHONPATH', 'PYTHONDONTWRITEBYTECODE']},
        dependency_hashes={str(p.relative_to(ROOT)): digest(p) for p in dependencies},
        library_hashes={name: digest(Path(name)) for name in ['/tmp/uav-fidelity-original.so', '/tmp/uav-fidelity-speed.so', '/tmp/uav-stage4-callback.so']},
        library_note='Model evaluator libraries built at 5581585; model unchanged. Callback library uses current unchanged src/lbfgs.rs.',
        paper_sha256=digest(ROOT.parent/'2609.40201v1.pdf'),
        human_notes={p.name: digest(p) for p in notes})
    (HERE/'provenance.json').write_text(json.dumps(provenance, indent=2)+'\n')
    artifacts = {str(p.relative_to(HERE)): dict(sha256=digest(p), bytes=p.stat().st_size)
        for p in sorted(HERE.rglob('*')) if p.is_file() and p.name != 'artifact-index.json' and '__pycache__' not in p.parts}
    (HERE/'artifact-index.json').write_text(json.dumps(artifacts, indent=2)+'\n')


if __name__ == '__main__':
    main()
