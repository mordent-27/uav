"""Audit the saved 48-case manifest and final certificates without another solve."""
import json
import math
from pathlib import Path

import numpy as np

import run


def main():
    source = json.loads(run.SOURCE.read_text())
    summary = json.loads((run.HERE / 'summary.json').read_text())
    expected = {(k, j) for k, m in enumerate(source['modes']) if m >= 0
                for j in range(-1, len(source['instance']['regions'])) if j != m}
    seen = set()
    verified = []
    for result in summary['cases']:
        k, new = result['segment'], result['new_region']
        assert (k, new) in expected and (k, new) not in seen
        seen.add((k, new))
        case = run.HERE / 'cases' / result['name']
        assert json.loads((case / 'result.json').read_text()) == result
        raw = json.loads((case / 'solver.json').read_text())
        assert raw['solver_status'] == result['solver_status']
        if not result['accepted']:
            assert not (case / 'solution.json').exists()
            continue
        data = json.loads((case / 'solution.json').read_text())
        tr, p = data['solution'], data['phys']
        assert len(tr['r']) == 37 and data['instance'] == source['instance'] and p == source['phys']
        assert data['task_stamp'] == source['task_stamp']
        modes = list(source['modes'])
        modes[k] = new
        assert data['modes'] == modes
        assert tr['r'][0] == data['instance']['r0'] and tr['r'][-1] == data['instance']['rf']
        for task, stamp in zip(data['instance']['tasks'], source['task_stamp']):
            assert tr['r'][stamp] == task
        for i, mode in enumerate(modes):
            assert tr['c'][i] == (tr['s'][i] if mode >= 0 else 0.)
            assert p['s_min'] <= tr['s'][i] <= p['s_max']
            speed = p['v_c'] if mode >= 0 else p['v_d']
            assert math.dist(tr['r'][i], tr['r'][i + 1]) <= speed * tr['s'][i] + 1e-10
            if mode >= 0:
                region = data['instance']['regions'][mode]
                assert all(math.dist(tr['r'][ii], region['o']) <= region['rho'] + 1e-10 for ii in (i, i + 1))
        residual = run.fb.diag.residuals(data)
        assert residual['viol'] < 1e-10
        replay = run.fb.diag.replay(data)
        assert max(abs(a - b) for a, b in zip(replay, tr['e'])) < 1e-14
        run.fb.build_history(data)
        assert min(data['history']['e']) >= p['e_min'] and max(data['history']['e']) <= p['e_max']
        assert abs(sum(tr['s']) - result['objective']) < 1e-13
        assert abs(data['metrics']['objective'] - result['objective']) < 1e-13
        assert not data['metrics']['converged'] and not data['diagnostic']['paper_algorithm']
        model = run.fb.FixedBranch(data, moving=True)
        raw_kkt = model.kkt(np.array(raw['point']), np.array(raw['lam']), np.array(raw['lam_x']))
        final_point = np.r_[np.array(tr['r'])[model.free].ravel(),
                            np.array(tr['e'][1:]) * model.range, np.array(tr['s']) * p['v_d']]
        final_kkt = model.kkt(final_point, np.array(raw['lam']), np.array(raw['lam_x']))
        for actual, saved in [(raw_kkt, result['raw_kkt']), (final_kkt, result['final_kkt'])]:
            assert all(v <= 1e-6 for v in actual.values())
            assert max(abs(actual[key] - saved[key]) for key in actual) < 1e-12
        verified.append(dict(name=result['name'], original_violation=residual['viol'], final_kkt=final_kkt))
    assert seen == expected and len(seen) == 48
    assert len(verified) == summary['accepted'] == 37
    best = min((r for r in summary['cases'] if r['accepted']), key=lambda r: r['objective'])
    assert best == summary['best']
    published = json.loads((run.HERE / 'best.json').read_text())
    stored = json.loads((run.HERE / 'cases' / best['name'] / 'solution.json').read_text())
    assert published['solution'] == stored['solution'] and published['modes'] == stored['modes']
    run.write(run.HERE / 'verification.json', dict(complete_manifest=True, accepted=len(verified),
        best=best['name'], strict_original_checks=True, certificates=verified))
    print(f'48 prescribed cases accounted for; {len(verified)} final certificates verified; best {best["name"]}')


if __name__ == '__main__':
    main()
