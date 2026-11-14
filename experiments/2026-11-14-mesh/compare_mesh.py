"""Stage 5: preserve the physical warm start while refining, or change only its order.

Run from uav/: python3 experiments/2026-11-14-mesh/compare_mesh.py
Initial snapshots are generated and checked before optimization. Identical starts are reused.
"""

from concurrent.futures import ThreadPoolExecutor
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import tempfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
SCALING=ROOT/'experiments/2026-11-14-scaling'
spec=importlib.util.spec_from_file_location('scaling',SCALING/'compare_scaling.py')
runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
audit=runner.audit


def dump(path,value):path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')


def build_main():
    main=(SCALING/'mode_scaled-main.rs').read_text()
    main='#[path = '+json.dumps(str(HERE/'mesh_init.rs'))+'] mod mesh_init;\n'+main
    old='\n    let sol = solver::solve(&inst, &ph, &o);'
    new='''
    let initial = instance::initial_trajectory(&inst, &ph, &o.init);
    let initial = if a.has("refine-init") { mesh_init::refine(&initial,&ph) } else { initial };
    mesh_init::log_smoothing(&inst,&ph,&initial,&o.hom.schedule());
    if a.has("inspect-init") {
        let sm=*o.hom.schedule().last().unwrap();
        let m=metrics::evaluate(&inst,&ph,&initial,sm);
        let snapshot=solver::Solution {n_stamps:initial.r.len(),init:initial.clone(),traj:initial,
            stages:vec![],metrics:m.clone(),init_metrics:m,seconds:0.,converged:false};
        std::fs::write(a.str("out").unwrap(),output::solution_json(&inst,&ph,&snapshot,false)).unwrap();
        return;
    }
    let sol = solver::solve_from(&inst, &ph, &o, initial);
'''
    main=runner.replace_once(main,old,new)
    (HERE/'mesh-main.rs').write_text(main)


def flags_for(case,variant):
    flags=list(case['flags'])
    if variant=='refined':flags+=['--refine-init']
    elif variant=='nearest':flags+=['--order','nearest']
    return dict(case,flags=flags)


def initial_snapshot(binary,variant,case):
    folder=HERE/variant/'mode_scaled'/case['name'];folder.mkdir(parents=True,exist_ok=True)
    cmd=[str(binary),'solve',*flags_for(case,variant)['flags'],'--inspect-init','--out',str(folder/'initial.json')]
    with (folder/'initial.log').open('w') as log:subprocess.run(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=10)
    d=json.loads((folder/'initial.json').read_text())
    for key in ('thm_value_dev','thm_grad_dev'):d['metrics'].pop(key,None)
    d['experiment']=dict(purpose='initial_snapshot',variant=variant)
    (folder/'initial.json').write_text(json.dumps(d,separators=(',',':'))+'\n')
    prior=json.loads((SCALING/'mode_scaled'/case['name']/'raw.json').read_text())
    assert d['instance']==prior['instance']
    original=prior['init'];tr=d['init'];smin=d['phys']['s_min']
    if variant=='refined':
        eligible=[s>=2*smin for s in original['s']]
        assert len(tr['r'])==len(original['r'])+sum(eligible)
        assert abs(sum(tr['s'])-sum(original['s']))<len(tr['s'])*1e-9
        j=0
        for k in range(len(original['r'])):
            assert tr['r'][j]==original['r'][k] and tr['e'][j]==original['e'][k]
            if k<len(eligible):j+=2 if eligible[k] else 1
        assert min(tr['s'])>=smin-1e-9
    else:assert len(tr['r'])==len(original['r'])
    smooth=[dict(eps=float(a),p=float(b),task=float(c),mode=float(e)) for a,b,c,e in
        re.findall(r'INITSMOOTH eps=(\S+) p=(\S+) task=(\S+) mode=(\S+)',(folder/'initial.log').read_text())]
    assert len(smooth)==2
    return dict(name=case['name'],variant=variant,command=cmd,initial_audit=audit.inspect(d),smoothing=smooth,
        stamps=len(tr['r']),base_stamps=len(original['r']),identical=tr==original,
        initial_time=sum(tr['s']),base_initial_time=sum(original['s']),
        unconditional_split_short_segments=sum(s<2*smin for s in original['s']),
        unconditional_split_extra_seconds=sum(max(0.,2*smin-s) for s in original['s'])*3600)


def run_case(binary,variant,case,initial,baseline):
    folder=HERE/variant/'mode_scaled'/case['name']
    if initial['identical']:
        row=dict(baseline,reused=True,reused_from=str(SCALING/'mode_scaled'/case['name']))
        dump(folder/'audit.json',row)
    else:
        row=runner.run_one(binary,'mode_scaled',flags_for(case,variant),check_initial=False)
        row['reused']=False
        if row['returncode']==0:
            d=json.loads((folder/'raw.json').read_text());expected=json.loads((folder/'initial.json').read_text())
            assert d['init']==expected['init']
            d['experiment']['initial_variant']=variant
            (folder/'raw.json').write_text(json.dumps(d,separators=(',',':'),allow_nan=False)+'\n')
    row['initial_check']=initial
    dump(folder/'audit.json',row)
    return row


def main():
    build_main()
    previous=json.loads((SCALING/'provenance.json').read_text())
    for name,h in previous['sources'].items():assert hashlib.sha256((ROOT/'src'/name).read_bytes()).hexdigest()==h
    baseline=json.loads((SCALING/'results.json').read_text())['cases']['mode_scaled'];base={r['name']:r for r in baseline}
    flags=previous['compile_flags']
    dump(HERE/'provenance.json',dict(head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        sources=previous['sources'],model_sha256=hashlib.sha256((SCALING/'mode-model.rs').read_bytes()).hexdigest(),
        compile_flags=flags,cases=previous['cases'],thresholds=audit.TOL,max_workers=2,timeout=90))
    results={'baseline':baseline};initials={}
    with tempfile.TemporaryDirectory(prefix='uav-mesh-') as td:
        binary=Path(td)/'mesh';tests=Path(td)/'tests';main_rs=HERE/'mesh-main.rs'
        with (HERE/'build.log').open('w') as log:
            subprocess.run(['rustc',*flags,str(main_rs),'-o',str(binary)],stdout=log,stderr=subprocess.STDOUT,check=True)
        with (HERE/'tests.log').open('w') as log:
            subprocess.run(['rustc','--edition=2021','--test',str(main_rs),'-o',str(tests)],stdout=log,stderr=subprocess.STDOUT,check=True)
            subprocess.run([str(tests)],stdout=log,stderr=subprocess.STDOUT,check=True)
        # Inspect both variants before optimizing either one.
        for variant in ('baseline','refined','nearest'):
            initials[variant]={c['name']:initial_snapshot(binary,variant,c) for c in previous['cases']}
        dump(HERE/'initial-checks.json',initials)
        for variant in ('refined','nearest'):
            runner.HERE=HERE/variant
            with ThreadPoolExecutor(max_workers=2) as pool:
                results[variant]=list(pool.map(lambda c:run_case(binary,variant,c,initials[variant][c['name']],base[c['name']]),previous['cases']))
    summary={}
    for variant,rows in results.items():
        done=[r for r in rows if r['returncode']==0 and 'audit' in r]
        common=[(base[r['name']]['audit'],r['audit']) for r in done
            if base[r['name']]['audit']['original_pass'] and base[r['name']]['audit']['exact_mode_battery_pass']
            and r['audit']['original_pass'] and r['audit']['exact_mode_battery_pass']]
        changes=[b['objective']-a['objective'] for a,b in common]
        summary[variant]=dict(total=13,completed=len(done),reused=sum(r.get('reused',False) for r in rows),
            original_pass=sum(r['audit']['original_pass'] for r in done),battery_pass=sum(r['audit']['exact_mode_battery_pass'] for r in done),
            physically_usable=sum(r['audit']['physically_usable'] for r in done),kkt_converged=sum(r['kkt_converged'] for r in done),
            common_model_replay=len(common),common_time_improved=sum(v < -1e-6 for v in changes),common_time_worse=sum(v > 1e-6 for v in changes))
    dump(HERE/'results.json',dict(summary=summary,cases=results))
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
