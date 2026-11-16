"""Record frozen-code equality, fresh-run evidence, output hashes, and finalized human notes."""
import hashlib
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys
import tarfile

BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[1]
R2H=BASE.parent/'2026-11-16-r2h-g-first'


def read(path):return json.loads(path.read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,data):path.write_text(json.dumps(data,indent=2)+'\n')
def git(*args):return subprocess.run(['git',*args],cwd=ROOT,text=True,stdout=subprocess.PIPE,check=True).stdout.strip()


def main():
    expected=read(BASE/'preflight.json')['dependencies']
    sources={p:sha(ROOT/p) for p in expected['source_hashes']}
    evaluators={p:sha(Path(p)) for p in expected['evaluator_hashes']}
    assert sources==expected['source_hashes'] and evaluators==expected['evaluator_hashes']
    assert not git('diff','b068733','--','src')
    files=list(BASE.glob('*.py'))+[ROOT/p for p in sources]
    notes=sorted((ROOT.parent/'human').glob('*.md'))
    with tarfile.open(BASE/'human-notes.tar.gz','w:gz') as archive:
        for p in notes:archive.add(p,arcname='human/'+p.name)
    evidence={}
    for case in read(BASE/'targets.json')['cases']:
        result=read(BASE/'runs'/case/'result.json')
        evidence[case]=dict(error=result['error'],g_reused=result.get('g_reused'),
            fallback_cache_used=result.get('fallback_cache_used'),
            launch_records={str(p.relative_to(BASE)):sha(p) for p in sorted((BASE/'logs'/case).glob('*-launch.json'))})
        if result['error'] is None:
            assert not result['g_reused'] and not result['fallback_cache_used']
            (ROOT/result['g_source']).relative_to(BASE)
            outcome=result['outcome']
            for key in ['solver_source','initialization_source']:
                if outcome[key] is not None:(ROOT/outcome[key]).relative_to(BASE)
    write(BASE/'provenance.json',dict(date='2026-11-16',recorded_head=git('rev-parse','HEAD'),
        plan_commit='54decfe',launch=read(BASE/'launch-record.json'),execution=read(BASE/'execution.json'),
        fixed_numerical_sources_equal=len(sources),evaluator_hashes=evaluators,
        source_hashes={str(p.relative_to(ROOT)):sha(p) for p in sorted(set(files))},
        fresh_run_evidence=evidence,baseline_provenance_sha256=sha(R2H/'provenance.json'),
        verification_environment=dict(python=sys.version,executable=sys.executable,
            packages={p:importlib.metadata.version(p) for p in ['numpy','scipy','casadi']},
            rustc=subprocess.run(['rustc','--version'],text=True,stdout=subprocess.PIPE,check=True).stdout.strip()),
        verification_commands=[
            'same numeric environment and Python as launch-record.json: reverify.py, without UAV_R2_CASE',
            'PYTHONDONTWRITEBYTECODE=1 python3 experiments/2026-11-16-r2i-fresh-entry/analyze.py',
            'PYTHONDONTWRITEBYTECODE=1 python3 experiments/2026-11-16-r2i-fresh-entry/audit_outputs.py',
            'same numeric environment and Python as launch-record.json: capture.py, stdout returned directly'],
        human_notes={p.name:sha(p) for p in notes},human_notes_archive='human-notes.tar.gz',
        solves_launched_by_verification=False,main_source_changed=False,cached_solves=0,
        paper_reproduction=False,monte_carlo_rerun=False,population_success_rate_precision_claimed=False))
    local=sorted(BASE.glob('cases/*/*/stages/*/inner*.jsonl.gz'))
    ignored=[p for p in git('ls-files','--others','--ignored','--exclude-standard','--',str(BASE.relative_to(ROOT))).splitlines() if '__pycache__' not in p]
    assert sorted(ignored)==sorted(str(p.relative_to(ROOT)) for p in local)
    write(BASE/'local-inner-manifest.json',dict(git_tracked=False,count=len(local),
        bytes=sum(p.stat().st_size for p in local),ignored_files_equal_manifest=True,
        logs={str(p.relative_to(BASE)):dict(bytes=p.stat().st_size,sha256=sha(p)) for p in local}))
    paths=[p for p in sorted(BASE.rglob('*')) if p.is_file() and p not in local and p.name!='artifact-index.json' and '__pycache__' not in p.parts]
    write(BASE/'artifact-index.json',{str(p.relative_to(BASE)):dict(bytes=p.stat().st_size,sha256=sha(p)) for p in paths})
    print(json.dumps(dict(indexed=len(paths),local_inner=len(local),fixed_numerical_sources_equal=len(sources),
        fresh_case_records=len(evidence),human_notes=len(notes))))


if __name__=='__main__':main()
