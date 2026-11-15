"""Rebuild the input-only NLP and recompute its KKT and acceptance without solving."""
import json
import numpy as np
import helpers as h


def read(name):
    return json.loads((h.INIT/name).read_text())


def main():
    result,data=read('result.json'),read('input.json')
    restoration=h.load_from(h.R2A,'restore')
    model=restoration.fb.FixedBranch(data,moving=True)
    checked=dict(accepted=result['accepted'],same_modes_and_task_stamps=True,original_input_verified=True)
    if (h.INIT/'solver.json').exists():
        saved=read('solver.json')
        point,lam,lam_x=(np.array(saved[k]) for k in ['point','lam','lam_x'])
        assert saved['options']==restoration.OPTIONS
        measured=model.kkt(point,lam,lam_x)
        np.testing.assert_allclose(list(measured.values()),list(result['raw_kkt'].values()),atol=1e-10,rtol=1e-8)
        checked['returned_kkt_recomputed']=True
        if result['accepted']:
            accepted,report,output=restoration.accept(model,data,point,lam,lam_x)
            assert accepted and all(report['checks'].values())
            document=read('solution.json')
            assert document['modes']==data['modes'] and document['task_stamp']==data['task_stamp']
            for k in ['r','e','s','c']:
                np.testing.assert_array_equal(output['solution'][k],document['solution'][k])
            m=h.fidelity.Variant('R')
            source=read('source.json');tr=document['solution']
            y=np.r_[np.array(tr['r'])[1:-1].ravel(),tr['e'][1:],tr['s'],tr['c']]/m.scale
            np.testing.assert_array_equal(y,source['y'])
            assert source['lam']==[0.]*m.me and source['mu']==[0.]*m.mi and source['rho']==1e4
            assert source['eps']==.0005 and source['p']==12.
            prior=json.loads((h.R2D/'cases/G'/h.CASE/'source.json').read_text())
            np.testing.assert_array_equal(m.native.y,prior['y'])
            np.testing.assert_array_equal(h.tr.decode(m,m.native.y,m.source)['r'],data['init']['r'])
            assert all(document['solution']['r'][stamp]==task for stamp,task in zip(data['task_stamp'],data['instance']['tasks']))
            checked.update(raw_kkt=measured,final_kkt=report['final_kkt'],original_residuals=report['original_residuals'],
                min_energy=report['min_energy'],strict_original_pass=report['original_residuals']['viol']<1e-10,
                dense_energy_checked=True,full_precision_y_checked=True)
            m.close()
    h.write(h.INIT/'verification.json',checked)


if __name__=='__main__':
    main()
