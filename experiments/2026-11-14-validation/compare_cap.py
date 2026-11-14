"""Paired c<=s experiment; generate isolated Rust models, never edit src/.

Run from uav/: python3 experiments/2026-11-14-validation/compare_cap.py
The extra constraint uses the existing duration-bound scaling v_d*(c-s)<=0.
Both models share compilation flags and stage-domain instrumentation.
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
DEST=HERE/"cap-comparison"
spec=importlib.util.spec_from_file_location("audit",HERE/"audit.py")
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)


def dump(path,value):
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+"\n")


def build_sources():
    DEST.mkdir(exist_ok=True)
    original=(ROOT/"src/model.rs").read_text()
    modified=original.replace('6 * (self.n - 1)', '7 * (self.n - 1)',1)
    anchor='            grad[lay.c(k)] -= ph.v_d * w.ineq(5 * nseg + k, -ph.v_d * c);'
    assert anchor in modified
    modified=modified.replace(anchor,anchor+'\n'
        '            let cap = ph.v_d * w.ineq(6 * nseg + k, ph.v_d * (c - s));\n'
        '            grad[lay.c(k)] += cap;\n'
        '            grad[lay.s(k)] -= cap;')
    # Regression: all original smoothed constraints of this fixture are feasible;
    # its physically impossible charging duration must violate the added bound.
    fixture=json.loads((ROOT/"experiments/2026-11-14-critical/duration-example.json").read_text())
    def literal(v):
        return '['+','.join(literal(x) for x in v)+']' if isinstance(v,list) else repr(float(v))
    modified+='\n#[cfg(test)] mod cap_regression { use super::*;\n'
    modified+='#[test] fn excludes_negative_discharge_duration() {\n'
    modified+='let ph=Phys::default(); let inst=Instance {r0:[0.,0.],rf:[0.,0.],regions:vec![Region{o:[3.,0.],rho:1.}],tasks:vec!'+literal(fixture['instance']['tasks'])+'};\n'
    modified+='let tr=crate::instance::Traj {'+','.join(k+':vec!'+literal(fixture['solution'][k]) for k in ('r','e','s','c'))+'};\n'
    modified+='let model=Model::new(&inst,&ph,3,Smooth{eps:.2,p:2.,delta:.001}); '
    modified+='let x=tr.to_x(&model.lay); let we=vec![0.;model.lay.n_eq()]; let wi=vec![0.;model.lay.n_ineq()]; '
    modified+='let mut rec=Recorder::new(&we,&wi); let mut g=vec![0.;x.len()]; model.eval(&x,&mut rec,&mut g); '
    modified+='assert!(rec.h.iter().all(|h|h.abs()<1e-12)); assert!(rec.g[..12].iter().all(|g|*g<1e-12)); '
    modified+='assert!(rec.g[13]>0.1); } }\n'
    (DEST/"cap-model.rs").write_text(modified)
    (DEST/"cap-model.diff").write_text(''.join(difflib.unified_diff(original.splitlines(True),modified.splitlines(True),fromfile='src/model.rs',tofile='cap-model.rs')))
    solver=(ROOT/"src/solver.rs").read_text()
    anchor='        converged = res.converged;'
    assert anchor in solver
    solver=solver.replace(anchor,
        '        let probe = Traj::from_x(&x, &lay, inst, ph);\n'
        '        let over = probe.c.iter().zip(&probe.s).map(|(c,s)| (c-s).max(0.)).fold(0., f64::max);\n'
        '        let below = probe.c.iter().map(|c| (-c).max(0.)).fold(0., f64::max);\n'
        '        eprintln!("DOMAIN stage={} over_sec={:.12e} below_sec={:.12e}", l+1, 3600.*over, 3600.*below);\n'+anchor)
    (DEST/"instrumented-solver.rs").write_text(solver)
    original_main=(ROOT/"src/main.rs").read_text()
    for variant in ("baseline","capped"):
        def repl(match):
            name=match[1]
            path=DEST/"instrumented-solver.rs" if name=="solver" else (
                DEST/"cap-model.rs" if name=="model" and variant=="capped" else ROOT/"src"/(name+".rs"))
            return '#[path = '+json.dumps(str(path))+'] mod '+name+';'
        (DEST/(variant+'-main.rs')).write_text(re.sub(r'^mod (\w+);$',repl,original_main,flags=re.M))


def run_one(binary,variant,case):
    name,flags=case['name'],case['flags']
    folder=DEST/variant/name;folder.mkdir(parents=True,exist_ok=True)
    path=folder/'raw.json'
    cmd=[str(binary),'solve',*flags,'--verbose','--out',str(path)]
    try:
        with (folder/'solver.log').open('w') as log:
            result=subprocess.run(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=90)
        timeout=False;code=result.returncode
    except subprocess.TimeoutExpired:
        timeout=True;code=None
    row=dict(name=name,variant=variant,command=cmd,returncode=code,timeout=timeout)
    if code==0 and path.exists():
        d=json.loads(path.read_text());row['audit']=audit.inspect(d)
        row['kkt_converged']=d['metrics']['converged']
        row['stage_domain']=[dict(stage=int(a),over_seconds=float(b),below_seconds=float(c))
            for a,b,c in re.findall(r'DOMAIN stage=(\d+) over_sec=(\S+) below_sec=(\S+)',(folder/'solver.log').read_text())]
        assert len(row['stage_domain'])==13
        row['max_stage_over_seconds']=max(s['over_seconds'] for s in row['stage_domain'])
        row['final_stationarity']=d['stages'][-1]['stat']
        row['final_smooth_feasibility']=d['stages'][-1]['feas']
    dump(folder/'audit.json',row)
    print(variant,name,'original',row.get('audit',{}).get('original_pass'),'over',row.get('max_stage_over_seconds'),flush=True)
    return row


def main():
    build_sources()
    cases=json.loads((HERE/'provenance.json').read_text())['cases']
    results={}
    with tempfile.TemporaryDirectory(prefix='uav-cap-') as td:
        for variant in ('baseline','capped'):
            main_rs=DEST/(variant+'-main.rs');binary=Path(td)/variant
            flags=['--edition=2021','-C','opt-level=3','-C','lto=true','-C','codegen-units=1','-C','debuginfo=1']
            with (DEST/(variant+'-build.log')).open('w') as log:
                subprocess.run(['rustc',*flags,str(main_rs),'-o',str(binary)],check=True,stdout=log,stderr=subprocess.STDOUT)
            if variant=='capped':
                tests=Path(td)/'cap-tests'
                with (DEST/'tests.log').open('w') as log:
                    subprocess.run(['rustc','--edition=2021','--test',str(main_rs),'-o',str(tests)],check=True,stdout=log,stderr=subprocess.STDOUT)
                    subprocess.run([str(tests)],check=True,stdout=log,stderr=subprocess.STDOUT)
            dump(DEST/(variant+'-provenance.json'),dict(compile_flags=flags,binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest()))
            with ThreadPoolExecutor(max_workers=2) as pool:
                results[variant]=list(pool.map(lambda c:run_one(binary,variant,c),cases))
    for b,c in zip(results['baseline'],results['capped']):
        if b['returncode']==0 and c['returncode']==0:
            bd=json.loads((DEST/'baseline'/b['name']/'raw.json').read_text())
            cd=json.loads((DEST/'capped'/c['name']/'raw.json').read_text())
            assert bd['instance']==cd['instance'] and bd['init']==cd['init']
    summary={}
    for variant,rows in results.items():
        done=[r for r in rows if r['returncode']==0 and 'audit' in r]
        summary[variant]=dict(total=len(cases),completed=len(done),
            original_pass=sum(r['audit']['original_pass'] for r in done),
            battery_pass=sum(r['audit']['exact_mode_battery_pass'] for r in done),
            physically_usable=sum(r['audit']['physically_usable'] for r in done),
            kkt_converged=sum(r['kkt_converged'] for r in done),
            stages_over_one_second=sum(r['max_stage_over_seconds']>1 for r in done),
            final_over_one_second=sum(r['audit']['charging_over_segment_seconds']>1 for r in done))
    dump(DEST/'results.json',dict(summary=summary,cases=results))
    print(json.dumps(summary,indent=2))


if __name__=='__main__':
    main()
