"""Stage 4: isolate penalty carry, multiplier carry, and strict stage convergence.

Run from uav/: python3 experiments/2026-11-14-auglag/compare_carry.py
Uses the fixed Stage-3 mode-scaled model and never edits src/.
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
SCALING=ROOT/'experiments/2026-11-14-scaling'
VALIDATION=ROOT/'experiments/2026-11-14-validation'
spec=importlib.util.spec_from_file_location('scaling',SCALING/'compare_scaling.py')
runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
audit=runner.audit


def dump(path,value):path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')


def build_sources():
    original=(VALIDATION/'cap-comparison/instrumented-solver.rs').read_text()
    main=(SCALING/'mode_scaled-main.rs').read_text()
    hook='        let is_last = l + 1 == schedule.len();'
    assert original.count(hook)==1
    for strategy in ('reset_penalty','reset_duals','strict_gate'):
        solver=original
        if strategy in ('reset_penalty','reset_duals'):
            change='st.rho = o.al.rho0;' if strategy=='reset_penalty' else 'st.lam.fill(0.); st.mu.fill(0.);'
            checks=('assert_eq!(st.lam, before.lam); assert_eq!(st.mu, before.mu); assert_eq!(st.rho, o.al.rho0);'
                    if strategy=='reset_penalty' else
                    'assert_eq!(st.rho, before.rho); assert!(st.lam.iter().all(|v| *v==0.)); assert!(st.mu.iter().all(|v| *v==0.));')
            injected='''
        let before = st.clone();
        if l > 0 { CHANGE }
        CHECKS
        let old_dual=before.lam.iter().chain(&before.mu).fold(0.0f64,|a,b|a.max(b.abs()));
        let new_dual=st.lam.iter().chain(&st.mu).fold(0.0f64,|a,b|a.max(b.abs()));
        eprintln!("CARRY stage={} rho_before={:.12e} rho_after={:.12e} dual_before={:.12e} dual_after={:.12e}",l+1,before.rho,st.rho,old_dual,new_dual);
'''.replace('CHANGE',change).replace('CHECKS',checks)
            solver=solver.replace(hook,hook+injected)
        else:
            solver=runner.replace_once(solver,'    for (l, &sm) in schedule.iter().enumerate() {',
                '    let mut remaining_outer = (schedule.len()-1)*o.stage_outer + o.al.max_outer;\n'
                '    for (l, &sm) in schedule.iter().enumerate() {\n'
                '        if remaining_outer == 0 { break; }')
            solver=runner.replace_once(solver,
                'max_outer: if is_last { o.al.max_outer } else { o.stage_outer },',
                'max_outer: remaining_outer,')
            solver=runner.replace_once(solver,'        converged = res.converged;',
                '        remaining_outer -= res.outer;\n'
                '        converged = res.converged && is_last;\n'
                '        if !res.converged { break; }')
        path=HERE/(strategy+'-solver.rs');path.write_text(solver)
        (HERE/(strategy+'.diff')).write_text(''.join(difflib.unified_diff(original.splitlines(True),solver.splitlines(True),fromfile='stage3-solver',tofile=strategy,n=0)))
        old='#[path = '+json.dumps(str(VALIDATION/'cap-comparison/instrumented-solver.rs'))+'] mod solver;'
        new='#[path = '+json.dumps(str(path))+'] mod solver;'
        (HERE/(strategy+'-main.rs')).write_text(runner.replace_once(main,old,new))


def augment(row,strategy):
    name=row['name'];folder=HERE/strategy/'mode_scaled'/name
    if row['returncode']!=0 or 'audit' not in row:return row
    d=json.loads((folder/'raw.json').read_text())
    d['experiment']['al_strategy']=strategy
    (folder/'raw.json').write_text(json.dumps(d,separators=(',',':'))+'\n')
    row['al_strategy']=strategy
    row['stages_completed']=len(d['stages'])
    row['homotopy_complete']=len(d['stages'])==13
    row['outer_total']=sum(s['outer'] for s in d['stages'])
    row['inner_total']=sum(s['inner'] for s in d['stages'])
    row['final_eps']=d['stages'][-1]['eps']
    row['final_p']=d['stages'][-1]['p']
    assert row['outer_total']<=150 and row['inner_total']<=300000
    log=(folder/'solver.log').read_text()
    carry=[dict(stage=int(a),rho_before=float(b),rho_after=float(c),dual_before=float(e),dual_after=float(f))
        for a,b,c,e,f in re.findall(r'CARRY stage=(\d+) rho_before=(\S+) rho_after=(\S+) dual_before=(\S+) dual_after=(\S+)',log)]
    if strategy!='strict_gate':
        assert len(carry)==13
        if strategy=='reset_penalty':assert all(s['rho_after']==10. for s in carry)
        else:assert all(s['dual_after']==0. and s['rho_before']==s['rho_after'] for s in carry)
    row['carry']=carry
    dump(folder/'audit.json',row)
    return row


def candidate_selection(rows,base):
    result=[]
    for row in rows:
        if row['returncode']!=0 or 'audit' not in row:continue
        folder=base/row['name'];d=json.loads((folder/'raw.json').read_text())
        init=audit.inspect(dict(d,solution=d['init']))
        pool=[('initial',init),('final',row['audit'])]
        if 'polished_audit' in row:pool.append(('polished',row['polished_audit']))
        choices={}
        for kind in ('model_and_replay','one_station'):
            eligible=[(tag,a) for tag,a in pool if (a['original_pass'] and a['exact_mode_battery_pass'] and
                       a['charging_domain_pass'] and (kind!='one_station' or a['one_station_pass']))]
            best=min(eligible,key=lambda x:x[1]['objective']) if eligible else None
            choices[kind]=None if best is None else dict(source=best[0],objective=best[1]['objective'])
        result.append(dict(name=row['name'],choices=choices))
    return result


def main():
    build_sources()
    prior=json.loads((SCALING/'provenance.json').read_text())
    for name,h in prior['sources'].items():assert hashlib.sha256((ROOT/'src'/name).read_bytes()).hexdigest()==h
    baseline=json.loads((SCALING/'results.json').read_text())['cases']['mode_scaled']
    results={'carry_all':baseline}
    flags=prior['compile_flags']
    dump(HERE/'provenance.json',dict(head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
         model_sha256=hashlib.sha256((SCALING/'mode-model.rs').read_bytes()).hexdigest(),
         sources=prior['sources'],cases=prior['cases'],compile_flags=flags,outer_budget=150,inner_budget=300000,
         baseline='experiments/2026-11-14-scaling/mode_scaled'))
    with tempfile.TemporaryDirectory(prefix='uav-carry-') as td:
        for strategy in ('reset_penalty','reset_duals','strict_gate'):
            binary=Path(td)/strategy
            with (HERE/(strategy+'-build.log')).open('w') as log:
                subprocess.run(['rustc',*flags,str(HERE/(strategy+'-main.rs')),'-o',str(binary)],check=True,stdout=log,stderr=subprocess.STDOUT)
            dump(HERE/(strategy+'-binary.json'),dict(sha256=hashlib.sha256(binary.read_bytes()).hexdigest()))
            runner.HERE=HERE/strategy;runner.HERE.mkdir(exist_ok=True)
            with ThreadPoolExecutor(max_workers=2) as pool:
                rows=list(pool.map(lambda c:runner.run_one(binary,'mode_scaled',c,
                    expected_stages=None if strategy=='strict_gate' else 13),prior['cases']))
            results[strategy]=[augment(r,strategy) for r in rows]
    selection={}
    selection['carry_all']=candidate_selection(baseline,SCALING/'mode_scaled')
    summary={}
    for strategy,rows in results.items():
        done=[r for r in rows if r['returncode']==0 and 'audit' in r]
        if strategy!='carry_all':selection[strategy]=candidate_selection(rows,HERE/strategy/'mode_scaled')
        summary[strategy]=dict(total=13,completed=len(done),original_pass=sum(r['audit']['original_pass'] for r in done),
            battery_pass=sum(r['audit']['exact_mode_battery_pass'] for r in done),
            physically_usable=sum(r['audit']['physically_usable'] for r in done),
            kkt_converged=sum(r['kkt_converged'] for r in done),
            homotopy_complete=sum(r.get('homotopy_complete',True) for r in done),
            selectable_model_and_replay=sum(s['choices']['model_and_replay'] is not None for s in selection[strategy]),
            selectable_one_station=sum(s['choices']['one_station'] is not None for s in selection[strategy]))
    dump(HERE/'candidate-selection.json',selection)
    dump(HERE/'results.json',dict(summary=summary,cases=results))
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
