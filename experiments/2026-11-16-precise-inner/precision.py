from decimal import Decimal as D,localcontext
from time import monotonic
import numpy as np
from reference import evaluate
from battery_reference import binary


def absolute_al(primal,metadata,digits):
    with localcontext() as ctx:
        ctx.prec=digits;value,eq,ineq=primal;rho=binary(metadata['rho'])
        value+=sum((binary(w)*v+rho*v*v/2 for w,v in zip(metadata['lam'],eq)),D(0))
        value+=sum(((max(D(0),binary(w)+rho*v)**2-binary(w)**2)/(2*rho)
            for w,v in zip(metadata['mu'],ineq)),D(0))
        return value


def central_gradient(function,point,digits,step,deadline=float('inf')):
    with localcontext() as ctx:
        ctx.prec=digits;point=[binary(v) for v in point];step=D(step);gradient=[]
        if step<=0:raise ValueError('positive difference step required')
        for i in range(len(point)):
            if monotonic()>=deadline:raise TimeoutError()
            plus=point.copy();plus[i]+=step;first=function(plus)
            if monotonic()>=deadline:raise TimeoutError()
            minus=point.copy();minus[i]-=step;second=function(minus)
            gradient.append((first-second)/(2*step))
        return gradient


class DecimalEvaluator:
    def __init__(self,metadata,digits=80,step='1e-20'):
        self.metadata=metadata;self.digits=digits;self.step=step;self.calls=0

    def scalar(self,point):
        self.calls+=1
        return absolute_al(evaluate(point,self.metadata,self.digits),self.metadata,self.digits)

    def __call__(self,point,deadline):
        if monotonic()>=deadline:raise TimeoutError()
        value=self.scalar(point)
        gradient=central_gradient(self.scalar,point,self.digits,self.step,deadline)
        return float(value),np.array([float(v) for v in gradient]),value
