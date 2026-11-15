"""R1 capture.py with this experiment's dependencies, commits and notes."""
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
        'experiments/2026-11-15-original-init/run.py',
        'experiments/2026-11-15-r2-cases/helpers.py',
        'experiments/2026-11-15-r2-cases/restore.py',
        'experiments/2026-11-15-r2-cases/verify.py',
        'experiments/2026-11-15-r2-cases/case.py',
        'experiments/2026-11-15-r2-cases/summary.json',
        'experiments/2026-11-15-r2-cases/r1-rejudged.json',
        'experiments/2026-11-15-original-init/verify.py',
        'experiments/2026-11-15-original-init/source.json',
        'experiments/2026-11-15-original-init/solution.json',
        'experiments/2026-11-15-original-init/restored/solver.json',
        'experiments/2026-11-15-original-init/stages/stage01/outer.jsonl.gz',
        'experiments/2026-11-15-decomposed-follow/helpers.py',
        'experiments/2026-11-15-decomposed-follow/newton.py',
        'experiments/2026-11-15-decomposed-follow/run.py',
        'experiments/2026-11-15-decomposed-follow/restore.py',
        'experiments/2026-11-15-decomposed-follow/verify.py',
        'experiments/2026-11-15-decomposed-follow/analyze.py',
        'experiments/2026-11-15-decomposed-follow/stages/stage05/outer.jsonl.gz',
        'experiments/2026-11-15-warm-start/default-seed.json',
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
    provenance = dict(date='2026-11-15', base_commit='576a5e7', plan_commit='1d805d1',
        plan_note='PLAN.md and the runner were committed before the solve',
        recorded_head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        main_source_changed=False, paper_reproduction=False, monte_carlo_rerun=False,
        python=sys.version, executable=sys.executable,
        packages={name: importlib.metadata.version(name) for name in ['numpy', 'scipy', 'matplotlib', 'casadi']},
        rustc=subprocess.check_output(['rustc', '--version'], text=True).strip(),
        environment={key: os.environ.get(key) for key in ['OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'PYTHONPATH', 'PYTHONDONTWRITEBYTECODE']},
        dependency_hashes={str(p.relative_to(ROOT)): digest(p) for p in dependencies},
        library_hashes={name: digest(Path(name)) for name in ['/tmp/uav-fidelity-original.so', '/tmp/uav-fidelity-speed.so']},
        library_note='Evaluators built at 5581585; model evaluator unchanged; AL and Newton outer logic in Python.',
        timing_note='Per-case limits as in R1; S ran alone, G and T three at a time. inner*.jsonl.gz are kept locally and not tracked by Git.',
        paper_sha256=digest(ROOT.parent/'2609.40201v1.pdf'),
        human_notes={p.name: digest(p) for p in notes})
    (HERE/'provenance.json').write_text(json.dumps(provenance, indent=2)+'\n')
    artifacts = {str(p.relative_to(HERE)): dict(sha256=digest(p), bytes=p.stat().st_size)
        for p in sorted(HERE.rglob('*')) if p.is_file() and p.name != 'artifact-index.json' and '__pycache__' not in p.parts}
    (HERE/'artifact-index.json').write_text(json.dumps(artifacts, indent=2)+'\n')


if __name__ == '__main__':
    main()
