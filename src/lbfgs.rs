//! Limited-memory BFGS with a strong-Wolfe line search (Nocedal & Wright, Alg. 7.4 / 3.5 / 3.6).

use std::collections::VecDeque;

#[derive(Clone, Debug)]
pub struct Opts {
    pub mem: usize,
    pub max_iter: usize,
    /// Stop when the infinity norm of the gradient is below this.
    pub gtol: f64,
    /// Stop after `stall` consecutive iterations with relative decrease below this.
    pub ftol: f64,
    pub stall: usize,
}

impl Default for Opts {
    fn default() -> Self {
        Opts { mem: 20, max_iter: 2000, gtol: 1e-6, ftol: 1e-14, stall: 10 }
    }
}

#[derive(Clone, Copy, Debug, PartialEq)]
pub enum Status {
    Converged,
    MaxIter,
    Stalled,
    LineSearchFailed,
}

#[derive(Clone, Copy, Debug)]
pub struct Outcome {
    pub f: f64,
    pub gnorm: f64,
    pub iters: usize,
    pub evals: usize,
    pub status: Status,
}

fn dot(a: &[f64], b: &[f64]) -> f64 {
    a.iter().zip(b).map(|(x, y)| x * y).sum()
}
fn inf_norm(a: &[f64]) -> f64 {
    a.iter().fold(0.0, |m, v| m.max(v.abs()))
}

const C1: f64 = 1e-4;
const C2: f64 = 0.9;

struct Line<'a, F> {
    fg: &'a mut F,
    x0: &'a [f64],
    d: &'a [f64],
    xt: &'a mut [f64],
    gt: &'a mut [f64],
    evals: usize,
}

impl<F: FnMut(&[f64], &mut [f64]) -> f64> Line<'_, F> {
    /// phi(a) and phi'(a); leaves the trial point and its gradient in xt / gt.
    fn at(&mut self, a: f64) -> (f64, f64) {
        for i in 0..self.x0.len() {
            self.xt[i] = self.x0[i] + a * self.d[i];
        }
        let f = (self.fg)(self.xt, self.gt);
        self.evals += 1;
        if f.is_finite() { (f, dot(self.gt, self.d)) } else { (f64::INFINITY, 0.0) }
    }
}

/// Minimiser of the cubic through (a, fa, da) and (b, fb, db), if it is usable.
fn cubic_min(a: f64, fa: f64, da: f64, b: f64, fb: f64, db: f64) -> Option<f64> {
    if !fb.is_finite() {
        return None;
    }
    let d1 = da + db - 3.0 * (fa - fb) / (a - b);
    let disc = d1 * d1 - da * db;
    if disc < 0.0 {
        return None;
    }
    let d2 = disc.sqrt() * (b - a).signum();
    let t = b - (b - a) * (db + d2 - d1) / (db - da + 2.0 * d2);
    t.is_finite().then_some(t)
}

/// Strong-Wolfe step. On success the accepted point and gradient are in xt / gt.
fn wolfe<F: FnMut(&[f64], &mut [f64]) -> f64>(
    ln: &mut Line<F>,
    f0: f64,
    dg0: f64,
    a_init: f64,
) -> Option<(f64, f64)> {
    let (mut a_prev, mut f_prev, mut d_prev) = (0.0, f0, dg0);
    let mut a = a_init;
    // Bracketing phase.
    let (mut lo, mut hi);
    let mut i = 0;
    loop {
        let (f, dphi) = ln.at(a);
        if f > f0 + C1 * a * dg0 || (i > 0 && f >= f_prev) {
            lo = (a_prev, f_prev, d_prev);
            hi = (a, f, dphi);
            break;
        }
        if dphi.abs() <= -C2 * dg0 {
            return Some((a, f));
        }
        if dphi >= 0.0 {
            lo = (a, f, dphi);
            hi = (a_prev, f_prev, d_prev);
            break;
        }
        (a_prev, f_prev, d_prev) = (a, f, dphi);
        a *= 3.0;
        i += 1;
        if i > 25 {
            return None;
        }
    }
    // Zoom phase: lo always satisfies sufficient decrease and has the lowest value so far.
    for _ in 0..40 {
        let width = hi.0 - lo.0;
        let mut t = cubic_min(lo.0, lo.1, lo.2, hi.0, hi.1, hi.2).unwrap_or(lo.0 + 0.5 * width);
        let (near, far) = (lo.0 + 0.1 * width, lo.0 + 0.9 * width);
        if !(t - near).is_finite() || (t - near) * (t - far) > 0.0 {
            t = lo.0 + 0.5 * width;
        }
        let (f, dphi) = ln.at(t);
        if f > f0 + C1 * t * dg0 || f >= lo.1 {
            hi = (t, f, dphi);
        } else {
            if dphi.abs() <= -C2 * dg0 {
                return Some((t, f));
            }
            if dphi * (hi.0 - lo.0) >= 0.0 {
                hi = lo;
            }
            lo = (t, f, dphi);
        }
        if (hi.0 - lo.0).abs() <= 1e-14 * lo.0.abs().max(1e-30) {
            break;
        }
    }
    // Accept the best sufficient-decrease point found, if it made progress.
    if lo.0 > 0.0 && lo.1 < f0 {
        let (f, _) = ln.at(lo.0);
        return Some((lo.0, f));
    }
    None
}

/// Minimise `fg` (returns the value and writes the gradient) starting from, and overwriting, x.
pub fn minimize<F: FnMut(&[f64], &mut [f64]) -> f64>(x: &mut [f64], mut fg: F, o: &Opts) -> Outcome {
    let n = x.len();
    let mut g = vec![0.0; n];
    let mut f = fg(x, &mut g);
    let mut evals = 1;
    let (mut xt, mut gt, mut d) = (vec![0.0; n], vec![0.0; n], vec![0.0; n]);
    let mut hist: VecDeque<(Vec<f64>, Vec<f64>, f64)> = VecDeque::with_capacity(o.mem);
    let mut alpha_buf = vec![0.0; o.mem];
    let mut stalled = 0;
    let mut iters = 0;

    let status = loop {
        let gnorm = inf_norm(&g);
        if gnorm <= o.gtol {
            break Status::Converged;
        }
        if iters >= o.max_iter {
            break Status::MaxIter;
        }

        // Two-loop recursion: d = -H g.
        d.copy_from_slice(&g);
        for (i, (s, y, rho)) in hist.iter().enumerate().rev() {
            let a = rho * dot(s, &d);
            alpha_buf[i] = a;
            for j in 0..n {
                d[j] -= a * y[j];
            }
        }
        if let Some((s, y, _)) = hist.back() {
            let gamma = dot(s, y) / dot(y, y);
            d.iter_mut().for_each(|v| *v *= gamma);
        }
        for (i, (s, y, rho)) in hist.iter().enumerate() {
            let b = rho * dot(y, &d);
            for j in 0..n {
                d[j] += (alpha_buf[i] - b) * s[j];
            }
        }
        d.iter_mut().for_each(|v| *v = -*v);

        let mut dg = dot(&g, &d);
        if !(dg < 0.0) {
            hist.clear();
            for j in 0..n {
                d[j] = -g[j];
            }
            dg = -dot(&g, &g);
        }
        let a_init = if hist.is_empty() { 1.0 / dot(&g, &g).sqrt().max(1.0) } else { 1.0 };

        let mut ln = Line { fg: &mut fg, x0: x, d: &d, xt: &mut xt, gt: &mut gt, evals: 0 };
        let step = wolfe(&mut ln, f, dg, a_init);
        evals += ln.evals;
        let Some((_, f_new)) = step else {
            if hist.is_empty() {
                break Status::LineSearchFailed;
            }
            // The quasi-Newton model may be poor; retry once along steepest descent.
            hist.clear();
            continue;
        };

        let mut s: Vec<f64> = (0..n).map(|j| xt[j] - x[j]).collect();
        let mut y: Vec<f64> = (0..n).map(|j| gt[j] - g[j]).collect();
        let sy = dot(&s, &y);
        if sy > 1e-12 * dot(&s, &s).sqrt() * dot(&y, &y).sqrt() {
            if hist.len() == o.mem {
                let (ps, py, _) = hist.pop_front().unwrap();
                // Reuse the allocations of the evicted pair.
                let (mut ps, mut py) = (ps, py);
                ps.copy_from_slice(&s);
                py.copy_from_slice(&y);
                (s, y) = (ps, py);
            }
            hist.push_back((s, y, 1.0 / sy));
        }

        let decrease = f - f_new;
        x.copy_from_slice(&xt);
        g.copy_from_slice(&gt);
        f = f_new;
        iters += 1;
        if decrease <= o.ftol * f.abs().max(1.0) {
            stalled += 1;
            if stalled >= o.stall {
                break Status::Stalled;
            }
        } else {
            stalled = 0;
        }
    };
    Outcome { f, gnorm: inf_norm(&g), iters, evals, status }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn rosenbrock() {
        let n = 20;
        let mut x = vec![-1.2; n];
        let out = minimize(
            &mut x,
            |x, g| {
                g.iter_mut().for_each(|v| *v = 0.0);
                let mut f = 0.0;
                for i in 0..x.len() - 1 {
                    let (a, b) = (1.0 - x[i], x[i + 1] - x[i] * x[i]);
                    f += a * a + 100.0 * b * b;
                    g[i] += -2.0 * a - 400.0 * b * x[i];
                    g[i + 1] += 200.0 * b;
                }
                f
            },
            &Opts { gtol: 1e-8, ..Opts::default() },
        );
        assert_eq!(out.status, Status::Converged, "{out:?}");
        assert!(x.iter().all(|v| (v - 1.0).abs() < 1e-6), "{x:?}");
    }
}
