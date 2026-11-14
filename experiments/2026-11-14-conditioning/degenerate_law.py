"""One-variable model of a smoothed disjunct: why the AL multiplier never settles.

minimise -F v  subject to  h(v) = sqrt(v^2 + eps^2) - eps = 0,
where v is the residual of the active disjunct (c on a discharging segment, c - s on a charging
one) and F > 0 is what one unit of residual is worth in the objective. h is what the paper's
smooth minimum reduces to when the other disjuncts are far away. Standard library only.
"""
import math


def inner(F, lam, rho, eps):
    """Exact minimiser of -F v + lam h + rho/2 h^2 over v >= 0 (the derivative is increasing)."""
    lo, hi = 0.0, 1.0
    slope = lambda v: -F + (lam + rho * (math.hypot(v, eps) - eps)) * v / math.hypot(v, eps)
    while slope(hi) < 0:
        hi *= 2
    for _ in range(200):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if slope(mid) < 0 else (lo, mid)
    return (lo + hi) / 2


def run(F, rho, eps, tol, limit=10**6):
    lam, trace = 0.0, []
    for k in range(1, limit + 1):
        v = inner(F, lam, rho, eps)
        h = math.hypot(v, eps) - eps
        lam += rho * h
        trace.append((k, v, h, lam))
        if h <= tol:
            break
    return trace


if __name__ == '__main__':
    eps, F, tol = 5e-4, 1.5, 1e-6
    print(f'eps {eps}, F {F}: multiplier needed for h <= {tol}: F*sqrt(eps/(2 tol)) = {F*math.sqrt(eps/(2*tol)):.1f}')
    print(f'residual at that point: v = sqrt(2 eps tol) = {math.sqrt(2*eps*tol):.2e} h = {math.sqrt(2*eps*tol)*3600:.2f} s')
    print('\nrho       outer iterations to h<=1e-6   predicted 2F sqrt(eps)/(3 rho (2 tol)^1.5)')
    for rho in (1e2, 1e3, 1e4, 1e5, 1e6, 1e8):
        t = run(F, rho, eps, tol)
        print(f'{rho:8.0e} {len(t):>12}                 {2*F*math.sqrt(eps)/(3*rho*(2*tol)**1.5):12.1f}')
    print('\nrho = 1e4: iteration, h, multiplier, predicted multiplier (1.5 rho eps F^2 k)^(1/3), h*lam^2/(eps F^2/2)')
    t = run(F, 1e4, eps, 0.0, limit=3000)
    for k in (1, 3, 10, 30, 100, 300, 1000, 3000):
        _, v, h, lam = t[k - 1]
        print(f'{k:>5} {h:.3e} {lam:8.3f} {(1.5*1e4*eps*F*F*k)**(1/3):8.3f} {h*lam*lam/(eps*F*F/2):.3f}')
    a, b = t[299], t[2999]
    print(f'slope of log h against log k between 300 and 3000: {math.log(b[2]/a[2])/math.log(10):.3f} (prediction -2/3)')
