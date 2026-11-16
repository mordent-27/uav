import unittest
import numpy as np
import stage


class Model:
    """min x0^2+x1^2 s.t. h=x0+x1-1=0, g=-x0<=0 (inactive)."""
    def __init__(self,c):self.c=c;self.h=np.zeros(1);self.g=np.zeros(1)
    def eval(self,y):
        lam,mu,rho=np.array(self.c['lam']),np.array(self.c['mu']),self.c['rho']
        self.h=np.array([y[0]+y[1]-1.]);self.g=np.array([-y[0]])
        v=y@y+lam@self.h+rho/2*self.h@self.h+(np.maximum(0,mu+rho*self.g)**2-mu**2).sum()/(2*rho)
        return v,2*y+(lam[0]+rho*self.h[0])*np.ones(2)+np.array([-np.maximum(0,mu[0]+rho*self.g[0]),0.])


class Frozen:
    def __init__(self,c):self.m=Model(c)
    def eval(self,y):return self.m.eval(y)
    def close(self):pass


def state(y,lam,mu,rho,st):return dict(y=y.tolist(),lam=lam.tolist(),mu=mu.tolist(),rho=rho,stage=st)


def inner(f,c,y,deadline,record):
    t=(c['rho']-c['lam'][0])/(2+2*c['rho']);z=np.array([t,t]);_,g=f.eval(z)
    return dict(y=z,gradient=g,gradient_inf=float(abs(g).max()),status='converged')


def assess(f,y,lam,mu):
    f.m.eval(y);h=f.m.h;stat=float(abs(2*y+lam[0]*np.ones(2)).max())
    k=dict(stat=stat,feas=float(abs(h).max()),comp=0.);return dict(common_kkt=k,paper_units_kkt=dict(k))


class TestStage(unittest.TestCase):
    def test_multiplier_update_and_pass(self):
        rows,final=stage.run_stage(np.array([0.,0.]),np.zeros(1),np.zeros(1),1e4,13,Frozen,inner,assess,state,1e-6,600,10)
        self.assertEqual(final['stop'],'kkt');self.assertTrue(final['stage_pass'])
        lam=0.;rho=1e4
        for r in rows:
            t=(rho-lam)/(2+2*rho);lam=lam+rho*(2*t-1);self.assertAlmostEqual(r['lam'][0],lam,places=12);rho=r['rho_next']
        self.assertAlmostEqual(final['lam'][0],-1.,places=6)

    def test_rho_increases_when_violation_stalls(self):
        rows,final=stage.run_stage(np.array([0.,0.]),np.zeros(1),np.zeros(1),1e-2,13,Frozen,inner,assess,state,1e-6,3,10)
        self.assertEqual([r['rho'] for r in rows],[1e-2,1e-2,1e-1]);self.assertEqual(rows[1]['rho_next'],1e-1)
        self.assertEqual(final['stop'],'outer_limit');self.assertEqual(final['completed_outer'],3)

    def test_inner_timeout_stops_without_update(self):
        def late(f,c,y,deadline,record):return dict(y=y,gradient=np.zeros(2),gradient_inf=0.,status='timeout')
        rows,final=stage.run_stage(np.array([.3,.3]),np.zeros(1),np.zeros(1),1e4,13,Frozen,late,assess,state,1e-6,600,10)
        self.assertEqual(rows,[]);self.assertEqual(final['stop'],'timeout');self.assertEqual(final['lam'],[0.])


if __name__=='__main__':unittest.main()
