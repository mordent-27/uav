"""Additional saved-point analysis of the accurate-inner R stage-2 endpoint."""
import json
import numpy as np
import run as r


def main():
    folder = r.HERE/'cases/R-expanded'
    data = json.loads((folder/'stage02-end.json').read_text())
    model = r.Variant('R')
    model.stage(data['eps'], data['p'])
    y, lam, mu = (np.array(data[k]) for k in ['y', 'lam', 'mu'])
    q, le, mi = model.reference_state(y, lam, mu)
    ref = model.reference
    ref.eval(q, le, mi, 0.)
    jac = ref.jacobian(q)
    order = np.argsort(np.r_[abs(ref.h), np.maximum(0., ref.g)])[::-1][:8]
    rows = []
    for i in order:
        if i < 36:
            kind, index = 'battery', int(i)
        elif i < 43:
            kind, index = 'task', int(i-36)
        elif i < 79:
            kind, index = 'mode', int(i-43)
        else:
            n = int(i-79)
            kind, index = ['speed', 'energy_min', 'energy_max', 'time_min', 'time_max', 'charge_min'][n//36], n%36
        value = float(ref.h[i]) if i < 79 else float(ref.g[i-79])
        rows.append(dict(row=int(i), kind=kind, index=index, common_residual=value,
                         reference_jacobian_norm=float(np.linalg.norm(jac[i]))))
    r.tr.write(r.HERE/'stage2-rows.json', dict(case='R-expanded', stage=2,
        additional_saved_point_analysis=True, rows=rows))
    model.close()


if __name__ == '__main__':
    main()
