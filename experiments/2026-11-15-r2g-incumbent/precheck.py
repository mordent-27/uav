"""Verify R2f numerical dependencies/evaluators and all cached outcomes, without solving."""
import hashlib
import json
from pathlib import Path
import helpers as h


def main():
    prior=json.loads((h.R2F/'provenance.json').read_text())
    sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
    for path,expected in prior['source_hashes'].items():assert sha(h.ROOT/path)==expected,path
    for path,expected in prior['evaluator_hashes'].items():assert sha(Path(path))==expected,path
    summary=json.loads((h.R2F/'summary.json').read_text())
    for row in summary['cases']:
        folder=h.ROOT/row['candidate']['path']
        assert json.loads((folder/'steps.json').read_text())==dict(run='ok',restore='ok',verify='ok')
    h.write(h.BASE/'reuse-preflight.json',dict(source_hashes_verified=len(prior['source_hashes']),
        evaluator_hashes_verified=2,cached_cases=len(summary['cases'])))


if __name__=='__main__':main()
