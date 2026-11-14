"""Stage 6: zero-set-preserving psi, approximate inequalities, and their combination.

Run from uav/: python3 experiments/2026-11-14-approximation/compare_approximation.py
The Stage-3 B model/initial order is the control. src/ is never edited.
"""

from concurrent.futures import ThreadPoolExecutor
import difflib
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import tempfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
SCALING=ROOT/'experiments/2026-11-14-scaling'
spec=importlib.util.spec_from_file_location('scaling',SCALING/'compare_scaling.py')
runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
audit=runner.audit


def dump(path,value):path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')


def build_sources():
    original=(SCALING/'mode-model.rs').read_text()
    main=(SCALING/'mode_scaled-main.rs').read_text()
    for variant in ('zero_psi','inequalities','combined'):
        zero=variant in ('zero_psi','combined');leq=variant in ('inequalities','combined');model=original
        if zero:
            old='''    if y <= -delta {
        (0.0, 0.0)
    } else if y <= delta {
        let t = y + delta;
        (t * t / (4.0 * delta), t / (2.0 * delta))
    } else {
        (y, 1.0)
    }'''
            new='''    if y <= 0.0 {
        (0.0, 0.0)
    } else if y <= delta {
        (y * y / (2.0 * delta), y / delta)
    } else {
        (y - delta / 2.0, 1.0)
    }'''
            model=runner.replace_once(model,old,new)
        if leq:
            edits=[
                ('2 * (self.n - 1) + self.tau','self.n - 1'),
                ('7 * (self.n - 1)','8 * (self.n - 1) + self.tau'),
                ('pub fn eq_task(&self, i: usize) -> usize {\n        self.n - 1 + i',
                 'pub fn ineq_task(&self, i: usize) -> usize {\n        7 * (self.n - 1) + i'),
                ('pub fn eq_mode(&self, k: usize) -> usize {\n        self.n - 1 + self.tau + k',
                 'pub fn ineq_mode(&self, k: usize) -> usize {\n        7 * (self.n - 1) + self.tau + k'),
                ('w.eq(lay.eq_task(i), phi - sm.eps)','w.ineq(lay.ineq_task(i), phi - sm.eps)'),
                ('w.eq(lay.eq_mode(k), phi - sm.eps)','w.ineq(lay.ineq_mode(k), phi - sm.eps)'),
            ]
            for old,new in edits:model=runner.replace_once(model,old,new)
            model=model.replace('//! Equalities:   dynamics (N-1), task visits (tau), charge/discharge mode (N-1).',
                '//! Equalities: battery dynamics only; task/mode approximations moved to inequalities.')
            model=model.replace('equals eps.', 'is at most eps.')
        (HERE/(variant+'.diff')).write_text(''.join(difflib.unified_diff(original.splitlines(True),model.splitlines(True),fromfile='stage3-B-model',tofile=variant,n=0)))
        model+='\n#[cfg(test)] const ZERO_SET_PRESERVED: bool = '+str(zero).lower()+';\n'
        model+='#[cfg(test)] const APPROX_INEQUALITIES: bool = '+str(leq).lower()+';\n'
        (HERE/(variant+'-model.rs')).write_text(model+(HERE/'approximation_tests.rs').read_text())
        old='#[path = '+json.dumps(str(SCALING/'mode-model.rs'))+'] mod model;'
        new='#[path = '+json.dumps(str(HERE/(variant+'-model.rs')))+'] mod model;'
        (HERE/(variant+'-main.rs')).write_text(runner.replace_once(main,old,new))


def augment(row,variant):
    folder=HERE/variant/'mode_scaled'/row['name']
    if row['returncode']==0 and 'audit' in row:
        p=folder/'raw.json';d=json.loads(p.read_text());d['experiment']['approximation']=variant
        p.write_text(json.dumps(d,separators=(',',':'),allow_nan=False)+'\n')
        row['approximation']=variant
        row['outer_total']=sum(s['outer'] for s in d['stages'])
        row['inner_total']=sum(s['inner'] for s in d['stages'])
        assert row['outer_total']<=150 and row['inner_total']<=300000
    dump(folder/'audit.json',row)
    return row


def theoretical_bounds():
    eps,p,delta=0.0005,12.,0.001
    task=eps*math.sqrt(37**(2/p)-1)
    mode=eps*math.sqrt(5**(2/p)-1)
    # Invert the zero-set-preserving scalar hinge on its positive branch.
    region=math.sqrt(2*delta*mode) if mode<=delta/2 else mode+delta/2
    return dict(assumption='Exact satisfaction of phi<=eps, N<=37, J=4; not a certificate for a nonconverged solve.',
                eps=eps,p=p,delta=delta,task_distance_m=1000*task,
                best_mode_time_seconds=3600*mode/36,region_violation_m=1000*region)


def main():
    build_sources()
    prior=json.loads((SCALING/'provenance.json').read_text())
    for name,h in prior['sources'].items():assert hashlib.sha256((ROOT/'src'/name).read_bytes()).hexdigest()==h
    baseline=json.loads((SCALING/'results.json').read_text())['cases']['mode_scaled']
    results={'baseline':baseline};flags=prior['compile_flags']
    dump(HERE/'provenance.json',dict(head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        sources=prior['sources'],baseline='experiments/2026-11-14-scaling/mode_scaled',
        model_sha256=hashlib.sha256((SCALING/'mode-model.rs').read_bytes()).hexdigest(),
        cases=prior['cases'],compile_flags=flags,thresholds=audit.TOL,timeout=90,max_workers=2))
    dump(HERE/'theoretical-bounds.json',theoretical_bounds())
    with tempfile.TemporaryDirectory(prefix='uav-approximation-') as td:
        binaries={}
        # Test all three formulations before running any optimization cases.
        for variant in ('zero_psi','inequalities','combined'):
            tests=Path(td)/(variant+'-tests');main_rs=HERE/(variant+'-main.rs')
            with (HERE/(variant+'-tests.log')).open('w') as log:
                subprocess.run(['rustc','--edition=2021','--test',str(main_rs),'-o',str(tests)],stdout=log,stderr=subprocess.STDOUT,check=True)
                subprocess.run([str(tests),'--nocapture'],stdout=log,stderr=subprocess.STDOUT,check=True)
            binary=Path(td)/variant;binaries[variant]=binary
            with (HERE/(variant+'-build.log')).open('w') as log:
                subprocess.run(['rustc',*flags,str(main_rs),'-o',str(binary)],stdout=log,stderr=subprocess.STDOUT,check=True)
            dump(HERE/(variant+'-binary.json'),dict(sha256=hashlib.sha256(binary.read_bytes()).hexdigest()))
        for variant,binary in binaries.items():
            runner.HERE=HERE/variant;runner.HERE.mkdir(exist_ok=True)
            with ThreadPoolExecutor(max_workers=2) as pool:
                rows=list(pool.map(lambda c:runner.run_one(binary,'mode_scaled',c),prior['cases']))
            results[variant]=[augment(row,variant) for row in rows]
    base={r['name']:r for r in baseline};summary={}
    for variant,rows in results.items():
        done=[r for r in rows if r['returncode']==0 and 'audit' in r]
        common=[(base[r['name']]['audit'],r['audit']) for r in done if base[r['name']]['audit']['original_pass']
            and base[r['name']]['audit']['exact_mode_battery_pass'] and r['audit']['original_pass'] and r['audit']['exact_mode_battery_pass']]
        repaired=[r['polished_audit'] for r in done if 'polished_audit' in r]
        summary[variant]=dict(total=13,completed=len(done),original_pass=sum(r['audit']['original_pass'] for r in done),
            battery_pass=sum(r['audit']['exact_mode_battery_pass'] for r in done),
            model_and_replay=sum(r['audit']['original_pass'] and r['audit']['exact_mode_battery_pass'] for r in done),
            physically_usable=sum(r['audit']['physically_usable'] for r in done),
            kkt_converged=sum(r['kkt_converged'] for r in done),common_pairs=len(common),
            common_time_improved=sum(b['objective']<a['objective']-1e-6 for a,b in common),
            common_time_worse=sum(b['objective']>a['objective']+1e-6 for a,b in common),
            polished_available=len(repaired),polished_physical=sum(r['physically_usable'] for r in repaired))
    dump(HERE/'results.json',dict(summary=summary,cases=results))
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
