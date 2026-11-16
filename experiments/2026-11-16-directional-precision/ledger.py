"""Decompose the same PHR AL difference using native constraints and Jacobian."""
import numpy as np


def decompose(delta,h0,g0,h1,g1,lam,mu,rho,gf,jac):
    ld=np.longdouble
    delta,h0,g0,h1,g1,lam,mu,gf,jac=[np.asarray(a,dtype=ld) for a in (delta,h0,g0,h1,g1,lam,mu,gf,jac)]
    rho=ld(rho);dh=h1-h0;dg=g1-g0
    le=lam+rho*h0;shift0=mu+rho*g0;shift1=mu+rho*g1;mi=np.maximum(0,shift0)
    both=(shift0>0)&(shift1>0)
    inequality=np.empty_like(dg)
    inequality[both]=dg[both]*(mu[both]+rho*(g1[both]+g0[both])/2)
    inequality[~both]=(np.maximum(0,shift1[~both])**2-np.maximum(0,shift0[~both])**2)/(2*rho)
    linear_h=jac[:len(h0)]@delta;linear_g=jac[len(h0):]@delta
    eq_residual=le*(dh-linear_h);ineq_residual=mi*(dg-linear_g)
    objective=gf@delta;equalities=dh*(lam+rho*(h1+h0)/2)
    linear=objective+le@linear_h+mi@linear_g
    eq_quadratic=rho*(dh@dh)/2
    ineq_remainder=np.sum(inequality)-mi@dg
    stable=objective+np.sum(equalities)+np.sum(inequality)
    reconstructed=linear+np.sum(eq_residual)+np.sum(ineq_residual)+eq_quadratic+ineq_remainder
    def top(a):
        return [dict(index=int(i),contribution=float(a[i])) for i in np.argsort(np.abs(a))[-5:][::-1]]
    return dict(stable=float(stable),objective=float(objective),equalities=float(np.sum(equalities)),
        inequalities=float(np.sum(inequality)),jacobian_linear=float(linear),
        weighted_equality_residual=float(np.sum(eq_residual)),weighted_inequality_residual=float(np.sum(ineq_residual)),
        equality_penalty_quadratic=float(eq_quadratic),inequality_nonlinear_remainder=float(ineq_remainder),
        reconstruction_error=float(stable-reconstructed),
        largest_weighted_equality_residuals=top(eq_residual),largest_weighted_inequality_residuals=top(ineq_residual))
