"""Frozen stage-4 AL functions and stable differences; model/gradients unchanged."""
import gzip
import json
from pathlib import Path
import sys

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PRIOR = HERE.parent/'2026-11-15-stage3/follow/stage04'
sys.path.insert(0, str(HERE.parent/'2026-11-15-stage2'))
import common as old

write = old.write


def source_rows():
    with gzip.open(PRIOR/'outer.jsonl.gz', 'rt') as stream:
        return [json.loads(line) for line in stream]


def inputs():
    rows = source_rows()
    out = {}
    for name, row, dual, rho in [('before-raise', rows[14], rows[14], 1e6),
                                ('after-raise', rows[14], rows[14], 1e7),
                                ('stalled', rows[199], rows[198], 1e7)]:
        out[name] = dict(y=row['y'], lam=dual['lam'], mu=dual['mu'], rho=rho,
            eps=row['eps'], p=row['p'], stage=4, source_outer=row['outer'],
            dual_outer=dual['outer'])
    return out


class Frozen:
    def __init__(self, state):
        self.state = state
        self.m = old.fidelity.Variant('R')
        self.m.stage(state['eps'], state['p'])
        self.m.current_stage = 4
        self.anchor, self.lam, self.mu = (np.array(state[k]) for k in ['y', 'lam', 'mu'])
        self.rho = state['rho']
        self.value0, _ = self.m.eval(self.anchor, self.lam, self.mu, self.rho)
        self.h0, self.g0 = self.m.h.copy(), self.m.g.copy()
        _, self.gf = self.m.eval(self.anchor, np.zeros(self.m.me), np.zeros(self.m.mi), 0.)

    def eval(self, point, stable=False):
        point = np.ascontiguousarray(point)
        value, gradient = self.m.eval(point, self.lam, self.mu, self.rho)
        if not stable:
            return value, gradient
        # Difference of the same mathematical AL, with no subtraction of its
        # O(1) constant or two nearly equal squared penalty terms.
        ld = np.longdouble
        h, g, h0, g0 = (np.asarray(a, dtype=ld) for a in [self.m.h, self.m.g, self.h0, self.g0])
        lam, mu, rho = np.asarray(self.lam, dtype=ld), np.asarray(self.mu, dtype=ld), ld(self.rho)
        result = np.sum(np.asarray(self.gf, dtype=ld)*(np.asarray(point, dtype=ld)-self.anchor), dtype=ld)
        result += np.sum((h-h0)*(lam+rho*(h+h0)/2), dtype=ld)
        w, w0 = mu+rho*g, mu+rho*g0
        both = (w > 0) & (w0 > 0)
        result += np.sum((g[both]-g0[both])*(mu[both]+rho*(g[both]+g0[both])/2), dtype=ld)
        different = ~both
        result += np.sum((np.maximum(0, w[different])**2-np.maximum(0, w0[different])**2)/(2*rho), dtype=ld)
        return float(result), gradient

    def close(self):
        self.m.close()


def preflight():
    assert not (HERE/'preflight.json').exists(), 'refuse to overwrite preflight'
    states, rows = inputs(), source_rows()
    assert all(states['before-raise'][key] == states['after-raise'][key] for key in ['y', 'lam', 'mu', 'eps', 'p'])
    reconstructions = []
    for index in [14, 199]:
        row, before = rows[index], rows[index-1]
        f = Frozen(dict(row, lam=before['lam'], mu=before['mu']))
        value, gradient = f.eval(np.array(row['y']))
        np.testing.assert_allclose(value, row['inner']['value'], atol=1e-12, rtol=1e-12)
        np.testing.assert_allclose(max(abs(gradient)), row['inner']['gradient_inf'], atol=1e-11, rtol=1e-8)
        np.testing.assert_allclose(row['lam'], f.lam+f.rho*f.m.h, atol=1e-11, rtol=1e-11)
        np.testing.assert_allclose(row['mu'], np.maximum(0., f.mu+f.rho*f.m.g), atol=1e-11, rtol=1e-11)
        reconstructions.append(dict(outer=row['outer'], value=value, gradient_inf=float(max(abs(gradient)))))
        f.close()
    checks = []
    direction = np.sin(np.arange(len(states['stalled']['y']))+1.)
    direction /= np.linalg.norm(direction)
    for name, state in states.items():
        f = Frozen(state)
        samples = []
        for distance in [0., 1e-3, -1e-3, 1e-5, -1e-5]:
            y = f.anchor+distance*direction
            ordinary, ga = f.eval(y)
            centered, gb = f.eval(y, stable=True)
            assert np.array_equal(ga, gb)
            np.testing.assert_allclose(ordinary, f.value0+centered, atol=1e-11, rtol=1e-12)
            samples.append(dict(distance=distance, ordinary=ordinary, centered=centered,
                constant_error=ordinary-f.value0-centered))
        y, step = f.anchor+1e-3*direction, 1e-7
        plus, _ = f.eval(y+step*direction, stable=True)
        minus, _ = f.eval(y-step*direction, stable=True)
        _, gradient = f.eval(y)
        fd, analytic = (plus-minus)/(2*step), float(gradient@direction)
        np.testing.assert_allclose(fd, analytic, atol=2e-5, rtol=2e-5)
        checks.append(dict(name=name, samples=samples, direction_fd=fd, direction_gradient=analytic))
        f.close()
    write(HERE/'inputs.json', states)
    write(HERE/'preflight.json', dict(reconstructions=reconstructions, same_primal_dual_pair=True,
        stable_gradient_identical=True, checks=checks, longdouble_epsilon=float(np.finfo(np.longdouble).eps)))
    print(json.dumps(dict(preflight=True, reconstructions=reconstructions)))


if __name__ == '__main__':
    preflight()
