"""Select negative-battery inputs before testing their repairability or solving anything."""
import copy
import hashlib
import json
import sys
from time import monotonic
import helpers as h

sys.path.insert(0,str(h.ROOT/'scripts'))
import repair_initialization as repair


def main():
    assert not (h.BASE/'screening.json').exists(),'refuse to rescreen'
    start=monotonic();rows=[];selected=[]
    for tau,lower,upper in [(5,200,399),(7,400,599)]:
        count=0
        for seed in range(lower,upper+1):
            case=f'tau{tau}-seed{seed}'
            model=h.tr.Model(tau,seed,h.fidelity.LIB['normalized']);y=model.y.copy()
            data=model.solution(y);trajectory=h.tr.decode(model,y,data)
            data['init']=copy.deepcopy(trajectory);data['solution']=copy.deepcopy(trajectory)
            data['instance']['tasks']=[trajectory['r'][stamp] for stamp in data['task_stamp']]
            audit=repair.audit(data)
            negative=min(trajectory['e'])<data['phys']['e_min'] or audit['min_energy']<data['phys']['e_min']
            row=dict(case=case,tau=tau,seed=seed,minimum_stored_energy=min(trajectory['e']),
                audit=audit,negative_battery=negative,selected=negative,
                initial_y_sha256=hashlib.sha256(json.dumps(y.tolist()).encode()).hexdigest())
            rows.append(row)
            if negative:
                folder=h.BASE/'screened-inputs'/case;folder.mkdir(parents=True,exist_ok=False)
                h.write(folder/'input.json',data);h.write(folder/'state.json',dict(y=y.tolist(),scale=model.scale.tolist()))
                selected.append(case);count+=1
            model.close()
            if count==2:break
    h.write(h.BASE/'screening.json',dict(rule='first two negative-battery inputs per fixed seed range',
        ranges=[dict(tau=5,start=200,end=399),dict(tau=7,start=400,end=599)],
        scanned=len(rows),selected=selected,rows=rows,seconds=monotonic()-start,
        conditional_cohort=True,repairability_not_used_for_selection=True))
    print(json.dumps(dict(scanned=len(rows),selected=selected,seconds=monotonic()-start)),flush=True)


if __name__=='__main__':main()
