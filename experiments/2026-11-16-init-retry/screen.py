"""Choose only on original negative battery; never launch an NLP."""
import json
import os
from pathlib import Path
import subprocess
import sys

BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[1]


def main():
    assert not (BASE/'screening.json').exists();(BASE/'screen-logs').mkdir()
    rows=[];selected=[]
    for tau,start in [(4,4100),(9,9100)]:
        found=0
        for seed in range(start,start+100):
            case=f'tau{tau}-seed{seed}'
            env=dict(os.environ,UAV_R2_CASE=case,UAV_R2F_KIND='original',
                OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1')
            with (BASE/'screen-logs'/f'{case}.log').open('x') as log:
                subprocess.run([sys.executable,str(BASE/'guard.py')],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
            guard=json.loads((BASE/'initializations'/case/'guard.json').read_text())
            negative=guard['original_audit']['min_energy']<0.
            rows.append(dict(case=case,tau=tau,seed=seed,original_audit=guard['original_audit'],selected=negative))
            if negative:selected.append(case);found+=1
            if found==2:break
    data=dict(rows=rows,selected=selected,selection='first two original-negative inputs in each fixed range',optimizer_launched=False)
    (BASE/'screening.json').write_text(json.dumps(data,indent=2)+'\n')
    print(json.dumps(dict(audited=len(rows),selected=selected)));assert len(selected)==4


if __name__=='__main__':main()
