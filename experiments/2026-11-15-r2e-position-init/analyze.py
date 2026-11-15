"""Compare original and accepted repaired initial states; keep rejected initialization explicit."""
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OLD=HERE.parent/'2026-11-15-r2d-fallback'


def read(p):return json.loads(p.read_text())


def direct(folder):
    r=read(folder/'result.json');v=read(folder/'verification.json')
    assert read(folder/'steps.json')==dict(run='ok',restore='ok',verify='ok')
    restored=folder/'restored/result.json';a=read(restored) if restored.exists() else dict(accepted=False)
    return dict(path=str(folder.relative_to(ROOT)),common_pass=r['final_common_pass'],both_scales_pass=r['final_both_scales_pass'],
        restored_accepted=a['accepted'],hours=a.get('objective') if a['accepted'] else None,raw_hours=r['objective'],
        common_kkt=r['common_kkt'],physical_kkt=r['paper_units_kkt'],stop=r['stop'],
        charges=r['selection']['charging_segments'],modes=[m['winner'] for m in r['selection']['modes']],
        original_residual=a.get('original_residuals',{}).get('viol'),min_energy=a.get('min_energy'),
        al_seconds=r['elapsed'],restoration_seconds=a.get('seconds',0.),
        outer=v['completed_outer'],inner=v['accepted_inner_points'],interrupted=v['interrupted_accepted_points'])


def main():
    rows=[];phases=[]
    for tau in [1,3,5,7]:
        case=f'tau{tau}-seed3';i=read(HERE/'initializations'/case/'result.json')
        v=read(HERE/'initializations'/case/'verification.json');assert v['accepted']==i['accepted']
        baseline=direct((HERE/'cases/original'/case) if tau in [1,3] else OLD/'cases/direct'/case)
        repaired=direct(HERE/'cases/repaired'/case) if i['accepted'] else None
        if repaired:phases.append(repaired)
        if tau in [1,3]:phases.append(baseline)
        rows.append(dict(case=case,initialization=i,initialization_checked=v,baseline=baseline,repaired=repaired,
            change_seconds=None if repaired is None or baseline['hours'] is None or repaired['hours'] is None else
                3600*(repaired['hours']-baseline['hours']),
            needed_charge19_preserved=None if repaired is None or tau<5 else repaired['modes'][19]==i['initial_modes'][19]))
    summary=dict(cases=rows,initializations_accepted=sum(r['initialization']['accepted'] for r in rows),
        repaired_restored_accepted=sum(bool(r['repaired'] and r['repaired']['restored_accepted']) for r in rows),
        new_phases=len(phases),new_outer=sum(p['outer'] for p in phases),
        new_inner=sum(p['inner'] for p in phases),new_interrupted=sum(p['interrupted'] for p in phases),
        execution=read(HERE/'execution.json'),independent_seed_families=1,
        main_source_changed=False,paper_reproduction=False)
    (HERE/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k not in ['cases','execution']}))


if __name__=='__main__':main()
