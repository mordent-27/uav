"""Freeze sources, runtime/metadata versions, cached baselines and external human notes."""
import hashlib
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys
import tarfile

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    prior=json.loads((HERE.parent/'2026-11-15-r2e-position-init/provenance.json').read_text())
    files=[ROOT/path for path in prior['source_hashes']]
    for name in ['2026-11-15-r2e-position-init','2026-11-15-r2e-feasible-start']:
        files+=sorted((HERE.parent/name).glob('*.py'))
    files += [ROOT/'scripts'/name for name in ['repair_initialization.py','test_repair_initialization.py',
        'diagnose_solution.py','carrier_certificate.py','verify_solutions.py']]
    files+=list(HERE.glob('*.py'))+[HERE/'run-source/repair_initialization.py']
    summary=json.loads((HERE/'summary.json').read_text())
    for row in summary['cases']:
        if row['baseline_reused']:
            folder=ROOT/row['baseline']['path'];files+=list(folder.glob('*.json'))
            files+=list((folder/'restored').glob('*.json'))
    notes=sorted((ROOT.parent/'human').glob('*.md'))
    with tarfile.open(HERE/'human-notes.tar.gz','w:gz') as archive:
        for path in notes:archive.add(path,arcname='human/'+path.name)
    provenance=dict(date='2026-11-15',base_commit='69b7a33',plan_commit='e5fdff3',numerical_code_commit='180e66c',
        production_metadata_commit='828369f',numerical_repair_source='run-source/repair_initialization.py',
        recorded_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        python=sys.version,executable=sys.executable,
        packages={name:importlib.metadata.version(name) for name in ['numpy','scipy','casadi','matplotlib']},
        source_hashes={str(path.relative_to(ROOT)):sha(path) for path in sorted(set(files))},
        evaluator_hashes={path:sha(Path(path)) for path in prior['evaluator_hashes']},
        execution=summary['execution'],main_source_changed=False,monte_carlo_rerun=False,paper_reproduction=False,
        human_notes={path.name:sha(path) for path in notes})
    (HERE/'provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
    local=sorted((HERE/'cases').glob('*/*/stages/*/inner*.jsonl.gz'))
    (HERE/'local-inner-manifest.json').write_text(json.dumps(dict(git_tracked=False,count=len(local),
        bytes=sum(path.stat().st_size for path in local),logs={str(path.relative_to(HERE)):
            dict(bytes=path.stat().st_size,sha256=sha(path)) for path in local}),indent=2)+'\n')
    paths=[path for path in sorted(HERE.rglob('*')) if path.is_file() and path not in local
        and path.name!='artifact-index.json' and '__pycache__' not in path.parts]
    (HERE/'artifact-index.json').write_text(json.dumps({str(path.relative_to(HERE)):
        dict(bytes=path.stat().st_size,sha256=sha(path)) for path in paths},indent=2)+'\n')


if __name__=='__main__':main()
