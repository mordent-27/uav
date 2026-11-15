"""Verify reused sources and the evaluator before any new numerical solve."""
import hashlib
import json
import numpy as np
import helpers as h


def main():
    previous = json.loads((h.DIRECT/'provenance.json').read_text())
    sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    for relative, expected in previous['source_hashes'].items():
        assert sha(h.ROOT/relative) == expected, relative
    for name, expected in previous['evaluator_hashes'].items():
        assert sha(h.Path(name)) == expected, name
    cases = []
    for folder in sorted((h.R2B/'cases/G').iterdir()):
        name = folder.name
        tau, seed = (0, 0) if name == 'fig1' else (int(name[3:name.index('-')]), int(name.split('seed')[1]))
        model = h.tr.Model(tau, seed, h.fidelity.LIB['normalized'])
        source = json.loads((folder/'source.json').read_text())
        np.testing.assert_array_equal(model.y, source['y'])
        model.close()
        assert json.loads((folder/'verification.json').read_text())['original_jacobian_stationarity_verified']
        direct = h.DIRECT/'cases'/name
        if direct.exists():
            assert source['y'] == json.loads((direct/'source.json').read_text())['y']
            assert json.loads((direct/'steps.json').read_text()) == dict(run='ok', restore='ok', verify='ok')
        cases.append(name)
    assert len(cases) == 13
    h.write(h.BASE/'reuse-preflight.json', dict(cases=cases, initial_state_matches=True,
        previous_source_hashes_verified=len(previous['source_hashes']), evaluator_hashes_verified=2))


if __name__ == '__main__':
    main()
