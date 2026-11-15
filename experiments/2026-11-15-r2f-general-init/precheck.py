"""Check cached baseline inputs and unchanged numerical dependencies before solving."""
import hashlib
import json
from pathlib import Path
import numpy as np
import helpers as h


def main():
    prior=json.loads((h.R2E/'provenance.json').read_text())
    sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
    for path,expected in prior['source_hashes'].items():assert sha(h.ROOT/path)==expected,path
    for path,expected in prior['evaluator_hashes'].items():assert sha(Path(path))==expected,path
    driver=h.load_from(h.BASE,'driver');cases=[]
    for case in driver.REGRESSION:
        tau,seed=(0,0) if case=='fig1' else (int(case[3:case.index('-')]),int(case.split('seed')[1]))
        model=h.tr.Model(tau,seed,h.fidelity.LIB['normalized']);baseline=driver.cached(case)
        if baseline:
            np.testing.assert_array_equal(model.y,json.loads((baseline/'source.json').read_text())['y'])
            assert json.loads((baseline/'steps.json').read_text())==dict(run='ok',restore='ok',verify='ok')
        model.close();cases.append(dict(case=case,baseline=None if baseline is None else str(baseline.relative_to(h.ROOT))))
    h.write(h.BASE/'reuse-preflight.json',dict(cases=cases,unchanged_source_hashes=len(prior['source_hashes']),
        evaluator_hashes_verified=2,cached_baselines=sum(row['baseline'] is not None for row in cases)))


if __name__=='__main__':main()
