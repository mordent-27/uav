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
    assert sha(ROOT/targets['full_precision_tasks'])==targets['full_precision_tasks_sha256']
    for r in targets['contexts']:
        assert sha(ROOT/r['samples'])==r['samples_sha256']
        assert sha(ROOT/r['result'])==r['result_sha256']
        assert sha(ROOT/r['metadata_source'])==r['metadata_sha256']
        assert sha(ROOT/r['precise_inner_gradient_check'])==r['precise_inner_gradient_check_sha256']
    for name,digest in targets['reused_modules'].items():assert sha(ROOT/name)==digest
    shared=read(ROOT/'experiments/2026-11-16-r3a-cohort/protocol.json')['dependencies']
    for name,digest in shared['source_hashes'].items():assert sha(ROOT/name)==digest
    for name,digest in shared['evaluator_hashes'].items():assert sha(Path(name))==digest
    old_indices=[ROOT/'experiments/2026-11-16-r3a-cohort/batches'/n/'artifact-index.json' for n in ['000','001','002']]
    old_indices += [ROOT/'experiments'/n/'artifact-index.json' for n in ['2026-11-16-nlp-bound-push','2026-11-16-init-retry','2026-11-16-hvp','2026-11-16-hvp-high-rho','2026-11-16-dense-cg','2026-11-16-tr-boundary-fix','2026-11-16-tr-acceptance','2026-11-16-directional-precision','2026-11-16-component-reference','2026-11-16-full-reference','2026-11-16-precise-inner']]
    preservation={}
    for p in old_indices:
        origin=p.parent
        if 'batches' in p.parts:origin=origin.parents[1]
        index=read(p);assert all(sha(origin/k)==v['sha256'] for k,v in index.items())
        preservation[str(p.relative_to(ROOT))]=dict(files=len(index),all_unchanged=True,index_sha256=sha(p))
    notes=sorted((ROOT.parent/'human').glob('*.md'))
    with tarfile.open(BASE/'human-notes.tar.gz','w:gz') as archive:
        for p in notes:archive.add(p,arcname='human/'+p.name)
    for name in ['ROADMAP.md','README.md','WORK_LOG.md','TESTING.md']:
        (BASE/(name.lower().replace('.md','')+'-snapshot.md')).write_bytes((ROOT/name).read_bytes())
    paths=[ROOT/p for p in shared['source_hashes']]+list(BASE.glob('*.py'))+list(BASE.glob('*.rs'))
    paths += [ROOT/'scripts/tr_acceptance.py',ROOT/'scripts/test_tr_acceptance.py',ROOT/'scripts/trust_region.py',ROOT/'scripts/test_trust_region.py',ROOT/'experiments/2026-11-14-conditioning/newton_al.py',ROOT/'experiments/2026-11-15-stage4-inner/decomposition.py',ROOT/'experiments/2026-11-15-decomposed-follow/newton.py']+[ROOT/n for n in targets['reused_modules']]
    write(BASE/'provenance.json',dict(date='2026-11-16',recorded_head=subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,text=True,stdout=subprocess.PIPE,check=True).stdout.strip(),
        launch=read(BASE/'launch-record.json'),execution=read(BASE/'execution.json'),targets=targets,
        source_hashes={str(p.relative_to(ROOT)):sha(p) for p in sorted(set(paths))},evaluator_hashes=shared['evaluator_hashes'],
        python=sys.version,executable=sys.executable,packages={p:importlib.metadata.version(p) for p in ['numpy','scipy','casadi']},
        verification='10 unit tests passed before measurement; gradients at x0/x1/x3/x1r/x3r recomputed at 100 digits/1e-24 in separate processes (max difference from 80 digits 2.3e-26); all 12 direction curvatures reproduced exactly; floors, rounded points and verdicts reproduced; inputs and state outputs unchanged. posthoc.py is a post-hoc diagnostic not in PLAN.md',
        previous_artifacts=preservation,human_notes={p.name:sha(p) for p in notes},
        optimizer_launched=False,fixed_states=2,directions_per_state=6,newton_steps=3,decimal_precisions=[80,100],outer_solver_launched=False,posthoc_planned=False,monte_carlo_results_changed=False,paper_reproduction=False))
    files=[p for p in sorted(BASE.rglob('*')) if p.is_file() and p.name!='artifact-index.json' and '__pycache__' not in p.parts]
    write(BASE/'artifact-index.json',{str(p.relative_to(BASE)):dict(bytes=p.stat().st_size,sha256=sha(p)) for p in files})
    print(json.dumps(dict(indexed=len(files),states=2,directions=12,newton_points=8,previous_experiments_unchanged=len(preservation))))


if __name__=='__main__':main()
