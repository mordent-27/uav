"""Freeze both experiments, including the failed attempt, dependencies and external notes."""
import hashlib
import importlib.metadata
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
FOLLOW=HERE.parent/'2026-11-15-r2e-feasible-start'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    prior=json.loads((HERE.parent/'2026-11-15-r2d-fallback/provenance.json').read_text())
    sources=[ROOT/name for name in prior['source_hashes']]
    sources+=sorted((HERE.parent/'2026-11-15-r2d-fallback').glob('*.py'))
    sources+=sorted(HERE.glob('*.py'))+sorted(FOLLOW.glob('*.py'))
    for case in ['tau5-seed3','tau7-seed3']:
        folder=HERE.parent/'2026-11-15-r2d-fallback/cases/direct'/case
        sources+=list(folder.glob('*.json'))
        sources+=list((folder/'restored').glob('*.json'))
    notes=sorted((ROOT.parent/'human').glob('*.md'))
    with tarfile.open(HERE/'human-notes.tar.gz','w:gz') as archive:
        for path in notes:archive.add(path,arcname='human/'+path.name)
    shutil.copyfile(HERE/'human-notes.tar.gz',FOLLOW/'human-notes.tar.gz')
    source_hashes={str(path.relative_to(ROOT)):sha(path) for path in sorted(set(sources))}
    for folder,plan,runner in [(HERE,'5553c4d','11e2c32'),(FOLLOW,'b3cd205','8950dd5')]:
        provenance=dict(date='2026-11-15',base_commit='1a15844',plan_commit=plan,runner_commit=runner,
            phase1_result_commit='1e1c6b1',recorded_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
            python=sys.version,executable=sys.executable,
            packages={name:importlib.metadata.version(name) for name in ['numpy','scipy','casadi','matplotlib']},
            source_hashes=source_hashes,evaluator_hashes={path:sha(Path(path)) for path in prior['evaluator_hashes']},
            execution=json.loads((folder/'execution.json').read_text()),
            main_source_changed=False,monte_carlo_rerun=False,paper_reproduction=False,
            human_notes={path.name:sha(path) for path in notes})
        (folder/'provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
        local=sorted((folder/'cases').glob('*/*/stages/*/inner*.jsonl.gz'))
        manifest={str(path.relative_to(folder)):dict(bytes=path.stat().st_size,sha256=sha(path)) for path in local}
        (folder/'local-inner-manifest.json').write_text(json.dumps(dict(git_tracked=False,logs=manifest,
            count=len(local),bytes=sum(path.stat().st_size for path in local)),indent=2)+'\n')
        paths=[path for path in sorted(folder.rglob('*')) if path.is_file() and path not in local
               and path.name!='artifact-index.json' and '__pycache__' not in path.parts]
        (folder/'artifact-index.json').write_text(json.dumps({str(path.relative_to(folder)):
            dict(bytes=path.stat().st_size,sha256=sha(path)) for path in paths},indent=2)+'\n')


if __name__=='__main__':main()
