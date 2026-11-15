"""Read the first direct AL trajectory and score its branch switch; no new solve."""
import gzip
import json
import numpy as np
import helpers as h


def main():
    assert h.PHASE == 'direct' and h.CASE == 'tau7-seed3'
    folder = h.HERE/'stages/stage13'
    with gzip.open(folder/'inner0001.jsonl.gz', 'rt') as handle:
        log = [json.loads(line) for line in handle]
    context = log[0]
    m = h.fidelity.Variant('R')
    m.stage(context['eps'], context['p'])
    lam, mu = np.array(context['lam']), np.array(context['mu'])
    assert not any(lam) and not any(mu)
    ns, segment = m.stamps-1, 19
    nr = 2*(m.stamps-2)
    rows = []
    for entry in log[1:]:
        y = np.array(entry['y'])
        value, gradient = m.eval(y, lam, mu, context['rho'])
        hh, gg = m.h.copy(), m.g.copy()
        trajectory = h.tr.decode(m, y, m.source)
        selection = h.tr.describe(m, y, m.source, context['eps'], context['p'])
        mode = selection['modes'][segment]
        objective = sum(trajectory['s'])
        penalty = .5*context['rho']*(hh@hh+np.maximum(gg,0)@np.maximum(gg,0))
        np.testing.assert_allclose(value, objective+penalty, atol=1e-10, rtol=1e-10)
        rows.append(dict(iteration=entry.get('iteration',0), al_value=value, objective=objective,
            penalty=penalty, winner=mode['winner'], c_over_s=mode['c_over_s'],
            battery_bound_penalty=float(.5*context['rho']*np.sum(np.maximum(gg[ns:3*ns],0)**2)),
            c=mode['c'], s=mode['s'], derivative_share=mode['derivative_share'],
            native_gradient_c=float(gradient[nr+2*ns+segment]),
            initial_region=0, mode_residual=mode['phi']-context['eps']))
    first = next(i for i,r in enumerate(rows) if r['winner'] == -1)
    assert rows[0]['winner'] == 0
    report = dict(case=h.CASE, stage=13, outer=1, rho=context['rho'], segment=segment,
        initial_original_audit=json.loads(h.SOURCE.read_text())['selection']['audit'],
        initial=rows[0], before_switch=rows[first-1], first_flight_winner=rows[first], final=rows[-1],
        accepted_inner_points=len(rows)-1, rows=rows,
        caveat='AL descent at finite rho can enter an infeasible fixed branch; this is not proof that another rho or solver repairs it')
    h.write(h.BASE/'switch-trace.json', report)
    print(json.dumps({k:v for k,v in report.items() if k not in ['rows','caveat']}))
    m.close()


if __name__ == '__main__':
    main()
