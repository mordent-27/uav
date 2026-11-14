"""Run deterministic witnesses and certify the frozen PI polished cohort; no solves."""

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def save(name, value):
    (HERE/name).write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def finalize(d, label):
    tr, p = d['solution'], d['phys']
    d.pop('station_revisit', None)  # Recompute carrier results; do not retain old fixture metadata.
    tr['c'] = [s if mode>=0 else 0. for s,mode in zip(tr['s'],d['modes'])]
    tr['e'] = diag.replay(d)
    d['init'] = copy.deepcopy(tr)
    d['stages'] = []
    d['diagnostic'] = dict(kind=label, globally_optimal=False)
    d['metrics'] = dict(objective=sum(tr['s']), init_objective=sum(tr['s']),
                        converged=False, seconds=0., stamps=len(tr['r']), **diag.residuals(d))
    assert d['metrics']['viol'] < 1e-12
    assert min(tr['e']) >= p['e_min'] and max(tr['e']) <= p['e_max']
    return d


if __name__ == '__main__':
    diag = module('diagnose', ROOT/'scripts/diagnose_solution.py')
    carrier = module('carrier', ROOT/'scripts/carrier_certificate.py')
    audit = module('audit', ROOT/'experiments/2026-11-14-validation/audit.py')
    provenance = dict(head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                      sources={str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest()
                               for path in sorted((ROOT/'src').glob('*.rs'))},
                      validation_sources={str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest()
                          for path in [ROOT/'scripts/carrier_certificate.py',
                                       ROOT/'scripts/diagnose_solution.py', ROOT/'scripts/verify_solutions.py',
                                       ROOT/'experiments/2026-11-14-validation/audit.py',
                                       HERE/'validate_carrier.py', HERE/'test_carrier.py']},
                      scope='deterministic witnesses and existing PI polished outputs; no optimization')
    save('provenance.json', provenance)
    simple = json.loads((ROOT/'experiments/2026-11-14-question2/station-counterexample.json').read_text())
    simple = finalize(simple, 'original short carrier counterexample')
    repaired = copy.deepcopy(simple)
    repaired['solution']['s'][1] = 2/repaired['phys']['v_c']
    repaired = finalize(repaired, 'minimal time extension with all route endpoints and charge durations fixed')
    strong = copy.deepcopy(simple)
    strong['instance'] = dict(r0=[-11.,0.], rf=[11.,0.],
                             regions=[dict(o=[0.,0.],rho=6.)], tasks=[[-5.,0.],[5.,0.]])
    strong['solution'] = dict(r=[[-11.,0.],[-5.,0.],[-5.,0.],[5.,0.],[5.,0.],[11.,0.]],
                              s=[600/3600,300/3600,1000/3600,600/3600,600/3600])
    strong['modes'], strong['task_stamp'] = [-1,0,-1,0,-1], [1,3]
    strong = finalize(strong, 'both charges necessary on fixed route; delay alone cannot repair')
    strong_repaired = copy.deepcopy(strong)
    strong_repaired['solution']['s'][2] = 10/strong_repaired['phys']['v_c']
    strong_repaired['modes'][2] = 0
    strong_repaired = finalize(strong_repaired, 'ride and charge during the middle transfer; feasible witness only')
    examples = []
    for name, d in [('simple',simple),('simple-repaired',repaired),('essential-charges',strong),
                    ('essential-charges-repaired',strong_repaired)]:
        save(name+'.json', d)
        result = carrier.certify(d)
        if result['feasible']:
            result['independent_check'] = carrier.check_constructed(d, result)
        save(name+'-carrier.json', result)
        examples.append(dict(case=name, seconds=sum(d['solution']['s'])*3600,
                             energy=d['solution']['e'], original_violation=d['metrics']['viol'],
                             carrier_feasible=result['feasible']))
    p = strong['phys']
    required = 10/p['v_c']
    energy_upper = (p['e_max']-p['e_min'])/p['zeta']
    delayed = copy.deepcopy(strong)
    delayed['solution']['s'][2] = required
    delayed_e = diag.replay(delayed)
    bounds = dict(gap_distance_km=10., original_gap_seconds=1000.,
                  carrier_required_seconds=required*3600,
                  maximum_uncharged_gap_seconds=energy_upper*3600,
                  cannot_repair_by_delay_even_from_full=required > energy_upper,
                  delayed_arrival_energy=delayed_e[3],
                  remove_first_charge_energy_before_second=1-p['zeta']*16/p['v_d'],
                  remove_second_charge_best_energy_at_destination=1-p['zeta']*16/p['v_d'])
    assert bounds['cannot_repair_by_delay_even_from_full']
    assert bounds['delayed_arrival_energy'] < 0
    assert bounds['remove_first_charge_energy_before_second'] < 0
    assert bounds['remove_second_charge_best_energy_at_destination'] < 0

    cohort = []
    frozen = ROOT/'experiments/2026-11-14-approximation/combined/mode_scaled'
    for path in sorted(frozen.glob('*/polished.json')):
        d = json.loads(path.read_text())
        result = carrier.certify(d)
        old = audit.inspect(d)
        if result['feasible']:
            result['independent_check'] = carrier.check_constructed(d,result)
        failures = [failure for item in result['carriers'] for failure in item['failures']]
        assert old['original_pass'] and old['exact_mode_battery_pass']
        (HERE/'certificates').mkdir(exist_ok=True)
        save('certificates/'+path.parent.name+'.json', result)
        cohort.append(dict(case=path.parent.name, source=str(path.relative_to(ROOT)),
                           source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                           original_violation=d['metrics']['viol'],
                           carrier_feasible=result['feasible'],
                           previous_1m_audit_pass=old['one_station_pass'],
                           max_excess_km=max([0.]+[v['excess_km'] for v in failures])))
    assert len(cohort) == 13
    summary = dict(examples=examples, delay_limitation=bounds, cohort=cohort,
                   cohort_count=len(cohort), carrier_certified=sum(v['carrier_feasible'] for v in cohort),
                   tolerance_disagreements=sum(v['carrier_feasible']!=v['previous_1m_audit_pass'] for v in cohort))
    save('results.json', summary)
    print(json.dumps(summary,indent=2))
