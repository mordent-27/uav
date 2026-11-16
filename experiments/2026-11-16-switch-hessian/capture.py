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
    P=targets['fix'];r=P['context']
    assert sha(ROOT/r['samples'])==r['samples_sha256'] and sha(ROOT/r['result'])==r['result_sha256'] and sha(ROOT/r['metadata_source'])==r['metadata_sha256']
    for key in ['previous_side_result','previous_side_arrays']:assert sha(ROOT/P[key])==P[key+'_sha256']
    for r in targets['switch']['states']:assert sha(ROOT/r['checkpoint'])==r['checkpoint_sha256'] and sha(ROOT/r['result'])==r['result_sha256']
    for name,digest in targets['reused_modules'].items():assert sha(ROOT/name)==digest
    shared=read(ROOT/'experiments/2026-11-16-r3a-cohort/protocol.json')['dependencies']
    for name,digest in shared['source_hashes'].items():assert sha(ROOT/name)==digest
    for name,digest in shared['evaluator_hashes'].items():assert sha(Path(name))==digest
    old_indices=[ROOT/'experiments/2026-11-16-r3a-cohort/batches'/n/'artifact-index.json' for n in ['000','001','002']]
    old_indices += [ROOT/'experiments'/n/'artifact-index.json' for n in ['2026-11-16-nlp-bound-push','2026-11-16-init-retry','2026-11-16-hvp','2026-11-16-hvp-high-rho','2026-11-16-dense-cg','2026-11-16-tr-boundary-fix','2026-11-16-tr-acceptance','2026-11-16-directional-precision','2026-11-16-component-reference','2026-11-16-full-reference','2026-11-16-precise-inner','2026-11-16-curvature-rounding','2026-11-16-kink-sides']]
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
        verification='5 unit tests passed before measurement; straddling set and both rebuilt columns reproduced bit for bit in a separate process; x0/x*/rounded/lattice gradients recomputed at 100 digits/1e-24 with zero difference; verdict reproduced; 24 straddling counts identical; inputs and outputs unchanged',
        previous_artifacts=preservation,human_notes={p.name:sha(p) for p in notes},
        optimizer_launched=False,fixed_states=1,switch_states=24,newton_steps=5,decimal_precisions=[80,100],outer_solver_launched=False,monte_carlo_results_changed=False,paper_reproduction=False))
    files=[p for p in sorted(BASE.rglob('*')) if p.is_file() and p.name!='artifact-index.json' and '__pycache__' not in p.parts]
    write(BASE/'artifact-index.json',{str(p.relative_to(BASE)):dict(bytes=p.stat().st_size,sha256=sha(p)) for p in files})
    print(json.dumps(dict(indexed=len(files),switch_states=24,previous_experiments_unchanged=len(preservation))))


if __name__=='__main__':main()
