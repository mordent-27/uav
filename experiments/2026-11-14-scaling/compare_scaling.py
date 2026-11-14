"""Stage 3: isolate mode-component scaling and full nondimensionalization.

Run from uav/: python3 experiments/2026-11-14-scaling/compare_scaling.py
Baseline is the archived capped cohort; src/ is never edited.
"""

from concurrent.futures import ThreadPoolExecutor
import difflib
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import tempfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
PREV=ROOT/'experiments/2026-11-14-validation'
spec=importlib.util.spec_from_file_location('audit',PREV/'audit.py')
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)


def dump(path,value):
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')


def replace_once(text,old,new):
    assert text.count(old)==1,old
    return text.replace(old,new,1)


def build_sources():
    cap=(PREV/'cap-comparison/cap-model.rs').read_text().split('\n#[cfg(test)] mod cap_regression')[0]+'\n'
    mode=cap
    edits=[
      ('z[0] = (c * c + sm.eps * sm.eps).sqrt();',
       'z[0] = (ph.v_d * ph.v_d * c * c + sm.eps * sm.eps).sqrt();'),
      ('((c - s) * (c - s) + p1 * p1 + p2 * p2 + p3 * p3 + sm.eps * sm.eps).sqrt();',
       '(ph.v_d * ph.v_d * (c - s) * (c - s) + p1 * p1 + p2 * p2 + p3 * p3 + sm.eps * sm.eps).sqrt();'),
      ('grad[lay.c(k)] += wt * dz[0] * c / z[0];',
       'grad[lay.c(k)] += wt * dz[0] * ph.v_d * ph.v_d * c / z[0];'),
      ('grad[lay.c(k)] += q * (c - s);',
       'grad[lay.c(k)] += q * ph.v_d * ph.v_d * (c - s);'),
      ('grad[lay.s(k)] += q * (-(c - s) - pp[j][2] * ph.v_c);',
       'grad[lay.s(k)] += q * (-ph.v_d * ph.v_d * (c - s) - pp[j][2] * ph.v_c);'),
    ]
    for old,new in edits:mode=replace_once(mode,old,new)
    (HERE/'mode-model.diff').write_text(''.join(difflib.unified_diff(cap.splitlines(True),mode.splitlines(True),fromfile='capped-model',tofile='mode-scaled-model')))
    (HERE/'mode-model.rs').write_text(mode+(HERE/'unit_tests.rs').read_text())
    (HERE/'dimensionless-model.rs').write_text(cap)
    solver=(PREV/'cap-comparison/instrumented-solver.rs').read_text()
    physical_probe='''let mut physical_probe = Traj::from_x(&x, &lay, inst, ph);
        physical_probe.s.iter_mut().for_each(|t| *t *= crate::TIME_UNIT_H);
        physical_probe.c.iter_mut().for_each(|t| *t *= crate::TIME_UNIT_H);
        let viol = evaluate(inst, &Phys::default(), &physical_probe, sm).viol;'''
    normalized_solver=replace_once(solver,
        'let viol = evaluate(inst, ph, &Traj::from_x(&x, &lay, inst, ph), sm).viol;',physical_probe)
    normalized_solver=replace_once(normalized_solver,'3600.*over, 3600.*below',
        '3600.*crate::TIME_UNIT_H*over, 3600.*crate::TIME_UNIT_H*below')
    (HERE/'dimensionless-solver.rs').write_text(normalized_solver)
    original_main=(ROOT/'src/main.rs').read_text()
    theorem='''    println!(
        "Theorem 1 deviations from 1: value {:.2e}, gradient {:.2e}",
        m.thm_value_dev, m.thm_grad_dev
    );'''
    original_main=replace_once(original_main,theorem,
        '    println!("Theorem 1 diagnostics omitted for the modified approximation");')
    for variant in ('mode_scaled','dimensionless'):
        def repl(match):
            name=match[1]
            if name=='model':path=HERE/('mode-model.rs' if variant=='mode_scaled' else 'dimensionless-model.rs')
            elif name=='solver':path=PREV/'cap-comparison/instrumented-solver.rs' if variant=='mode_scaled' else HERE/'dimensionless-solver.rs'
            else:path=ROOT/'src'/(name+'.rs')
            return '#[path = '+json.dumps(str(path))+'] mod '+name+';'
        main=re.sub(r'^mod (\w+);$',repl,original_main,flags=re.M)
        if variant=='dimensionless':
            main='const TIME_UNIT_H: f64 = 1.0 / 36.0;\n'+main
            old='    let sol = solver::solve(&inst, &ph, &o);'
            new='''    let initial = instance::initial_trajectory(&inst, &ph, &o.init);
    let mut hp = ph.clone();
    hp.v_d *= TIME_UNIT_H; hp.v_c *= TIME_UNIT_H;
    hp.kappa *= TIME_UNIT_H; hp.zeta *= TIME_UNIT_H;
    hp.s_min /= TIME_UNIT_H; hp.s_max /= TIME_UNIT_H;
    let mut hi = initial.clone();
    hi.s.iter_mut().for_each(|t| *t /= TIME_UNIT_H);
    hi.c.iter_mut().for_each(|t| *t /= TIME_UNIT_H);
    let mut sol = solver::solve_from(&inst, &hp, &o, hi);
    sol.init = initial;
    sol.traj.s.iter_mut().for_each(|t| *t *= TIME_UNIT_H);
    sol.traj.c.iter_mut().for_each(|t| *t *= TIME_UNIT_H);
    let sm = *o.hom.schedule().last().unwrap();
    sol.metrics = metrics::evaluate(&inst, &ph, &sol.traj, sm);
    sol.init_metrics = metrics::evaluate(&inst, &ph, &sol.init, sm);
    for stage in &mut sol.stages { stage.f *= TIME_UNIT_H; }
'''
            main=replace_once(main,old,new)
        (HERE/(variant+'-main.rs')).write_text(main)


def run_one(binary,variant,case):
    name=case['name'];folder=HERE/variant/name;folder.mkdir(parents=True,exist_ok=True)
    path=folder/'raw.json'
    cmd=[str(binary),'solve',*case['flags'],'--verbose','--out',str(path)]
    try:
        with (folder/'solver.log').open('w') as log:
            result=subprocess.run(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=90)
        code=result.returncode;timeout=False
    except subprocess.TimeoutExpired:code=None;timeout=True
    row=dict(name=name,variant=variant,command=cmd,returncode=code,timeout=timeout)
    if code==0 and path.exists():
        d=json.loads(path.read_text())
        # Original-constraint metrics stay in physical units; old theorem indicators
        # are unrelated to the new smoothing and must not be presented as validation.
        for k in ('thm_value_dev','thm_grad_dev'):d['metrics'].pop(k,None)
        d['experiment']=dict(variant=variant,length_ref_km=1.,time_ref_hours=1/36,
            optimizer_objective='hours' if variant=='mode_scaled' else 'dimensionless (hours*36)',
            stage_kkt_units='optimizer units; do not directly compare stationarity across objective scales')
        path.write_text(json.dumps(d,separators=(',',':'),allow_nan=False)+'\n')
        prior=json.loads((PREV/'cap-comparison/capped'/name/'raw.json').read_text())
        assert d['instance']==prior['instance']
        for key in ('r','e','s','c'):
            va=d['init'][key];vb=prior['init'][key]
            assert va==vb,(variant,name,key)
        row.update(audit=audit.inspect(d),kkt_converged=d['metrics']['converged'],
            final_stationarity=d['stages'][-1]['stat'],final_smooth_feasibility=d['stages'][-1]['feas'])
        row['stage_domain']=[dict(stage=int(a),over_seconds=float(b),below_seconds=float(c))
            for a,b,c in re.findall(r'DOMAIN stage=(\d+) over_sec=(\S+) below_sec=(\S+)',(folder/'solver.log').read_text())]
        assert len(row['stage_domain'])==13
        row['max_stage_over_seconds']=max(s['over_seconds'] for s in row['stage_domain'])
        candidate,reason=audit.diag.polish_fixed_modes(dict(d,modes=row['audit']['modes']))
        row['polish_status']=reason
        if candidate:
            (folder/'polished.json').write_text(json.dumps(candidate,separators=(',',':'),allow_nan=False)+'\n')
            row['polished_audit']=audit.inspect(candidate)
    dump(folder/'audit.json',row)
    print(variant,name,'original',row.get('audit',{}).get('original_pass'),
          'battery',row.get('audit',{}).get('exact_mode_battery_pass'),
          'station+physical',row.get('audit',{}).get('physically_usable'),flush=True)
    return row


def main():
    build_sources()
    prior=json.loads((PREV/'provenance.json').read_text())
    for name,h in prior['sources'].items():assert hashlib.sha256((ROOT/'src'/name).read_bytes()).hexdigest()==h
    conditions=json.loads((PREV/'cap-comparison/results.json').read_text())['cases']['capped']
    results={'capped':conditions}
    flags=['--edition=2021','-C','opt-level=3','-C','lto=true','-C','codegen-units=1','-C','debuginfo=1']
    dump(HERE/'provenance.json',dict(head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        sources=prior['sources'],baseline='experiments/2026-11-14-validation/cap-comparison/capped',
        cases=prior['cases'],compile_flags=flags,thresholds=audit.TOL,length_ref_km=1.,time_ref_h=1/36))
    with tempfile.TemporaryDirectory(prefix='uav-scaling-') as td:
        # The unit tests must pass before any optimization run.
        tests=Path(td)/'unit-tests'
        with (HERE/'tests.log').open('w') as log:
            subprocess.run(['rustc','--edition=2021','--test',str(HERE/'mode_scaled-main.rs'),'-o',str(tests)],check=True,stdout=log,stderr=subprocess.STDOUT)
            subprocess.run([str(tests),'--nocapture'],check=True,stdout=log,stderr=subprocess.STDOUT)
        for variant in ('mode_scaled','dimensionless'):
            binary=Path(td)/variant
            with (HERE/(variant+'-build.log')).open('w') as log:
                subprocess.run(['rustc',*flags,str(HERE/(variant+'-main.rs')),'-o',str(binary)],check=True,stdout=log,stderr=subprocess.STDOUT)
            dump(HERE/(variant+'-binary.json'),dict(sha256=hashlib.sha256(binary.read_bytes()).hexdigest()))
            with ThreadPoolExecutor(max_workers=2) as pool:
                results[variant]=list(pool.map(lambda c:run_one(binary,variant,c),prior['cases']))
    summary={}
    for variant,rows in results.items():
        done=[r for r in rows if r['returncode']==0 and 'audit' in r]
        repaired=[r['polished_audit'] for r in done if 'polished_audit' in r]
        summary[variant]=dict(total=13,completed=len(done),original_pass=sum(r['audit']['original_pass'] for r in done),
            battery_pass=sum(r['audit']['exact_mode_battery_pass'] for r in done),
            physically_usable=sum(r['audit']['physically_usable'] for r in done),
            kkt_converged=sum(r['kkt_converged'] for r in done),
            stages_over_one_second=sum(r['max_stage_over_seconds']>1 for r in done),
            polished_available=len(repaired),polished_physical=sum(a['physically_usable'] for a in repaired))
    dump(HERE/'results.json',dict(summary=summary,cases=results))
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
