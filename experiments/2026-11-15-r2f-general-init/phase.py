"""Use original or repaired input y with the unchanged direct-final runner."""
import json
import traceback
import numpy as np
import helpers as h


def main():
    h.HERE.mkdir(parents=True,exist_ok=False)
    m=h.fidelity.Variant('R')
    prior=json.loads((h.INIT/'original-state.json').read_text())
    np.testing.assert_array_equal(m.native.y,prior['y'])
    if h.KIND=='original':
        y=m.native.y.copy()
    else:
        assert json.loads((h.INIT/'result.json').read_text())['accepted']
        assert json.loads((h.INIT/'verification.json').read_text())['accepted']
        y=np.array(json.loads((h.INIT/'source.json').read_text())['y'])
    m.stage(.0005,12.)
    lam,mu,rho=np.zeros(m.me),np.zeros(m.mi),1e4
    value,gradient=m.eval(y,lam,mu,rho)
    le,mi=lam+rho*m.h,np.maximum(0.,mu+rho*m.g)
    jac=m.jacobian(y)
    _,gf=m.eval(y,np.zeros(m.me),np.zeros(m.mi),0.)
    np.testing.assert_allclose(gradient,gf+jac[:m.me].T@le+jac[m.me:].T@mi,atol=1e-9,rtol=1e-8)
    class Wrap:
        pass
    wrap=Wrap();wrap.m=m
    source=dict(h.state(y,lam,mu,rho,0),eps=.0005,p=12.,**h.assess(wrap,y,lam,mu),
        note='R2e '+h.KIND+' input state; same final-stage model, AL and budget')
    h.write(h.SOURCE,source)
    h.write(h.HERE/'preflight.json',dict(case=h.CASE,kind=h.KIND,original_initial_state_verified=True,
        independent_Jacobian_gradient_verified=True,initial_al_value=value,
        initial_al_gradient_inf=float(max(abs(gradient))),stamps=m.stamps,variables=m.n))
    m.close()
    steps={}
    try:
        for name,action in [('run',lambda:h.load_from(h.DIRECT,'run').main()),
                            ('restore',lambda:h.load_from(h.R2A,'restore').main()),
                            ('verify',lambda:h.load_from(h.DIRECT,'verify').main())]:
            try:
                action();steps[name]='ok'
            except Exception:
                steps[name]=traceback.format_exc();raise
    finally:
        h.write(h.HERE/'steps.json',steps)


if __name__=='__main__':
    main()
