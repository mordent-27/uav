"""usage: python restore_evaluators.py [protocol.json] [runtime-evaluators.tar.gz]
Place missing evaluator libraries from the archive after checking the protocol hashes. A present file with a different hash is an error, never overwritten."""
import hashlib
import json
from pathlib import Path
import sys
import tarfile

HERE=Path(__file__).resolve().parent


def sha(data):return hashlib.sha256(data).hexdigest()


def restore(protocol,archive):
    want=json.loads(Path(protocol).read_text())['dependencies']['evaluator_hashes'];done=[]
    for path,digest in want.items():
        p=Path(path)
        if p.exists():
            if sha(p.read_bytes())!=digest:raise SystemExit(f'{p} exists with a different sha256; refusing to overwrite')
            continue
        with tarfile.open(archive) as t:data=t.extractfile(p.name).read()
        if sha(data)!=digest:raise SystemExit(f'archive copy of {p.name} does not match the protocol hash')
        p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data);p.chmod(0o755);done.append(str(p))
    return done


if __name__=='__main__':
    args=sys.argv[1:]
    done=restore(args[0] if args else HERE/'protocol.json',args[1] if len(args)>1 else HERE/'runtime-evaluators.tar.gz')
    print(json.dumps(dict(restored=done)))
