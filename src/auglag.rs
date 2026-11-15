//! Augmented Lagrangian method (Rockafellar's form for inequalities) with L-BFGS inner solves.

use crate::lbfgs;
use crate::model::{Model, Recorder, Weights};

#[derive(Clone, Debug)]
pub struct Opts {
    pub rho0: f64,
    pub rho_mult: f64,
    pub rho_max: f64,
    /// The penalty grows when the violation fails to shrink by this factor.
    pub shrink: f64,
    pub max_outer: usize,
    /// Tolerances on the KKT residuals: stationarity, feasibility and complementarity.
    pub tol_stat: f64,
    pub tol_feas: f64,
    pub inner: lbfgs::Opts,
    /// Print one line per outer iteration to stderr.
    pub debug: bool,
}

impl Default for Opts {
    fn default() -> Self {
        Opts {
            rho0: 10.0,
            rho_mult: 10.0,
            rho_max: 1e8,
            shrink: 0.25,
            max_outer: 30,
            tol_stat: 1e-6,
            tol_feas: 1e-6,
            inner: lbfgs::Opts::default(),
            debug: false,
        }
    }
}

/// Multipliers and penalty, carried from one homotopy stage to the next.
#[derive(Clone, Debug)]
pub struct State {
    pub lam: Vec<f64>,
    pub mu: Vec<f64>,
    pub rho: f64,
}

impl State {
    pub fn new(n_eq: usize, n_ineq: usize, rho: f64) -> Self {
        State { lam: vec![0.0; n_eq], mu: vec![0.0; n_ineq], rho }
    }
}

/// Weights of the augmented Lagrangian
///   f + sum_i (lam_i h_i + rho/2 h_i^2) + 1/(2 rho) sum_j (max(0, mu_j + rho g_j)^2 - mu_j^2).
struct AlSink<'a> {
    lam: &'a [f64],
    mu: &'a [f64],
    rho: f64,
    val: f64,
}

impl Weights for AlSink<'_> {
    #[inline]
    fn eq(&mut self, i: usize, v: f64) -> f64 {
        self.val += (self.lam[i] + 0.5 * self.rho * v) * v;
        self.lam[i] + self.rho * v
    }
    #[inline]
    fn ineq(&mut self, i: usize, v: f64) -> f64 {
        let t = (self.mu[i] + self.rho * v).max(0.0);
        self.val += (t * t - self.mu[i] * self.mu[i]) / (2.0 * self.rho);
        t
    }
}

#[derive(Clone, Copy, Debug, Default)]
pub struct Kkt {
    /// || grad f + sum lam grad h + sum mu grad g ||_inf
    pub stat: f64,
    /// max(|h|, g^+)
    pub feas: f64,
    /// max_j |min(mu_j, -g_j)|
    pub comp: f64,
}

/// KKT residuals at x; the stationarity residual is measured in the scaled variables y = x / d.
pub fn kkt(model: &Model, x: &[f64], st: &State, d: &[f64], grad: &mut [f64]) -> (f64, Kkt) {
    let mut rec = Recorder::new(&st.lam, &st.mu);
    let f = model.eval(x, &mut rec, grad);
    let stat = grad.iter().zip(d).fold(0.0f64, |m, (g, d)| m.max((g * d).abs()));
    let feas = rec.h.iter().fold(0.0f64, |m, v| m.max(v.abs()));
    let feas = rec.g.iter().fold(feas, |m, v| m.max(*v));
    let comp = rec.g.iter().zip(&st.mu).fold(0.0f64, |m, (g, mu)| m.max(mu.min(-g).abs()));
    (f, Kkt { stat, feas, comp })
}

#[derive(Clone, Copy, Debug, Default)]
pub struct Outcome {
    pub f: f64,
    pub kkt: Kkt,
    pub outer: usize,
    pub inner_iters: usize,
    pub evals: usize,
    pub converged: bool,
}

fn should_increase_penalty(violation: f64, previous: f64, o: &Opts) -> bool {
    // Once feasibility/complementarity are acceptable, a stationarity failure is
    // an inner-solve issue; a larger penalty can make that solve harder.
    violation > o.tol_feas && violation > o.shrink * previous
}

pub fn solve(model: &Model, x: &mut [f64], st: &mut State, o: &Opts) -> Outcome {
    let mut out = Outcome::default();
    let n = x.len();
    let d = model.var_scale();
    let mut grad = vec![0.0; n];
    let mut y: Vec<f64> = x.iter().zip(&d).map(|(x, d)| x / d).collect();
    let mut xs = vec![0.0; n];
    let mut prev_viol = f64::INFINITY;
    for outer in 1..=o.max_outer {
        out.outer = outer;
        let (lam, mu, rho) = (&st.lam, &st.mu, st.rho);
        // Inner solve in the scaled variables y, with x = d * y.
        let res = lbfgs::minimize(
            &mut y,
            |y, g| {
                for j in 0..n {
                    xs[j] = d[j] * y[j];
                }
                let mut sink = AlSink { lam, mu, rho, val: 0.0 };
                let f = model.eval(&xs, &mut sink, g);
                for j in 0..n {
                    g[j] *= d[j];
                }
                f + sink.val
            },
            &lbfgs::Opts { gtol: o.tol_stat, ..o.inner.clone() },
        );
        if o.debug && res.status == lbfgs::Status::LineSearchFailed {
            // Compare the analytic gradient with central differences at the failure point.
            let mut al = |y: &[f64], g: &mut [f64]| {
                let xs: Vec<f64> = (0..n).map(|j| d[j] * y[j]).collect();
                let mut sink = AlSink { lam, mu, rho, val: 0.0 };
                let f = model.eval(&xs, &mut sink, g);
                for j in 0..n {
                    g[j] *= d[j];
                }
                f + sink.val
            };
            let mut g0 = vec![0.0; n];
            let mut tmp = vec![0.0; n];
            al(&y, &mut g0);
            let mut yy = y.clone();
            let mut bad: Vec<(f64, usize, f64, f64)> = vec![];
            for j in 0..n {
                let h = 1e-7 * yy[j].abs().max(1e-3);
                let y0 = yy[j];
                yy[j] = y0 + h;
                let fp = al(&yy, &mut tmp);
                yy[j] = y0 - h;
                let fm = al(&yy, &mut tmp);
                yy[j] = y0;
                let fd = (fp - fm) / (2.0 * h);
                bad.push(((fd - g0[j]).abs() / (1.0 + fd.abs()), j, g0[j], fd));
            }
            bad.sort_by(|a, b| b.0.total_cmp(&a.0));
            for (err, j, ga, fd) in bad.iter().take(5) {
                eprintln!("      FD check var {j}: analytic {ga:.6e} fd {fd:.6e} rel err {err:.2e} (x = {:.6e})", d[*j] * y[*j]);
            }
        }
        for j in 0..n {
            x[j] = d[j] * y[j];
        }
        out.inner_iters += res.iters;
        out.evals += res.evals;
        if o.debug {
            eprintln!(
                "    outer {outer:>2} rho {:.1e}  lbfgs {:?} iters {} evals {} L {:.6} |g| {:.2e}",
                st.rho, res.status, res.iters, res.evals, res.f, res.gnorm
            );
        }

        // First-order multiplier update.
        let zeros_eq = vec![0.0; st.lam.len()];
        let zeros_in = vec![0.0; st.mu.len()];
        let mut rec = Recorder::new(&zeros_eq, &zeros_in);
        model.eval(x, &mut rec, &mut grad);
        for (l, h) in st.lam.iter_mut().zip(&rec.h) {
            *l += st.rho * h;
        }
        for (m, g) in st.mu.iter_mut().zip(&rec.g) {
            *m = (*m + st.rho * g).max(0.0);
        }

        let (f, k) = kkt(model, x, st, &d, &mut grad);
        out.f = f;
        out.kkt = k;
        if o.debug {
            eprintln!("             f {f:.6} stat {:.2e} feas {:.2e} comp {:.2e}", k.stat, k.feas, k.comp);
        }
        if k.stat <= o.tol_stat && k.feas <= o.tol_feas && k.comp <= o.tol_feas {
            out.converged = true;
            break;
        }
        let viol = k.feas.max(k.comp);
        if should_increase_penalty(viol, prev_viol, o) {
            st.rho = (st.rho * o.rho_mult).min(o.rho_max);
        }
        prev_viol = viol;
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn stage2_feasible_point_does_not_raise_penalty_for_stationarity() {
        // Recorded adaptive stage-2 iteration 5: increasing rho here sent the
        // solver to rho=1e8; keeping it at 1e6 reached KKT two iterations later.
        let o = Opts::default();
        let k = Kkt { stat: 1.156831326278492e-6, feas: 6.064224474661151e-7, comp: 5.772324482775093e-7 };
        let previous = 1.9825603809892067e-6;
        let violation = k.feas.max(k.comp);
        assert!(k.stat > o.tol_stat);
        assert!(violation > o.shrink * previous);
        assert!(!should_increase_penalty(violation, previous, &o));
        assert!(!should_increase_penalty(o.tol_feas, previous, &o));
    }

    #[test]
    fn unsatisfied_complementarity_still_uses_progress_rule() {
        let o = Opts::default();
        let k = Kkt { stat: 1e-8, feas: 1e-8, comp: 2e-6 };
        assert!(should_increase_penalty(k.feas.max(k.comp), 4e-6, &o));
        assert!(!should_increase_penalty(k.feas.max(k.comp), 1e-5, &o));
        assert!(!should_increase_penalty(k.feas.max(k.comp), f64::INFINITY, &o));
    }
}
