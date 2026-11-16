"""Audit the old hard-case boundary arithmetic on saved initial matrices only."""
import json
from pathlib import Path
import numpy as np

BASE=Path(__file__).resolve().parent


def main():
    rows=[]
    for path in sorted((BASE/'inner').glob('*/first-step.npz')):
        with np.load(path) as data:
            H,g=data['H'],data['g'];w,V=np.linalg.eigh(H);gt=V.T@g
            lo=max(0.,-w[0])+1e-14*max(1.,abs(w[0]));p=-gt/(w+lo)
            hard=bool(np.linalg.norm(p)<=1.)
            row=dict(case=path.parent.name,delta=1.,old_step_norm=float(np.linalg.norm(data['old_step'])),
                hard_case_branch=hard,shift=float(lo),lowest_component_before=float(p[0]))
            if hard:
                t=np.sqrt(max(1.-float(p@p),0.));t=t if gt[0]<=0 else -t
                old=p.copy();old[0]+=t
                # Solve ||p+t*e0||=delta including the cross term 2*p[0]*t.
                fixed=p.copy();sign=1. if gt[0]<=0 else -1.
                fixed[0]=sign*np.sqrt(max(1.-float(p[1:]@p[1:]),0.))
                np.testing.assert_allclose(np.linalg.norm(old),np.linalg.norm(data['old_step']),atol=1e-12)
                np.testing.assert_allclose(np.linalg.norm(fixed),1.,atol=1e-12,rtol=1e-12)
                row.update(old_added_component=float(t),omitted_norm_squared_cross_term=float(2*p[0]*t),
                    algebra_corrected_step_norm=float(np.linalg.norm(fixed)),
                    correction_is_algebra_only=True,corrected_optimizer_launched=False)
            rows.append(row)
    # Nonzero first component exposes the cross term without a UAV model.
    p=np.array([.2,.3]);t=np.sqrt(1.-p@p)
    wrong=p+np.array([t,0.]);fixed=p.copy();fixed[0]=np.sqrt(1.-p[1]**2)
    assert np.linalg.norm(wrong)>1.1
    np.testing.assert_allclose(np.linalg.norm(fixed),1.,atol=1e-15)
    result=dict(rows=rows,synthetic_old_norm=float(np.linalg.norm(wrong)),
        synthetic_corrected_norm=float(np.linalg.norm(fixed)),new_inner_solves=0)
    out=BASE/'tr-audit.json';assert not out.exists();out.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))


if __name__=='__main__':main()
