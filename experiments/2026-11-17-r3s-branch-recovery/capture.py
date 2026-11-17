"""Snapshot the repository notes and human notes after the documents are final, then index all artifacts (as gradient-e2e/capture.py)."""
import hashlib
import json
from pathlib import Path
import shutil
import tarfile

BASE=Path(__file__).resolve().parent;ROOT=BASE.parents[1]


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_text(json.dumps(v,indent=2)+'\n')


def main():
    assert json.loads((BASE/'verification.json').read_text())['passed'] and not (BASE/'artifact-index.json').exists()
    human=ROOT.parent/'human';names=['report.md','reproduction.md','question2_notes.md','validation_plan.md','critical_review.md','carrier_model.md']
    with tarfile.open(BASE/'human-notes.tar.gz','w:gz') as archive:
        for name in names:archive.add(human/name,arcname='human/'+name)
    write(BASE/'human-source-index.json',{name:sha(human/name) for name in names})
    notes=BASE/'repo-notes';notes.mkdir(exist_ok=False)
    for name in ['README.md','ROADMAP.md','WORK_LOG.md','TESTING.md']:shutil.copyfile(ROOT/name,notes/name)
    index={str(p.relative_to(BASE)):sha(p) for p in sorted(BASE.rglob('*')) if p.is_file() and p.name!='artifact-index.json' and '__pycache__' not in p.parts}
    write(BASE/'artifact-index.json',index);print(json.dumps(dict(artifacts=len(index))))


if __name__=='__main__':main()
