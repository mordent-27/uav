"""Observe only the first iterate. Returning zero never requests termination."""
import casadi as ca
import numpy as np


class FirstPoint(ca.Callback):
    def __init__(self,name,nx,ng):
        ca.Callback.__init__(self);self.nx=nx;self.ng=ng;self.calls=0;self.point=None
        self.construct(name,{})
    def get_n_in(self):return ca.nlpsol_n_out()
    def get_n_out(self):return 1
    def get_name_in(self,i):return ca.nlpsol_out(i)
    def get_name_out(self,i):return 'ret'
    def get_sparsity_in(self,i):
        name=ca.nlpsol_out(i)
        if name=='f':return ca.Sparsity.scalar()
        if name in ('x','lam_x'):return ca.Sparsity.dense(self.nx)
        if name in ('g','lam_g'):return ca.Sparsity.dense(self.ng)
        return ca.Sparsity(0,0)
    def eval(self,args):
        if self.calls==0:self.point=np.array(args[ca.nlpsol_out().index('x')]).ravel().copy()
        self.calls+=1
        return [0]


def violation(model,point):
    _,values,_,_=model.evaluate(point);v=np.array(values).ravel()
    return float(max(0.,max(abs(v[:model.me])),max(v[model.me:],default=-np.inf),
        max(model.lb-point),max(point-model.ub)))
