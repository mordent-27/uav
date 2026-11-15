"""Count actual PHR active-set changes in the finite-difference samples."""
import json
import numpy as np
import support as s


def main():
    assert not (s.HERE/'switches.json').exists()
    checks = []
    for name, state in json.loads((s.HERE/'inputs.json').read_text()).items():
        frozen = s.Frozen(state)
        samples = []
        for step in [1e-6, 1e-7, 1e-8, 1e-9, 1e-10, 1e-11, 1e-12]:
            changed_rows = np.zeros(frozen.m.mi, dtype=bool)
            changed_columns = []
            for j in range(len(frozen.anchor)):
                a, b = frozen.anchor.copy(), frozen.anchor.copy()
                a[j] += step
                b[j] -= step
                frozen.eval(a)
                active_a = frozen.mu+frozen.rho*frozen.m.g > 0
                frozen.eval(b)
                active_b = frozen.mu+frozen.rho*frozen.m.g > 0
                changed = active_a != active_b
                changed_rows |= changed
                if any(changed):
                    changed_columns.append(j)
            samples.append(dict(step=step, crossing_columns=changed_columns,
                crossing_constraints=np.flatnonzero(changed_rows).tolist()))
        frozen.close()
        checks.append(dict(problem=name, samples=samples))
    s.write(s.HERE/'switches.json', checks)
    print(json.dumps([{r['problem']: [(v['step'], len(v['crossing_columns']), len(v['crossing_constraints'])) for v in r['samples']]} for r in checks]))


if __name__ == '__main__':
    main()
