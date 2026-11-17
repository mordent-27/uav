import gzip
import hashlib
import json
from pathlib import Path

BASE=Path(__file__).resolve().parent;ROOT=BASE.parents[1]
PRIOR=ROOT/'experiments/2026-11-17-r3s-stage01'


def main():
    assert not (BASE/'source-index.json').exists()
    sources={}
    def consume(p):
        data=p.read_bytes();sources[str(p.relative_to(ROOT))]=hashlib.sha256(data).hexdigest();return data
    selections=json.loads(consume(PRIOR/'representative-selection.json'))
    previous=json.loads(consume(PRIOR/'representative-source-index.json'))
    protocol=json.loads(consume(ROOT/'experiments/2026-11-16-r3s-cohort/protocol.json'))
    for name,digest in protocol['dependencies']['source_hashes'].items():
        assert hashlib.sha256(consume(ROOT/name)).hexdigest()==digest,name
    # Import-chain modules not individually listed by the earlier cohort protocol.
    for name in ['experiments/2026-11-15-stage4-inner/support.py',
                 'experiments/2026-11-15-stage4-inner/curvature.py',
                 'experiments/2026-11-15-stage2/common.py',
                 'experiments/2026-11-14-conditioning/newton_al.py',
                 'experiments/2026-11-14-reproduction/independent_al.py']:
        consume(ROOT/name)
    states=[]
    for case in dict.fromkeys(r['case'] for r in selections):
        chosen=[r for r in selections if r['case']==case][-1]
        data=consume(ROOT/chosen['saved']);assert hashlib.sha256(data).hexdigest()==previous[chosen['saved']]
        rows=[json.loads(line) for line in gzip.decompress(data).splitlines()]
        assert rows[0]['kind']=='context' and rows[1]['kind']=='input' and rows[2]['kind']=='accepted'
        states.append(dict(case=case,source=chosen['saved'],context=rows[0],input=rows[1],first_accepted=rows[2]))
    libraries={}
    for name,digest in protocol['dependencies']['evaluator_hashes'].items():
        assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==digest,name
        libraries[name]=digest
    for name,value in [('source-index.json',sources),('states.json',states),('library-index.json',libraries)]:
        (BASE/name).write_text(json.dumps(value,indent=2)+'\n')
    print(json.dumps(dict(sources=len(sources),states=len(states),libraries=len(libraries))))


if __name__=='__main__':main()
