"""Stage 7: stable LSE with the same original-residual worst-case bound as PI.

Run from uav/: python3 experiments/2026-11-14-lse/compare_lse.py
The two LSE variants differ only in a derived residual scale, not their feasible sets.
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

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
SCALING=ROOT/'experiments/2026-11-14-scaling';APPROX=ROOT/'experiments/2026-11-14-approximation'
spec=importlib.util.spec_from_file_location('scaling',SCALING/'compare_scaling.py')
runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner);audit=runner.audit


def dump(path,value):path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')


def build_sources():
    original=(APPROX/'combined-model.rs').read_text();main=(APPROX/'combined-main.rs').read_text()
    helper='''
pub fn lse_temperature(n:usize,p:f64,eps:f64)->f64 {
    if n==1 {return eps/p;}
    let logn=(n as f64).ln();eps*(logn/p).exp_m1()/logn
}

pub fn matched_lse(z:&[f64],p:f64,eps:f64,d:&mut[f64])->f64 {
    if z.len()==1 {d[0]=1.;return z[0];}
    let tau=lse_temperature(z.len(),p,eps);
    let shift=z.iter().copied().fold(f64::INFINITY,f64::min);
    let mut sum=0.;
    for (di,zi) in d.iter_mut().zip(z) {*di=(-(zi-shift)/tau).exp();sum+=*di;}
    for di in &mut d[..z.len()] {*di/=sum;}
    shift-tau*sum.ln()
}
'''
    for variant in ('lse','lse_scaled'):
        scaled=variant=='lse_scaled';model=original
        model=runner.replace_once(model,'pub struct Model<',helper+'\npub struct Model<')
        for length in ('n','nj + 1'):
            old=f'smooth_min(&z[..{length}], sm.p, &mut dz[..{length}])'
            new=f'matched_lse(&z[..{length}], sm.p, sm.eps, &mut dz[..{length}])'
            model=runner.replace_once(model,old,new)
        if scaled:
            model=runner.replace_once(model,'let wt = w.ineq(lay.ineq_task(i), phi - sm.eps);',
                'let beta = (n as f64).powf(-1.0/sm.p);\n            let wt = beta * w.ineq(lay.ineq_task(i), beta * (phi - sm.eps));')
            model=runner.replace_once(model,'let wt = w.ineq(lay.ineq_mode(k), phi - sm.eps);',
                'let beta = ((nj+1) as f64).powf(-1.0/sm.p);\n            let wt = beta * w.ineq(lay.ineq_mode(k), beta * (phi - sm.eps));')
        (HERE/(variant+'.diff')).write_text(''.join(difflib.unified_diff(original.splitlines(True),model.splitlines(True),fromfile='PI-model',tofile=variant,n=0)))
        model+='\n#[cfg(test)] const SCALE_LSE_RESIDUAL: bool = '+str(scaled).lower()+';\n'
        (HERE/(variant+'-model.rs')).write_text(model+(HERE/'lse_tests.rs').read_text())
        old='#[path = '+json.dumps(str(APPROX/'combined-model.rs'))+'] mod model;'
        new='#[path = '+json.dumps(str(HERE/(variant+'-model.rs')))+'] mod model;'
        (HERE/(variant+'-main.rs')).write_text(runner.replace_once(main,old,new))


def augment(row,variant):
    folder=HERE/variant/'mode_scaled'/row['name']
    if row['returncode']==0 and 'audit' in row:
        path=folder/'raw.json';d=json.loads(path.read_text());n=len(d['solution']['r']);j=len(d['instance']['regions'])+1
        def tau(count,p,eps):return eps*math.expm1(math.log(count)/p)/math.log(count) if count>1 else eps/p
        d['experiment']['approximation']=variant
        d['experiment']['temperatures']=[dict(eps=s['eps'],p=s['p'],task=tau(n,s['p'],s['eps']),mode=tau(j,s['p'],s['eps'])) for s in d['stages']]
        path.write_text(json.dumps(d,separators=(',',':'),allow_nan=False)+'\n')
        row['approximation']=variant;row['outer_total']=sum(s['outer'] for s in d['stages']);row['inner_total']=sum(s['inner'] for s in d['stages'])
        assert row['outer_total']<=150 and row['inner_total']<=300000
    dump(folder/'audit.json',row);return row


def main():
    build_sources();prior=json.loads((SCALING/'provenance.json').read_text())
    for name,h in prior['sources'].items():assert hashlib.sha256((ROOT/'src'/name).read_bytes()).hexdigest()==h
    baseline=json.loads((APPROX/'results.json').read_text())['cases']['combined'];base={r['name']:r for r in baseline};flags=prior['compile_flags']
    dump(HERE/'provenance.json',dict(head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),sources=prior['sources'],
        baseline='experiments/2026-11-14-approximation/combined',model_sha256=hashlib.sha256((APPROX/'combined-model.rs').read_bytes()).hexdigest(),
        cases=prior['cases'],compile_flags=flags,thresholds=audit.TOL,timeout=90,max_workers=2))
    results={'PI':baseline}
    with tempfile.TemporaryDirectory(prefix='uav-lse-') as td:
        binaries={}
        for variant in ('lse','lse_scaled'):
            tests=Path(td)/(variant+'-tests');main_rs=HERE/(variant+'-main.rs')
            with (HERE/(variant+'-tests.log')).open('w') as log:
                subprocess.run(['rustc','--edition=2021','--test',str(main_rs),'-o',str(tests)],stdout=log,stderr=subprocess.STDOUT,check=True)
                subprocess.run([str(tests),'--nocapture','--test-threads=1'],stdout=log,stderr=subprocess.STDOUT,check=True)
            binary=Path(td)/variant;binaries[variant]=binary
            with (HERE/(variant+'-build.log')).open('w') as log:
                subprocess.run(['rustc',*flags,str(main_rs),'-o',str(binary)],stdout=log,stderr=subprocess.STDOUT,check=True)
            dump(HERE/(variant+'-binary.json'),dict(sha256=hashlib.sha256(binary.read_bytes()).hexdigest()))
        for variant,binary in binaries.items():
            runner.HERE=HERE/variant;runner.HERE.mkdir(exist_ok=True)
            with ThreadPoolExecutor(max_workers=2) as pool:rows=list(pool.map(lambda c:runner.run_one(binary,'mode_scaled',c),prior['cases']))
            results[variant]=[augment(r,variant) for r in rows]
    summary={}
    for variant,rows in results.items():
        done=[r for r in rows if r['returncode']==0 and 'audit' in r];repaired=[r['polished_audit'] for r in done if 'polished_audit' in r]
        common=[(base[r['name']]['audit'],r['audit']) for r in done if base[r['name']]['audit']['original_pass'] and base[r['name']]['audit']['exact_mode_battery_pass']
             and r['audit']['original_pass'] and r['audit']['exact_mode_battery_pass']]
        summary[variant]=dict(total=13,completed=len(done),original_pass=sum(r['audit']['original_pass'] for r in done),
            battery_pass=sum(r['audit']['exact_mode_battery_pass'] for r in done),model_and_replay=sum(r['audit']['original_pass'] and r['audit']['exact_mode_battery_pass'] for r in done),
            physically_usable=sum(r['audit']['physically_usable'] for r in done),kkt_converged=sum(r['kkt_converged'] for r in done),
            common_pairs=len(common),common_time_improved=sum(b['objective']<a['objective']-1e-6 for a,b in common),
            common_time_worse=sum(b['objective']>a['objective']+1e-6 for a,b in common),polished_available=len(repaired),polished_physical=sum(r['physically_usable'] for r in repaired))
    dump(HERE/'results.json',dict(summary=summary,cases=results));print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
