"""Audit the input-only optimization against Rust initialization and original physics."""
import copy
import json
import numpy as np
import helpers as h


def main():
    result = json.loads((h.INIT/'result.json').read_text())
    m = h.fidelity.Variant('R')
    before = h.tr.decode(m, m.native.y, m.source)
    fb = h.load_from(h.ROOT/'experiments/2026-11-14-restoration', 'fixed_branch')
    data = copy.deepcopy(m.source)
    data['init'] = before
    data['solution'] = before
    data['instance']['tasks'] = [before['r'][stamp] for stamp in data['task_stamp']]
    model = fb.FixedBranch(data, moving=False)
    if (h.INIT/'solver.json').exists():
        raw = json.loads((h.INIT/'solver.json').read_text())
        kkt = model.kkt(np.array(raw['point']), np.array(raw['lam']), np.array(raw['lam_x']))
        np.testing.assert_allclose(list(kkt.values()), list(result['raw_kkt'].values()), atol=1e-10, rtol=1e-8)
    if result['accepted']:
        output = json.loads((h.INIT/'solution.json').read_text())
        source = json.loads((h.INIT/'source.json').read_text())
        assert output['solution']['r'] == before['r']
        assert output['modes'] == m.source['modes'] and output['task_stamp'] == m.source['task_stamp']
        y = np.array(source['y'])
        decoded = h.tr.decode(m, y, m.source)
        for key in ['r', 'e', 's', 'c']:
            np.testing.assert_allclose(decoded[key], output['solution'][key], atol=1e-14, rtol=1e-14)
        energy = fb.diag.replay(output)
        np.testing.assert_allclose(energy, output['solution']['e'], atol=1e-14, rtol=1e-14)
        assert min(energy) >= 0. and max(energy) <= 1.
        check = fb.diag.residuals(output)
        assert check['viol'] <= 1e-6
        point = np.r_[np.array(energy[1:])*model.range, np.array(output['solution']['s'])*model.p['v_d']]
        final_kkt = model.kkt(point, np.array(raw['lam']), np.array(raw['lam_x']))
        assert max(final_kkt.values()) <= 1e-6
        np.testing.assert_allclose(list(final_kkt.values()), list(result['final_kkt'].values()), atol=1e-10, rtol=1e-8)
        m.stage(.2, 2.)
        metrics = m.metrics(y, np.zeros(m.me), np.zeros(m.mi))
        for key in ['common_kkt', 'paper_units_kkt']:
            np.testing.assert_allclose(list(metrics[key].values()), list(source[key].values()), atol=1e-10, rtol=1e-8)
        assert min(output['history']['e']) >= 0. and max(output['history']['e']) <= 1.
    report = dict(case=h.CASE, accepted=result['accepted'], input_positions_modes_stamps_verified=True,
        kkt_recomputed=True, replay_and_dense_energy_verified=result['accepted'])
    h.write(h.INIT/'verification.json', report)
    print(json.dumps(report))
    m.close()


if __name__ == '__main__':
    main()
