import hashlib
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys
import tarfile

BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[1]


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):return json.loads(path.read_text())
def write(path,data):path.write_text(json.dumps(data,indent=2)+'\n')


def main():
    assert not (BASE/'artifact-index.json').exists()
    targets=read(BASE/'targets.json');old={}
    for case,entry in targets['cases'].items():
        for name,digest in entry['hashes'].items():assert sha(ROOT/name)==digest
        old[case]=entry['hashes']
    notes=sorted((ROOT.parent/'human').glob('*.md'))
    with tarfile.open(BASE/'human-notes.tar.gz','w:gz') as archive:
        for p in notes:archive.add(p,arcname='human/'+p.name)
    for name in ['ROADMAP.md','README.md','WORK_LOG.md']:
        (BASE/(name.lower().replace('.md','')+'-snapshot.md')).write_bytes((ROOT/name).read_bytes())
    shared=read(ROOT/'experiments/2026-11-16-r3a-cohort/protocol.json')['dependencies']
    for name,digest in shared['source_hashes'].items():assert sha(ROOT/name)==digest
    for name,digest in shared['evaluator_hashes'].items():assert sha(Path(name))==digest
    paths=[ROOT/p for p in shared['source_hashes']]+list(BASE.glob('*.py'))
    write(BASE/'provenance.json',dict(date='2026-11-16',recorded_head=subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,text=True,stdout=subprocess.PIPE,check=True).stdout.strip(),
        launch=read(BASE/'launch-record.json'),execution=read(BASE/'execution.json'),
        original_inputs_unchanged=old,source_hashes={str(p.relative_to(ROOT)):sha(p) for p in sorted(set(paths))},
        evaluator_hashes=shared['evaluator_hashes'],python=sys.version,executable=sys.executable,
        packages={p:importlib.metadata.version(p) for p in ['numpy','scipy','casadi']},
        verification='verify_analyze.py recomputed all 8 points/first iterates/options/acceptance; scripts/verify_solutions.py checked all 5 accepted outputs',
        official_sources=['https://coin-or.github.io/Ipopt/OPTIONS.html#OPT_bound_push','https://web.casadi.org/api/html/d7/df0/solvers_2callback_8py-example.html'],
        human_notes={p.name:sha(p) for p in notes},monte_carlo_results_changed=False,paper_reproduction=False))
    files=[p for p in sorted(BASE.rglob('*')) if p.is_file() and p.name!='artifact-index.json' and '__pycache__' not in p.parts]
    write(BASE/'artifact-index.json',{str(p.relative_to(BASE)):dict(bytes=p.stat().st_size,sha256=sha(p)) for p in files})
    print(json.dumps(dict(indexed=len(files),cases=len(targets['cases']),human_notes=len(notes))))


if __name__=='__main__':main()
