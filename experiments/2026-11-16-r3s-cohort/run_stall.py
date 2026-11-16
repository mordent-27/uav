"""Copy of 2026-11-15-r2b-coarse/run.py with the stage-13 outer-stall stop rule (stall-e2e PLAN.md). Nothing else changed."""
import gzip
import json
from time import monotonic

import numpy as np
import helpers as h
newton = h.load("newton")  # the previous Newton file, unchanged
import importlib.util as _u
from pathlib import Path as _P
_spec = _u.spec_from_file_location('outer_stall_rule', _P(__file__).resolve().parent.parent/'2026-11-16-outer-stall'/'stall.py')
stall = _u.module_from_spec(_spec); _spec.loader.exec_module(stall)
STALL_K, STALL_DELTA = 20, 0.1


def main():
    assert (h.HERE/'preflight.json').exists()
    assert not (h.HERE/'stages').exists(), 'refuse to overwrite a run'
    source = json.loads(h.SOURCE.read_text())
    h.write(h.HERE/'initial.json', source)
    y = np.array(source['y'])
    summaries, total_outer, start, stop = [], 0, monotonic(), 'stage_limit'
    final = None
    for stage in range(1, 14):
        folder = h.HERE/'stages'/f'stage{stage:02d}'
        folder.mkdir(parents=True, exist_ok=False)
        lam, mu = np.zeros(len(source['lam'])), np.zeros(len(source['mu']))
        rho, previous = 1e4, np.inf
        initial = h.state(y, lam, mu, rho, stage)
        f = h.stage4.Frozen(initial)
        f.m.current_stage = stage
        h.write(folder/'initial.json', dict(**initial, **h.assess(f, y, lam, mu)))
        f.close()
        stage_start, records = monotonic(), []
        deadline = min(start+960, stage_start+120)
        stop = 'outer_limit'
        with gzip.open(folder/'outer.jsonl.gz', 'wt') as log:
            for outer in range(h.outer_cap(stage)):
                if monotonic() >= deadline:
                    stop = 'timeout'
                    break
                context = h.state(y, lam, mu, rho, stage)
                f = h.stage4.Frozen(context)
                f.m.current_stage = stage
                with gzip.open(folder/f'inner{outer+1:04d}.jsonl.gz', 'wt', compresslevel=1) as inner_log:
                    inner_log.write(json.dumps(dict(kind='context', **context))+'\n')
                    def record(row):
                        inner_log.write(json.dumps(row)+'\n')
                    result = newton.solve(f, y.copy(), deadline, record)
                info = {key: val for key, val in result.items() if key not in ['y', 'gradient']}
                if result['status'] == 'timeout':
                    h.write(folder/'interrupted-inner.json', dict(context=context,
                        last_accepted_y=result['y'].tolist(), inner=info,
                        note='no multiplier update; completed outer state remains unchanged'))
                    f.close()
                    stop = 'timeout'
                    break
                y = np.ascontiguousarray(result['y'])
                value, gradient = f.eval(y)
                np.testing.assert_allclose(result['gradient'], gradient, atol=1e-12, rtol=1e-10)
                lam += rho*f.m.h
                mu = np.maximum(0., mu+rho*f.m.g)
                metrics = h.assess(f, y, lam, mu)
                common = max(metrics['common_kkt'].values()) <= h.tolerance(stage)
                physical = max(metrics['paper_units_kkt'].values()) <= 1e-6
                passed = common and (stage != 13 or physical)
                violation = max(metrics['common_kkt']['feas'], metrics['common_kkt']['comp'])
                increase = violation > h.tolerance(stage) and violation > .25*previous and result['gradient_inf'] <= 1e-6 and not passed
                next_rho = min(1e8, 10*rho) if increase else rho
                row = dict(**h.state(y, lam, mu, rho, stage), outer=outer+1, **metrics,
                    inner=info, rho_next=next_rho, violation=violation,
                    previous_violation=None if not np.isfinite(previous) else previous,
                    common_pass=common, physical_pass=physical, stage_pass=passed,
                    seconds=monotonic()-stage_start, elapsed=monotonic()-start)
                records.append(row)
                total_outer += 1
                log.write(json.dumps(row, allow_nan=False)+'\n')
                log.flush()
                h.write(folder/'checkpoint.json', row)
                if common and not (folder/'first-common-kkt.json').exists():
                    h.write(folder/'first-common-kkt.json', row)
                if outer % 10 == 0 or passed:
                    print(json.dumps(dict(stage=stage, outer=outer+1, rho=rho,
                        inner=info['status'], gradient=info['gradient_inf'],
                        common_kkt=metrics['common_kkt'], physical_kkt=metrics['paper_units_kkt'],
                        elapsed=monotonic()-start)), flush=True)
                f.close()
                previous, rho = violation, next_rho
                if passed:
                    stop = 'kkt'
                    break
                if stage == 13 and stall.first_trigger(records, STALL_K, STALL_DELTA, h.tolerance(stage), 1e8) == len(records):
                    stop = 'stalled'
                    h.write(folder/'stall.json', dict(trigger=len(records), K=STALL_K, delta=STALL_DELTA,
                        violation=records[-1]['violation'], seconds=records[-1]['seconds']))
                    break
        context = h.state(y, lam, mu, rho, stage)
        f = h.stage4.Frozen(context)
        f.m.current_stage = stage
        metrics = h.assess(f, y, lam, mu)
        common = max(metrics['common_kkt'].values()) <= h.tolerance(stage)
        physical = max(metrics['paper_units_kkt'].values()) <= 1e-6
        passed = common and (stage != 13 or physical)
        final = dict(**context, **metrics, common_pass=common, physical_pass=physical,
            stage_pass=passed, completed_outer=len(records), seconds=monotonic()-stage_start, stop=stop)
        h.write(folder/'result.json', final)
        h.export(folder, f, final, initial, final['seconds'], final_pass=stage == 13 and common)
        summaries.append({k: final[k] for k in ['stage', 'completed_outer', 'common_kkt', 'paper_units_kkt',
            'common_pass', 'physical_pass', 'stage_pass', 'objective', 'seconds', 'stop']})
        aggregate = dict(**final, total_outer=total_outer, stages=summaries, elapsed=monotonic()-start,
            final_common_pass=bool(stage == 13 and common), final_both_scales_pass=bool(stage == 13 and common and physical),
            paper_reproduction=False, reached_final=stage == 13)
        h.write(h.HERE/'result.json', aggregate)
        h.export(h.HERE, f, final, source, aggregate['elapsed'], final_pass=stage == 13 and common)
        f.close()
        print(json.dumps(dict(stage_end=stage, outer=len(records), passed=passed, stop=stop,
            objective=final['objective'], elapsed=aggregate['elapsed'])), flush=True)
        if not passed and not h.advance_anyway(stage, stop):
            break


if __name__ == '__main__':
    main()
