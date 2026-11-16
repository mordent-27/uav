"""Archive finalized documentation and hash sources, reused files, and local inner logs."""
import hashlib
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys
import tarfile

BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[1]
R2G=BASE.parent/'2026-11-15-r2g-incumbent'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):return json.loads(path.read_text())
def write(path,data):path.write_text(json.dumps(data,indent=2)+'\n')
def git(*args):return subprocess.run(['git',*args],cwd=ROOT,text=True,stdout=subprocess.PIPE,check=True).stdout.strip()


def main():
    prior=read(R2G/'provenance.json')
    changed=[p for p,digest in prior['source_hashes'].items() if not (ROOT/p).exists() or sha(ROOT/p)!=digest]
    assert not changed,changed
    evaluators={name:sha(Path(name)) for name in prior['dependencies_recheck_at_verification']['evaluator_hashes']}
    assert all(digest==prior['dependencies_recheck_at_verification']['evaluator_hashes'][name]['recorded'] for name,digest in evaluators.items())
    source_paths=[ROOT/p for p in prior['source_hashes']]
    source_paths+=list(BASE.glob('*.py'))+[ROOT/'scripts/g_first_policy.py',ROOT/'scripts/test_g_first_policy.py']
    source_paths+=[BASE.parent/'2026-11-15-r2b-coarse'/name for name in ['case.py','run.py','verify.py','helpers.py']]
    cache={}
    for case,entry in read(BASE/'catalog.json')['cases'].items():
        folders=[ROOT/entry['canonical_input']]
        if entry['g_source']:folders.append(ROOT/entry['g_source'])
        # Preserve a reference/hash to the fallback baseline even when G prevents its evaluation.
        baseline=ROOT/entry['fallback_evaluation'];folders.append(baseline)
        old=read(baseline/'result.json')
        if old['solver_source']:folders.append(ROOT/old['solver_source'])
        folders.append(ROOT/old['initialization_source'])
        paths=set(p for folder in folders for p in folder.rglob('*') if p.is_file() and '__pycache__' not in p.parts)
        cache[case]={str(p.relative_to(ROOT)):sha(p) for p in sorted(paths)}
        assert sha(ROOT/entry['canonical_input']/'original-state.json')==entry['input_state_sha256']
        assert sha(baseline/'result.json')==entry['fallback_result_sha256']
    notes=sorted((ROOT.parent/'human').glob('*.md'))
    with tarfile.open(BASE/'human-notes.tar.gz','w:gz') as archive:
        for p in notes:archive.add(p,arcname='human/'+p.name)
    provenance=dict(date='2026-11-16',recorded_head=git('rev-parse','HEAD'),
        launch=read(BASE/'launch-record.json'),execution=read(BASE/'execution.json'),
        prior_source_hashes_equal=len(prior['source_hashes']),source_hashes_changed=changed,
        source_hashes={str(p.relative_to(ROOT)):sha(p) for p in sorted(set(source_paths))},
        evaluator_hashes=evaluators,reused_artifacts=cache,
        verification_environment=dict(executable=sys.executable,python=sys.version,
            packages={p:importlib.metadata.version(p) for p in ['numpy','scipy','casadi']},
            rustc=subprocess.run(['rustc','--version'],text=True,stdout=subprocess.PIPE,check=True).stdout.strip()),
        verification_commands=[
            'same numeric environment/executable as launch-record.json: reverify.py (no UAV_R2_CASE)',
            'PYTHONDONTWRITEBYTECODE=1 python3 experiments/2026-11-16-r2h-g-first/audit_outputs.py',
            "PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s scripts -p 'test_*policy.py' -v",
            'PYTHONDONTWRITEBYTECODE=1 python3 experiments/2026-11-16-r2h-g-first/analyze.py',
            'same numeric environment/executable as launch-record.json: capture.py'],
        solves_launched_by_verification=False,main_source_changed=False,paper_reproduction=False,
        monte_carlo_rerun=False,independent_success_rate_estimated=False,
        human_notes_archive='human-notes.tar.gz',human_notes={p.name:sha(p) for p in notes})
    write(BASE/'provenance.json',provenance)
    local=sorted(BASE.glob('cases/*/*/stages/*/inner*.jsonl.gz'))
    ignored=[p for p in git('ls-files','--others','--ignored','--exclude-standard','--',str(BASE.relative_to(ROOT))).splitlines() if '__pycache__' not in p]
    local_names=[str(p.relative_to(ROOT)) for p in local]
    assert sorted(ignored)==sorted(local_names),(len(ignored),len(local))
    write(BASE/'local-inner-manifest.json',dict(git_tracked=False,count=len(local),bytes=sum(p.stat().st_size for p in local),
        logs={str(p.relative_to(BASE)):dict(bytes=p.stat().st_size,sha256=sha(p)) for p in local},
        ignored_files_equal_manifest=True))
    paths=[p for p in sorted(BASE.rglob('*')) if p.is_file() and p not in local and p.name!='artifact-index.json' and '__pycache__' not in p.parts]
    write(BASE/'artifact-index.json',{str(p.relative_to(BASE)):dict(bytes=p.stat().st_size,sha256=sha(p)) for p in paths})
    print(json.dumps(dict(indexed=len(paths),local_inner=len(local),cache_cases=len(cache),
        prior_source_hashes_equal=len(prior['source_hashes']),human_notes=len(notes))))


if __name__=='__main__':main()
