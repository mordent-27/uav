"""Frozen-multiplier directional curvature; no full Hessian is formed here."""
import numpy as np


class DirectionalCurvature:
    def __init__(self,frozen,y,step=1e-7):
        self.f=frozen;self.y=np.array(y,copy=True);self.step=step
        m=frozen.m;m.eval(self.y,frozen.lam,frozen.mu,frozen.rho)
        self.le=frozen.lam+frozen.rho*m.h.copy()
        shifted=frozen.mu+frozen.rho*m.g.copy();self.mi=np.maximum(0.,shifted)
        jac=m.jacobian(self.y)
        self.J=jac[:m.me].copy();self.G=jac[m.me:][shifted>0].copy()
    def matvec(self,v):
        v=np.asarray(v);norm=float(np.linalg.norm(v))
        if norm==0:return np.zeros_like(v)
        t=self.step/norm;m=self.f.m
        a=m.eval(self.y+t*v,self.le,self.mi,0.)[1].copy()
        b=m.eval(self.y-t*v,self.le,self.mi,0.)[1].copy()
        return (a-b)/(2*t)+self.f.rho*(self.J.T@(self.J@v)+self.G.T@(self.G@v))
