"""Before any solve: the case-switching model reproduces R1 on Figure 1. Run with UAV_R2_CASE=fig1."""
import gzip
import json
from time import monotonic

import numpy as np
import helpers as h


def main():
    assert h.CASE == 'fig1' and not (h.BASE/'preflight.json').exists()
    newton = h.load('newton')
    source = json.loads((h.R1/'source.json').read_text())
    m = h.fidelity.Variant('R')
    assert type(m).__name__ == 'CaseVariant'
    np.testing.assert_array_equal(m.native.y, np.array(source['y']))
    m.close()
    with gzip.open(h.R1/'stages/stage01/outer.jsonl.gz', 'rt') as stream:
        row = json.loads(stream.readline())
    y = np.array(source['y'])
    context = h.state(y, np.zeros(len(source['lam'])), np.zeros(len(source['mu'])), 1e4, 1)
    f = h.stage4.Frozen(context)
    assert type(f.m).__name__ == 'CaseVariant'
    f.m.current_stage = 1
    step = newton.solve(f, y.copy(), monotonic()+120)
    point = np.ascontiguousarray(step['y'])
    f.eval(point)
    lam, mu = 1e4*f.m.h, np.maximum(0., 1e4*f.m.g)
    np.testing.assert_allclose(point, row['y'], atol=1e-12, rtol=1e-12)
    np.testing.assert_allclose(lam, row['lam'], atol=1e-10, rtol=1e-10)
    np.testing.assert_allclose(mu, row['mu'], atol=1e-10, rtol=1e-10)
    assert step['status'] == row['inner']['status'] and step['accepted'] == row['inner']['accepted']
    measured = f.m.metrics(point, lam, mu)
    for key in ['common_kkt', 'paper_units_kkt']:
        np.testing.assert_allclose(list(measured[key].values()), list(row[key].values()), atol=1e-10, rtol=1e-8)
    f.close()
    h.write(h.BASE/'preflight.json', dict(model='CaseVariant', figure1_start_identical_to_R1=True,
        figure1_first_outer_of_stage1_identical_to_R1=True, inner_status=step['status'],
        inner_accepted=step['accepted'], common_kkt=measured['common_kkt']))
    print(json.dumps(dict(preflight=True, inner_status=step['status'], accepted=step['accepted'])), flush=True)


if __name__ == '__main__':
    main()
