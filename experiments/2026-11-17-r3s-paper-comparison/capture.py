import hashlib
import json
from pathlib import Path
import subprocess
import tarfile
from analyze import BASE,ROOT,read,write,verify_sources


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    assert not (BASE/'artifact-index.json').exists();verify_sources()
    summary=read(BASE/'summary.json');verification=read(BASE/'verification.json')
    assert verification['all_checks_passed'] and summary['cases']==900 and summary['returned']==894
    notes=sorted((ROOT.parent/'human').glob('*.md'))
    with tarfile.open(BASE/'human-notes.tar.gz','w:gz') as archive:
        for p in notes:archive.add(p,arcname='human/'+p.name)
    for name in ['README','ROADMAP','WORK_LOG','TESTING']:
        (BASE/(name.lower()+'-snapshot.md')).write_bytes((ROOT/(name+'.md')).read_bytes())
    sources=read(BASE/'source-index.json')
    write(BASE/'provenance.json',dict(date='2026-11-17',base_head='b127bee',
        recorded_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        execution=read(BASE/'execution.json'),launch=read(BASE/'launch-record.json'),
        input_manifest='source-index.json',input_manifest_sha256=sha(BASE/'source-index.json'),
        source_files_verified=len(sources),case_results=900,returned_points=894,
        previous_batch_indices_verified=sum(k.endswith('artifact-index.json') for k in sources),
        code_hashes={p.name:sha(p) for p in sorted(BASE.glob('*.py'))},
        human_notes={p.name:sha(p) for p in notes},verification=verification,
        visual_qa=dict(files=['objective-distributions.png','objective-ecdf.png'],
            checked=['labels and legends readable','all outliers retained','denominator 100 and missing cases disclosed']),
        optimizer_launched=False,original_results_changed=False,paired_with_paper=False,paper_reproduction=False))
    files=[p for p in sorted(BASE.rglob('*')) if p.is_file() and p.name!='artifact-index.json' and '__pycache__' not in p.parts]
    write(BASE/'artifact-index.json',{str(p.relative_to(BASE)):dict(bytes=p.stat().st_size,sha256=sha(p)) for p in files})
    verify_sources();print(json.dumps(dict(indexed=len(files),input_files_unchanged=len(sources),human_notes=len(notes),optimizer_launched=False)))


if __name__=='__main__':main()
