"""Verify reused dependencies/evaluators and all four original input states before solving."""
import hashlib
import json
from pathlib import Path
import numpy as np
import helpers as h


def main():
    prior=json.loads((h.R2D/'provenance.json').read_text())
    sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
    for path,expected in prior['source_hashes'].items():assert sha(h.ROOT/path)==expected,path
    for path,expected in prior['evaluator_hashes'].items():assert sha(Path(path))==expected,path
    cases=[]
    for tau in [1,3,5,7]:
        name=f'tau{tau}-seed3'
        model=h.tr.Model(tau,3,h.fidelity.LIB['normalized'])
        source=json.loads((h.R2D/'cases/G'/name/'source.json').read_text())
        np.testing.assert_array_equal(model.y,source['y'])
        model.close()
        if tau in [5,7]:
            folder=h.R2D/'cases/direct'/name
            assert json.loads((folder/'steps.json').read_text())==dict(run='ok',restore='ok',verify='ok')
            assert json.loads((folder/'source.json').read_text())['y']==source['y']
        cases.append(name)
    h.write(h.BASE/'reuse-preflight.json',dict(cases=cases,initial_states_equal=True,
        source_hashes_verified=len(prior['source_hashes']),evaluator_hashes_verified=2))


if __name__=='__main__':
    main()
