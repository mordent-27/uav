import hashlib
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys
import tarfile

BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[1]


def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,data):p.write_text(json.dumps(data,indent=2)+'\n')


def main():
    assert not (BASE/'artifact-index.json').exists()
    targets=read(BASE/'targets.json')
    for r in targets['contexts']:assert sha(ROOT/r['source'])==r['sha256']
    shared=read(ROOT/'experiments/2026-11-16-r3a-cohort/protocol.json')['dependencies']
    for name,digest in shared['source_hashes'].items():assert sha(ROOT/name)==digest
    for name,digest in shared['evaluator_hashes'].items():assert sha(Path(name))==digest
    old_indices=[ROOT/'experiments/2026-11-16-r3a-cohort/batches'/n/'artifact-index.json' for n in ['000','001','002']]
    old_indices += [ROOT/'experiments'/n/'artifact-index.json' for n in ['2026-11-16-nlp-bound-push','2026-11-16-init-retry','2026-11-16-hvp','2026-11-16-hvp-high-rho']]
    preservation={}
    for p in old_indices:
        origin=p.parent
        if 'batches' in p.parts:origin=origin.parents[1]
        index=read(p);assert all(sha(origin/k)==v['sha256'] for k,v in index.items())
        preservation[str(p.relative_to(ROOT))]=dict(files=len(index),all_unchanged=True,index_sha256=sha(p))
    notes=sorted((ROOT.parent/'human').glob('*.md'))
    with tarfile.open(BASE/'human-notes.tar.gz','w:gz') as archive:
        for p in notes:archive.add(p,arcname='human/'+p.name)
    for name in ['ROADMAP.md','README.md','WORK_LOG.md']:
        (BASE/(name.lower().replace('.md','')+'-snapshot.md')).write_bytes((ROOT/name).read_bytes())
    paths=[ROOT/p for p in shared['source_hashes']]+list(BASE.glob('*.py'))
    paths += [ROOT/'experiments/2026-11-14-conditioning/newton_al.py',ROOT/'experiments/2026-11-15-stage4-inner/decomposition.py',ROOT/'experiments/2026-11-15-decomposed-follow/newton.py']
    write(BASE/'provenance.json',dict(date='2026-11-16',recorded_head=subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,text=True,stdout=subprocess.PIPE,check=True).stdout.strip(),
        launch=read(BASE/'launch-record.json'),execution=read(BASE/'execution.json'),targets=targets,
        source_hashes={str(p.relative_to(ROOT)):sha(p) for p in sorted(set(paths))},evaluator_hashes=shared['evaluator_hashes'],
        python=sys.version,executable=sys.executable,packages={p:importlib.metadata.version(p) for p in ['numpy','scipy','casadi']},
        verification='verify.py re-evaluated all 461 new input/accepted points and final gradients, shared initial matrices and both initial steps; audit_tr.py checked hard-case boundary algebra',
        previous_artifacts=preservation,human_notes={p.name:sha(p) for p in notes},
        optimizer_launched=True,frozen_inner_solves=2,outer_solver_launched=False,monte_carlo_results_changed=False,paper_reproduction=False))
    files=[p for p in sorted(BASE.rglob('*')) if p.is_file() and p.name!='artifact-index.json' and '__pycache__' not in p.parts]
    write(BASE/'artifact-index.json',{str(p.relative_to(BASE)):dict(bytes=p.stat().st_size,sha256=sha(p)) for p in files})
    print(json.dumps(dict(indexed=len(files),states=2,new_inner_solves=2,previous_experiments_unchanged=len(preservation))))


if __name__=='__main__':main()
