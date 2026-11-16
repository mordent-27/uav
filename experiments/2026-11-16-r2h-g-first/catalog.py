"""Fix all input/cached-route references before any new G solve."""
import hashlib
import json
from pathlib import Path
import numpy as np
import helpers as h


def read(path):return json.loads(path.read_text())


def main():
    assert not (h.OUT/'catalog.json').exists(),'refuse to replace the catalog'
    prior=read(h.R2G/'provenance.json')
    for relative,expected in prior['source_hashes'].items():
        assert hashlib.sha256((h.ROOT/relative).read_bytes()).hexdigest()==expected,relative
    recheck=prior['dependencies_recheck_at_verification']
    for name,entry in recheck['evaluator_hashes'].items():
        assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==entry['recorded'],name
    old=read(h.R2F/'summary.json');names=[r['case'] for r in old['cases']]+read(h.R2G/'screening.json')['selected']
    rows={}
    for case in names:
        fallback=h.R2G/'regression'/case
        if not fallback.exists():fallback=h.R2G/'evaluations/repaired'/case
        f=read(fallback/'result.json');init=h.ROOT/f['initialization_source']
        original=read(init/'original-state.json')
        tau,seed=(0,0) if case=='fig1' else (int(case[3:case.index('-')]),int(case.split('seed')[1]))
        model=h.tr.Model(tau,seed,h.fidelity.LIB['normalized'])
        np.testing.assert_array_equal(model.y,original['y']);model.close()
        g=next((root/case for root in [h.R2B/'cases/G',h.R2D/'cases/G'] if (root/case/'result.json').exists()),None)
        if g:
            assert read(g/'steps.json')==dict(run='ok',restore='ok',verify='ok')
            assert read(g/'source.json')['y']==original['y']
        rows[case]=dict(g_source=None if g is None else str(g.relative_to(h.ROOT)),
            fallback_evaluation=str(fallback.relative_to(h.ROOT)),canonical_input=str(init.relative_to(h.ROOT)),
            input_state_sha256=hashlib.sha256((init/'original-state.json').read_bytes()).hexdigest(),
            fallback_result_sha256=hashlib.sha256((fallback/'result.json').read_bytes()).hexdigest())
    pending=[name for name,row in rows.items() if row['g_source'] is None]
    assert len(rows)==25 and len(pending)==8
    h.write(h.OUT/'catalog.json',dict(cases=rows,new_G_cases=pending,cached_G=17,cached_fallback=25,
        dependency_hashes_verified=len(prior['source_hashes']),evaluator_hashes_verified=2))
    print(json.dumps(dict(cases=len(rows),new_G_cases=pending)),flush=True)


if __name__=='__main__':main()
