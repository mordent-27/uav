"""Save immutable batch provenance, documentation snapshots, and hashes without solving."""
import hashlib
import importlib.metadata
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import driver

BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[1]
OUT=BASE/'batches'/os.environ.get('UAV_R3_BATCH','000')


def read(path):return json.loads(path.read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,data):path.write_text(json.dumps(data,indent=2)+'\n')
def git(*args):return subprocess.run(['git',*args],cwd=ROOT,text=True,stdout=subprocess.PIPE,check=True).stdout.strip()


def main():
    with driver.protocol_lock():
        assert not (OUT/'artifact-index.json').exists(),'batch provenance already finalized'
        protocol=read(BASE/'protocol.json')
        assert driver.dependencies()==protocol['dependencies']
        assert not git('diff','7f83545','--','src')
        attempts=[read(p) for p in sorted(OUT.glob('attempt*.json'))]
        assert attempts and all(a['status']=='complete' for a in attempts)
        cases=list(dict.fromkeys(n for a in attempts for n in a['cases']))
        notes=sorted((ROOT.parent/'human').glob('*.md'))
        with tarfile.open(OUT/'human-notes.tar.gz','w:gz') as archive:
            for path in notes:archive.add(path,arcname='human/'+path.name)
        for name in ['ROADMAP.md','README.md','WORK_LOG.md']:
            (OUT/(name.lower().replace('.md','')+'-snapshot.md')).write_bytes((ROOT/name).read_bytes())
        (OUT/'cohort-progress.json').write_bytes((BASE/'summary.json').read_bytes())
        libraries=protocol['dependencies']['evaluator_hashes']
        runtime=BASE/'runtime-evaluators.tar.gz'
        if not runtime.exists():
            with tarfile.open(runtime,'w:gz') as archive:
                for name in libraries:archive.add(name,arcname=Path(name).name)
        with tarfile.open(runtime) as archive:
            for name,digest in libraries.items():
                assert hashlib.sha256(archive.extractfile(Path(name).name).read()).hexdigest()==digest
        evidence={}
        for case in cases:
            raw=read(BASE/'runs'/case/'result.json')
            if raw['error'] is None:
                assert not raw['g_reused'] and not raw['fallback_cache_used']
                (ROOT/raw['g_source']).relative_to(BASE)
                for key in ['solver_source','initialization_source']:
                    if raw['outcome'][key]:(ROOT/raw['outcome'][key]).relative_to(BASE)
            evidence[case]=dict(error=raw['error'],g_reused=raw.get('g_reused'),
                fallback_cache_used=raw.get('fallback_cache_used'),
                launch_records={str(p.relative_to(BASE)):sha(p) for p in sorted((BASE/'logs'/case).glob('*-launch.json'))})
        sources=[ROOT/p for p in protocol['dependencies']['source_hashes']]+list(BASE.glob('*.py'))
        sources.append(BASE.parent/'2026-11-16-r2i-fresh-entry/analyze.py')
        write(OUT/'provenance.json',dict(date='2026-11-16',recorded_head=git('rev-parse','HEAD'),
            protocol_targets_commit='d134003',protocol_sha256=sha(BASE/'protocol.json'),
            targets_sha256=sha(BASE/'targets.json'),fixed_numerical_sources_equal=58,
            launch=read(OUT/'launch-record.json'),attempts=attempts,
            source_hashes={str(p.relative_to(ROOT)):sha(p) for p in sorted(set(sources))},
            evaluator_hashes=libraries,runtime_archive=str(runtime.relative_to(BASE)),runtime_archive_sha256=sha(runtime),
            fresh_run_evidence=evidence,cache_reuse=False,solves_launched_by_verification=False,main_Rust_changed=False,
            verification_environment=dict(executable=sys.executable,python=sys.version,
                packages={p:importlib.metadata.version(p) for p in ['numpy','scipy','casadi']},
                rustc=subprocess.run(['rustc','--version'],text=True,stdout=subprocess.PIPE,check=True).stdout.strip()),
            verification_commands=[
                'same numeric Python/environment as launch-record.json, UAV_R3_BATCH=000: reverify.py',
                'PYTHONDONTWRITEBYTECODE=1 python3 experiments/2026-11-16-r3s-cohort/aggregate.py',
                'PYTHONDONTWRITEBYTECODE=1 UAV_R3_BATCH=000 python3 experiments/2026-11-16-r3s-cohort/audit_outputs.py',
                'same numeric Python/environment as launch-record.json, UAV_R3_BATCH=000: capture.py'],
            human_notes={p.name:sha(p) for p in notes},human_notes_archive='human-notes.tar.gz',
            population_distribution_complete=read(BASE/'summary.json')['final_distribution_complete'],paper_reproduction=False))
        numeric_folders=[BASE/sub/case for sub in ['inputs','initializations','cases/G','cases/fallback','evaluations/G','evaluations/fallback','runs','logs'] for case in cases]
        numeric_paths={p for folder in numeric_folders for p in folder.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
        local=sorted(p for p in numeric_paths if p.name.startswith('inner') and p.name.endswith('.jsonl.gz'))
        write(OUT/'local-inner-manifest.json',dict(git_tracked=False,count=len(local),bytes=sum(p.stat().st_size for p in local),
            logs={str(p.relative_to(BASE)):dict(bytes=p.stat().st_size,sha256=sha(p)) for p in local}))
        common=[p for p in BASE.iterdir() if p.is_file() and p.name!='driver.lock' and p.name!='summary.json' and p.name!='comparison.md' and p.name!='REPORT.md' and not p.name.startswith('batch')]
        files=numeric_paths-set(local)
        files.update(common)
        files.update(p for p in OUT.rglob('*') if p.is_file() and p.name!='artifact-index.json')
        log=BASE/f'batch{OUT.name}.log'
        if log.exists():files.add(log)
        write(OUT/'artifact-index.json',{str(p.relative_to(BASE)):dict(bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(files)})
        print(json.dumps(dict(batch=OUT.name,indexed=len(files),local_inner=len(local),cases=len(cases),human_notes=len(notes))))


if __name__=='__main__':main()
