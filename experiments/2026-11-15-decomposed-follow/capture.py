"""Freeze external notes and record dependencies of the continuation and audits."""
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
        'experiments/2026-11-15-stage4-inner/cases/stalled/newton-decomposed/one-update-state.json',
        'experiments/2026-11-15-stage4-inner/cases/stalled/newton-decomposed/initial.json',
        'experiments/2026-11-15-stage4-inner/cases/stalled/newton-decomposed/result.json',
        'experiments/2026-11-15-stage4-inner/support.py',
        'experiments/2026-11-15-stage4-inner/decomposition.py',
        'experiments/2026-11-15-stage4-inner/curvature.py',
        'experiments/2026-11-15-stage2/common.py',
        'experiments/2026-11-15-fidelity/run.py',
        'experiments/2026-11-15-library-trace/trace.py',
        'experiments/2026-11-14-conditioning/newton_al.py',
        'experiments/2026-11-14-reproduction/independent_al.py',
        'experiments/2026-11-14-reproduction/bridge.rs',
        'experiments/2026-11-14-reproduction/bridge-speed.rs',
        'experiments/2026-11-14-reproduction/speed-model.rs',
        'experiments/2026-11-14-resume/fixed-modes/default-fig1-fixed-modes.json',
        'experiments/2026-11-14-restoration/fixed_branch.py',
        'scripts/verify_solutions.py', 'scripts/diagnose_solution.py', 'scripts/carrier_certificate.py']]
    notes = sorted((ROOT.parent/'human').glob('*.md'))
    with tarfile.open(HERE/'human-notes.tar.gz', 'w:gz') as archive:
        for note in notes:
            archive.add(note, arcname='human/'+note.name)
    provenance = dict(date='2026-11-15', base_commit='651a5f1', plan_commit='f667e36',
        recorded_head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        main_source_changed=False, paper_reproduction=False, monte_carlo_rerun=False,
        python=sys.version, executable=sys.executable,
        packages={name: importlib.metadata.version(name) for name in ['numpy', 'scipy', 'matplotlib', 'casadi']},
        rustc=subprocess.check_output(['rustc', '--version'], text=True).strip(),
        environment={key: os.environ.get(key) for key in ['OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'PYTHONPATH', 'PYTHONDONTWRITEBYTECODE']},
        dependency_hashes={str(p.relative_to(ROOT)): digest(p) for p in dependencies},
        library_hashes={name: digest(Path(name)) for name in ['/tmp/uav-fidelity-original.so', '/tmp/uav-fidelity-speed.so']},
        library_note='Evaluators built at 5581585; model evaluator unchanged; AL and Newton outer logic in Python.',
        post_run_change='Only the initial deadline guard was made safe; timeout checkpoint and unchanged normal fixed-AL output checked in timeout-check.json. No rerun of continuation.',
        timing_note='480 seconds excludes upstream initialization/stages 1-4, preflight, restoration and verification.',
        paper_sha256=digest(ROOT.parent/'2609.40201v1.pdf'),
        human_notes={p.name: digest(p) for p in notes})
    (HERE/'provenance.json').write_text(json.dumps(provenance, indent=2)+'\n')
    artifacts = {str(p.relative_to(HERE)): dict(sha256=digest(p), bytes=p.stat().st_size)
        for p in sorted(HERE.rglob('*')) if p.is_file() and p.name != 'artifact-index.json' and '__pycache__' not in p.parts}
    (HERE/'artifact-index.json').write_text(json.dumps(artifacts, indent=2)+'\n')


if __name__ == '__main__':
    main()
