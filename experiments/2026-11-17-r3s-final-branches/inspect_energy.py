import json
from pathlib import Path
import sys
from diagnostics import decode

BASE=Path(__file__).resolve().parent;ROOT=BASE.parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from repair_initialization import audit
from diagnose_solution import signed_charge


def read(p):return json.loads(p.read_text())


def main():
    assert not (BASE/'energy-detail.json').exists()
    source=ROOT/'experiments/2026-11-17-r3s-gradient-e2e/fast';result=[]
    for case in ['tau8-seed8000006','tau8-seed8000062']:
        template=read(source/'inputs'/case/'input.json');scale=read(source/'inputs'/case/'original-state.json')['scale']
        raw=read(source/'cases/G'/case/'stages/stage13/result.json');tr=decode(raw['y'],scale,template)
        modes=[r['winner'] for r in raw['selection']['modes']];ph=template['phys']
        result.append(dict(case=case,original_audit=audit(template),returned_audit=audit(read(source/'runs'/case/'selected.json')),
             discharge_segment_charge_seconds=sum(c*3600 for c,m in zip(tr['c'],modes) if m<0),
             discharge_segment_local_energy_gain=sum(signed_charge(ph,tr['e'][k],tr['c'][k])-tr['e'][k]+ph['zeta']*tr['c'][k]
                                                    for k,m in enumerate(modes) if m<0),
             stored_min_energy=min(tr['e']),pure_mode_min_energy=raw['selection']['audit']['pure_mode_min_energy']))
    (BASE/'energy-detail.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))


if __name__=='__main__':main()
