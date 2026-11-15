"""Prespecified 2 x 2 x 2 stage-3 controls; refuse to overwrite outputs."""
import gzip
import json
from pathlib import Path
import sys
from time import monotonic

import numpy as np

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent/'2026-11-15-stage2'
sys.path.insert(0, str(PRIOR))
import continue_al as helpers

c = helpers.c
SOURCE = PRIOR/'follow-guarded/stage03-start.json'
write = c.write


def penalty(rho, violation, previous, passed, inner_gradient, gate):
    eligible = violation > 1e-6 and (not gate or inner_gradient <= 1e-6)
    increase = eligible and not passed and violation > .25*previous
    return min(1e8, 10*rho) if increase else rho


def solve(folder, y, lam, mu, rho, stage, gate, deadline, limit, name, metadata=None):
    folder.mkdir(parents=True, exist_ok=False)
    m = c.fidelity.Variant('R')
    eps, p = max(.0005, .2*.6**(stage-1)), min(12., 2.*1.2**(stage-1))
    m.stage(eps, p)
    m.current_stage = stage
    write(folder/'initial.json', dict(**c.state(y, lam, mu, rho, stage, eps, p),
        gate=gate, **(metadata or {})))
    start, records, previous, stop = monotonic(), [], np.inf, 'outer_limit'
    with gzip.open(folder/'outer.jsonl.gz', 'wt') as log:
        for outer in range(limit):
            if monotonic() >= deadline:
                stop = 'timeout'
                break
            point, info = helpers.inner(m, y, lam, mu, rho, 'bfgs', deadline)
            if info['interrupted']:
                write(folder/'interrupted-inner.json', dict(y=point.tolist(), **info))
                stop = 'timeout'
                break
            y = point
            m.eval(y, lam, mu, 0.)
            lam += rho*m.h
            mu = np.maximum(0., mu+rho*m.g)
            metrics = c.assess(m, y, lam, mu)
            passed = max(metrics['common_kkt'].values()) <= 1e-6
            violation = max(metrics['common_kkt']['feas'], metrics['common_kkt']['comp'])
            next_rho = penalty(rho, violation, previous, passed, info['gradient_inf'], gate)
            row = dict(**c.state(y, lam, mu, rho, stage, eps, p), outer=outer+1,
                **metrics, inner=info, rho_next=next_rho, violation=violation,
                previous_violation=None if not np.isfinite(previous) else previous,
                gate=gate, elapsed=monotonic()-start)
            records.append(row)
            log.write(json.dumps(row, allow_nan=False)+'\n')
            log.flush()
            write(folder/'checkpoint.json', row)
            if outer % 50 == 0:
                print(json.dumps(dict(name=name, stage=stage, outer=outer+1, rho=rho,
                    rho_next=next_rho, inner_gradient=info['gradient_inf'],
                    common_kkt=metrics['common_kkt'], elapsed=monotonic()-start)), flush=True)
            previous, rho = violation, next_rho
            if passed:
                stop = 'kkt'
                break
    result = helpers.export(folder, m, y, lam, mu, rho, records, stop,
        monotonic()-start, name, final_required=True)
    m.close()
    return result


def main():
    assert not (HERE/'cases').exists(), 'refuse to overwrite experiment'
    source = json.loads(SOURCE.read_text())
    results = []
    for dual_reset in [False, True]:
        for rho_reset in [False, True]:
            for gate in [False, True]:
                name = ('dual-reset' if dual_reset else 'dual-carry')+'_'+('rho-reset' if rho_reset else 'rho-carry')+'_'+('gated' if gate else 'plain')
                y, lam, mu = (np.array(source[k]) for k in ['y', 'lam', 'mu'])
                if dual_reset:
                    lam.fill(0.)
                    mu.fill(0.)
                rho = 1e4 if rho_reset else source['rho']
                results.append(solve(HERE/'cases'/name, y, lam, mu, rho, 3, gate,
                    monotonic()+60, 200, name, dict(dual_reset=dual_reset,
                        rho_reset=rho_reset, source=str(SOURCE.relative_to(HERE.parents[1])))))
    write(HERE/'matrix.json', results)
    selected = next(r for r in results if r['name'] == 'dual-reset_rho-reset_gated')
    if not selected['target_kkt_pass']:
        write(HERE/'follow-skipped.json', dict(reason='prespecified reset/reset/gated stage 3 did not pass KKT'))
        return
    parent, stages, deadline = selected, [], monotonic()+300
    for stage in range(4, 14):
        y = np.array(parent['y'])
        lam, mu = np.zeros(len(parent['lam'])), np.zeros(len(parent['mu']))
        result = solve(HERE/'follow'/f'stage{stage:02d}', y, lam, mu, 1e4,
            stage, True, deadline, 600 if stage == 13 else 200,
            f'follow-stage{stage:02d}', dict(parent=parent['name'], dual_reset=True, rho_reset=True))
        stages.append(result)
        write(HERE/'follow.json', stages)
        if not result['target_kkt_pass']:
            break
        parent = result


if __name__ == '__main__':
    main()
