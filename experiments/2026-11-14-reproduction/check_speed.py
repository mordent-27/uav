"""Verify identical feasible sets, derivatives, and multiplier mapping for the variant."""
import json
from pathlib import Path
from independent_al import Model,np

HERE=Path(__file__).resolve().parent


def denominator(model,y):
    x=y*model.scale;ns=model.stamps-1;np_=2*(model.stamps-2)
    d=model.solution(y);inst=d['instance']
    r=np.vstack([inst['r0'],x[:np_].reshape(-1,2),inst['rf']])
    s=x[np_+ns:np_+2*ns]
    return np.sqrt(np.sum(np.diff(r,axis=0)**2,axis=1)+.001**2)+np.sqrt((36*s)**2+.001**2)


def check():
    orig=Model();new=Model(library='/tmp/uav-reproduction-speed.so')
    np.testing.assert_array_equal(orig.y,new.y);np.testing.assert_array_equal(orig.scale,new.scale)
    rng=np.random.default_rng(890)
    maximum=0.
    for eps,p in [(.2,2.),(.0005,12.)]:
        orig.stage(eps,p);new.stage(eps,p)
        for _ in range(25):
            y=orig.y+rng.uniform(-.3,.3,orig.n)
            orig.eval(y,np.zeros(orig.me),np.zeros(orig.mi),0.)
            oldh,oldg=orig.h.copy(),orig.g.copy()
            new.eval(y,np.zeros(new.me),np.zeros(new.mi),0.)
            ns=orig.stamps-1
            np.testing.assert_array_equal(oldh,new.h)
            np.testing.assert_array_equal(oldg[ns:],new.g[ns:])
            np.testing.assert_array_equal(oldg[:ns]<=0,new.g[:ns]<=0)
            error=np.max(abs(new.g[:ns]*denominator(orig,y)-oldg[:ns]))
            maximum=max(maximum,float(error))
            assert error<1e-10
    # Direct finite differences of the actual modified model at final smoothing.
    y=new.y+rng.uniform(-.1,.1,new.n)
    lam,mu=rng.normal(size=new.me),rng.uniform(0.,1.,new.mi)
    _,grad=new.eval(y,lam,mu,0.)
    worst=0.
    for i in range(new.n):
        plus,minus=y.copy(),y.copy();plus[i]+=1e-6;minus[i]-=1e-6
        fd=(new.eval(plus,lam,mu,0.)[0]-new.eval(minus,lam,mu,0.)[0])/(2e-6)
        worst=max(worst,float(abs(fd-grad[i])/(1+abs(fd))))
    assert worst<1e-5
    result=dict(random_points=50,initial_state_identical=True,other_constraints_identical=True,
                speed_feasible_set_identical=True,max_identity_error=maximum,gradient_error=worst)
    (HERE/'speed-equivalence.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))
    orig.close();new.close()


if __name__=='__main__':check()
