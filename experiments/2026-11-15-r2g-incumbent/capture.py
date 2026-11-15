"""Record verification-time versions, the recovered launch command, and human notes.

No numerical solve is launched. Run last after documents have been finalized.
"""
import hashlib
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys
import tarfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
R2F = HERE.parent/'2026-11-15-r2f-general-init'
PYTHONPATH = '/home/mordent/.cache/uv/archive-v0/IH8olt7ky0AxR5WV:/home/mordent/.cache/uv/environments-v2/sys-id-chirp-1714f8f5f4d59f0e/lib/python3.12/site-packages'
UV_PYTHON = '/home/mordent/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/bin/python'
THREADS = 'OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1'
COMMANDS = [
    dict(step='1 reverification of the 8 new phases with the existing verifier', cwd='uav',
        command=f'{THREADS} PYTHONPATH={PYTHONPATH} {UV_PYTHON} experiments/2026-11-15-r2g-incumbent/reverify.py',
        outputs=['reverification.json', 'reverification/']),
    dict(step='1b retention rule re-run on saved states into a temporary folder', cwd='uav',
        command=f'{THREADS} PYTHONPATH={PYTHONPATH} TMPDIR=<scratchpad> UAV_R2_CASE=fig1 {UV_PYTHON} experiments/2026-11-15-r2g-incumbent/recheck_retention.py',
        outputs=['retention-recheck.json']),
    dict(step='2 Rust cross-check', cwd='uav',
        command='PYTHONDONTWRITEBYTECODE=1 python3 experiments/2026-11-15-r2g-incumbent/audit_outputs.py',
        outputs=['rust-validation.log', 'output-verification.json']),
    dict(step='3 unit tests', cwd='uav', command='PYTHONDONTWRITEBYTECODE=1 python3 scripts/test_feasible_incumbent.py -v',
        outputs=['unit-test-feasible-incumbent.log']),
    dict(step='4 aggregation', cwd='uav', command='PYTHONDONTWRITEBYTECODE=1 python3 experiments/2026-11-15-r2g-incumbent/analyze.py',
        outputs=['summary.json', 'comparison.md']),
    dict(step='5 provenance', cwd='uav',
        command=f'PYTHONDONTWRITEBYTECODE=1 PYTHONPATH={PYTHONPATH} {UV_PYTHON} experiments/2026-11-15-r2g-incumbent/capture.py',
        outputs=['provenance.json', 'local-inner-manifest.json', 'artifact-index.json']),
]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args):
    return subprocess.run(['git', *args], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.strip()


def version(name):
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def main():
    prior = json.loads((R2F/'provenance.json').read_text())
    recheck = dict(source='experiments/2026-11-15-r2f-general-init/provenance.json',
        source_hashes=len(prior['source_hashes']),
        source_hashes_equal_now=sum((ROOT/path).exists() and sha(ROOT/path) == digest for path, digest in prior['source_hashes'].items()),
        source_hashes_different_now=[path for path, digest in prior['source_hashes'].items()
            if not (ROOT/path).exists() or sha(ROOT/path) != digest],
        evaluator_hashes={path: dict(recorded=digest, exists=Path(path).exists(),
            equal_now=Path(path).exists() and sha(Path(path)) == digest) for path, digest in prior['evaluator_hashes'].items()},
        solve_time_precheck=json.loads((HERE/'reuse-preflight.json').read_text()))
    files = list(HERE.glob('*.py'))
    files += [ROOT/'scripts'/name for name in ['feasible_incumbent.py', 'test_feasible_incumbent.py', 'repair_initialization.py',
        'test_repair_initialization.py', 'diagnose_solution.py', 'carrier_certificate.py', 'verify_solutions.py']]
    files += [R2F/name for name in ['helpers.py', 'phase.py', 'guard.py', 'initialize.py', 'verify_init.py', 'summary.json']]
    files += [HERE.parent/'2026-11-15-r2c-direct-final'/name for name in ['run.py', 'verify.py', 'helpers.py']]
    files += [HERE.parent/'2026-11-15-r2-cases'/name for name in ['restore.py', 'helpers.py']]
    files += [HERE.parent/'2026-11-14-restoration/fixed_branch.py']
    reused = {}
    for folder in sorted((HERE/'regression').iterdir()):
        result = json.loads((folder/'result.json').read_text())
        source, init = ROOT/result['solver_source'], ROOT/result['initialization_source']
        paths = sorted(source.glob('*.json'))+sorted((source/'restored').glob('*.json'))+sorted(init.glob('*.json'))
        reused[folder.name] = dict(solver_source=result['solver_source'], initialization_source=result['initialization_source'],
            files={str(path.relative_to(ROOT)): sha(path) for path in paths},
            git_status=git('status', '--porcelain', '--', result['solver_source'], result['initialization_source']))
    status = git('status', '--short')
    launch = json.loads((HERE/'launch-record.json').read_text())
    notes = sorted((ROOT.parent/'human').glob('*.md'))
    with tarfile.open(HERE/'human-notes.tar.gz', 'w:gz') as archive:
        for path in notes:
            archive.add(path, arcname='human/'+path.name)
    provenance = dict(
        date_of_solve='2026-11-15', date_of_this_verification='2026-11-16',
        base_commit='d56963d', plan_commit='a044da9', implementation_commit='aec1831', screened_targets_commit='30d3095',
        recorded_head=git('rev-parse', 'HEAD'),
        tracked_files_modified_at_capture=[line for line in status.splitlines() if not line.startswith('??')],
        solve_time_environment=dict(recorded_in_experiment_files_at_execution=False,
            launch_recovered_from_conversation=launch,
            version_strings_at_execution_saved=False,
            note='The actual command and executable path were recovered from the conversation on 2026-11-16; package/version strings below are verification-time measurements',
            known_from_saved_files=dict(workers=json.loads((HERE/'execution.json').read_text())['workers'],
                blas_threads=json.loads((HERE/'execution.json').read_text())['blas_threads'],
                affinity_cpus=json.loads((HERE/'execution.json').read_text())['affinity_cpus'],
                dependency_precheck='reuse-preflight.json: 314 source hashes and 2 evaluator hashes equal to the R2f provenance at solve time')),
        verification_time_environment=dict(python=sys.version, executable=sys.executable,
            packages={name: version(name) for name in ['numpy', 'scipy', 'casadi', 'matplotlib']},
            system_python3=subprocess.run(['python3', '--version'], text=True, stdout=subprocess.PIPE).stdout.strip(),
            rustc=subprocess.run(['rustc', '--version'], text=True, stdout=subprocess.PIPE).stdout.strip(),
            note='reverify.py, recheck_retention.py and capture.py ran with `executable`; audit_outputs.py, analyze.py and the unit tests with system python3'),
        verification_commands=COMMANDS,
        dependencies_recheck_at_verification=recheck,
        source_hashes={str(path.relative_to(ROOT)): sha(path) for path in sorted(set(files))},
        reused_regression_sources=reused,
        solves_launched_by_verification=False, main_source_changed=False, monte_carlo_rerun=False, paper_reproduction=False,
        human_notes_archive='human-notes.tar.gz', human_notes={path.name: sha(path) for path in notes})
    (HERE/'provenance.json').write_text(json.dumps(provenance, indent=2)+'\n')
    local = sorted((HERE/'cases').glob('*/*/stages/*/inner*.jsonl.gz'))
    ignored = git('ls-files', '--others', '--ignored', '--exclude-standard', '--', str(HERE.relative_to(ROOT))).splitlines()
    ignored = [path for path in ignored if '__pycache__' not in path]
    (HERE/'local-inner-manifest.json').write_text(json.dumps(dict(git_tracked=False,
        excluded_by='experiments/2026-11-15-r2g-incumbent/.gitignore: /cases/*/*/stages/*/inner*.jsonl.gz',
        count=len(local), bytes=sum(path.stat().st_size for path in local),
        git_ignored_files_in_folder=len(ignored),
        git_ignored_equals_this_list=sorted(ignored) == sorted(str(path.relative_to(ROOT)) for path in local),
        logs={str(path.relative_to(HERE)): dict(bytes=path.stat().st_size, sha256=sha(path)) for path in local}), indent=2)+'\n')
    tracked = set(git('ls-files', '--', str(HERE.relative_to(ROOT))).splitlines())
    paths = [path for path in sorted(HERE.rglob('*')) if path.is_file() and path not in local
        and path.name != 'artifact-index.json' and '__pycache__' not in path.parts]
    (HERE/'artifact-index.json').write_text(json.dumps({str(path.relative_to(HERE)):
        dict(bytes=path.stat().st_size, sha256=sha(path), tracked_at_capture=str(path.relative_to(ROOT)) in tracked)
        for path in paths}, indent=2)+'\n')
    print(json.dumps(dict(head=provenance['recorded_head'], packages=provenance['verification_time_environment']['packages'],
        rustc=provenance['verification_time_environment']['rustc'],
        r2f_source_hashes_equal_now=f"{recheck['source_hashes_equal_now']}/{recheck['source_hashes']}",
        evaluators_equal_now=sum(e['equal_now'] for e in recheck['evaluator_hashes'].values()),
        inner_logs=len(local), ignored_equals_inner_logs=sorted(ignored) == sorted(str(path.relative_to(ROOT)) for path in local),
        indexed_files=len(paths), tracked_modified=provenance['tracked_files_modified_at_capture'])))


if __name__ == '__main__':
    main()
