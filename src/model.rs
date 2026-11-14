//! Smooth NLP (23): objective, constraints (11) and the l_p smooth-min approximation of (17).
//!
//! Decision vector x (fixed r_1, r_N and e_1 are eliminated):
//!   r_k for k = 1..N-2 (0-based stamps), e_k for k = 1..N-1, s_k and c_k for k = 0..N-2.
//!
//! Equalities:   dynamics (N-1), task visits (tau), charge/discharge mode (N-1).
//! Inequalities: speed, e lower/upper, s lower/upper, c >= 0   (N-1 each), written as g <= 0.

use crate::battery::charge;
use crate::params::*;

/// Receives each constraint value and returns the weight its gradient gets in the output
/// gradient. One pass over the model then yields grad f + sum_i w_i grad c_i.
pub trait Weights {
    fn eq(&mut self, i: usize, v: f64) -> f64;
    fn ineq(&mut self, i: usize, v: f64) -> f64;
}

#[derive(Clone, Copy, Debug)]
pub struct Layout {
    /// Number of time stamps N.
    pub n: usize,
    pub tau: usize,
}

impl Layout {
    pub fn n_var(&self) -> usize {
        2 * (self.n - 2) + 3 * (self.n - 1)
    }
    pub fn n_eq(&self) -> usize {
        2 * (self.n - 1) + self.tau
    }
    pub fn n_ineq(&self) -> usize {
        6 * (self.n - 1)
    }
    /// Index of r_k's x-coordinate, None for the fixed end points.
    #[inline]
    pub fn r(&self, k: usize) -> Option<usize> {
        (k >= 1 && k + 1 < self.n).then(|| 2 * (k - 1))
    }
    /// Index of e_k, None for the fixed e_0.
    #[inline]
    pub fn e(&self, k: usize) -> Option<usize> {
        (k >= 1).then(|| 2 * (self.n - 2) + k - 1)
    }
    #[inline]
    pub fn s(&self, k: usize) -> usize {
        2 * (self.n - 2) + (self.n - 1) + k
    }
    #[inline]
    pub fn c(&self, k: usize) -> usize {
        2 * (self.n - 2) + 2 * (self.n - 1) + k
    }
    pub fn eq_dyn(&self, k: usize) -> usize {
        k
    }
    pub fn eq_task(&self, i: usize) -> usize {
        self.n - 1 + i
    }
    pub fn eq_mode(&self, k: usize) -> usize {
        self.n - 1 + self.tau + k
    }
}

/// Smooth approximation (19) of min_i z_i for z_i > 0. Writes d phi / d z_i into `d`.
pub fn smooth_min(z: &[f64], p: f64, d: &mut [f64]) -> f64 {
    let zmin = z.iter().cloned().fold(f64::INFINITY, f64::min);
    let sum: f64 = z.iter().map(|&zi| (zmin / zi).powf(p)).sum();
    let phi = zmin * sum.powf(-1.0 / p);
    for (di, &zi) in d.iter_mut().zip(z) {
        *di = (phi / zi).powf(p + 1.0);
    }
    phi
}

/// Smooth violation measure (18) of y <= 0. Returns (psi, psi').
#[inline]
pub fn psi(y: f64, delta: f64) -> (f64, f64) {
    if y <= -delta {
        (0.0, 0.0)
    } else if y <= delta {
        let t = y + delta;
        (t * t / (4.0 * delta), t / (2.0 * delta))
    } else {
        (y, 1.0)
    }
}

pub struct Model<'a> {
    pub inst: &'a Instance,
    pub ph: &'a Phys,
    pub lay: Layout,
    pub sm: Smooth,
}

impl<'a> Model<'a> {
    pub fn new(inst: &'a Instance, ph: &'a Phys, n_stamps: usize, sm: Smooth) -> Self {
        Model { inst, ph, lay: Layout { n: n_stamps, tau: inst.tasks.len() }, sm }
    }

    #[inline]
    pub fn pos(&self, x: &[f64], k: usize) -> V2 {
        match self.lay.r(k) {
            Some(i) => [x[i], x[i + 1]],
            None if k == 0 => self.inst.r0,
            None => self.inst.rf,
        }
    }
    #[inline]
    pub fn energy(&self, x: &[f64], k: usize) -> f64 {
        self.lay.e(k).map_or(self.ph.e_max, |i| x[i])
    }
    #[inline]
    fn add_r(&self, grad: &mut [f64], k: usize, w: f64, g: V2) {
        if let Some(i) = self.lay.r(k) {
            grad[i] += w * g[0];
            grad[i + 1] += w * g[1];
        }
    }

    /// Typical size of each variable, used to precondition the solver: positions in km, and
    /// durations and battery levels converted to the km they are worth at full speed.
    pub fn var_scale(&self) -> Vec<f64> {
        let lay = self.lay;
        let mut d = vec![1.0; lay.n_var()];
        for k in 0..lay.n {
            if let Some(i) = lay.e(k) {
                d[i] = self.ph.zeta / self.ph.v_d;
            }
        }
        for k in 0..lay.n - 1 {
            d[lay.s(k)] = 1.0 / self.ph.v_d;
            d[lay.c(k)] = 1.0 / self.ph.v_d;
        }
        d
    }

    /// Returns the objective (1) and sets grad = grad f + sum_i w_i grad c_i, with w_i from `w`.
    pub fn eval<W: Weights>(&self, x: &[f64], w: &mut W, grad: &mut [f64]) -> f64 {
        let (lay, ph, sm) = (self.lay, self.ph, self.sm);
        let n = lay.n;
        let nseg = n - 1;
        grad.iter_mut().for_each(|g| *g = 0.0);

        // Objective: total mission time.
        let mut f = 0.0;
        for k in 0..nseg {
            f += x[lay.s(k)];
            grad[lay.s(k)] += 1.0;
        }

        // Battery dynamics: e_{k+1} - f_c(e_k, c_k) + zeta (s_k - c_k) = 0, expressed in km of
        // flight range so that its size is comparable to the position constraints.
        let range = ph.v_d / ph.zeta;
        for k in 0..nseg {
            let (e0, e1) = (self.energy(x, k), self.energy(x, k + 1));
            let (s, c) = (x[lay.s(k)], x[lay.c(k)]);
            let (fc, dfe, dfc) = charge(ph, e0, c);
            let wt = range * w.eq(lay.eq_dyn(k), range * (e1 - fc + ph.zeta * (s - c)));
            if let Some(i) = lay.e(k + 1) {
                grad[i] += wt;
            }
            if let Some(i) = lay.e(k) {
                grad[i] -= wt * dfe;
            }
            grad[lay.s(k)] += wt * ph.zeta;
            grad[lay.c(k)] -= wt * (dfc + ph.zeta);
        }

        // Task visits: phi_p over all stamps of || [r_k - a_i ; eps] || equals eps.
        let mut z = vec![0.0; n.max(self.inst.regions.len() + 1)];
        let mut dz = vec![0.0; z.len()];
        for (i, &a) in self.inst.tasks.iter().enumerate() {
            for k in 0..n {
                let d = sub(self.pos(x, k), a);
                z[k] = (d[0] * d[0] + d[1] * d[1] + sm.eps * sm.eps).sqrt();
            }
            let phi = smooth_min(&z[..n], sm.p, &mut dz[..n]);
            let wt = w.eq(lay.eq_task(i), phi - sm.eps);
            for k in 1..n - 1 {
                let d = sub(self.pos(x, k), a);
                self.add_r(grad, k, wt * dz[k] / z[k], d);
            }
        }

        // Mode: discharge (c = 0) or charge in region j (c = s and g_j <= 0).
        let nj = self.inst.regions.len();
        // Per region: psi*psi' for the three components of g_j, and the unit vectors they act on.
        let mut pp = vec![[0.0f64; 3]; nj];
        let mut u = vec![[[0.0f64; 2]; 2]; nj];
        for k in 0..nseg {
            let (ra, rb) = (self.pos(x, k), self.pos(x, k + 1));
            let (s, c) = (x[lay.s(k)], x[lay.c(k)]);
            let dab = sub(ra, rb);
            let lab = norm(dab);
            let (p3, dp3) = psi(lab - ph.v_c * s, sm.delta);
            let u3 = if lab > 0.0 { [dab[0] / lab, dab[1] / lab] } else { [0.0, 0.0] };
            z[0] = (c * c + sm.eps * sm.eps).sqrt();
            for (j, reg) in self.inst.regions.iter().enumerate() {
                let (da, db) = (sub(ra, reg.o), sub(rb, reg.o));
                let (la, lb) = (norm(da), norm(db));
                let (p1, dp1) = psi(la - reg.rho, sm.delta);
                let (p2, dp2) = psi(lb - reg.rho, sm.delta);
                z[j + 1] =
                    ((c - s) * (c - s) + p1 * p1 + p2 * p2 + p3 * p3 + sm.eps * sm.eps).sqrt();
                pp[j] = [p1 * dp1, p2 * dp2, p3 * dp3];
                u[j][0] = if la > 0.0 { [da[0] / la, da[1] / la] } else { [0.0, 0.0] };
                u[j][1] = if lb > 0.0 { [db[0] / lb, db[1] / lb] } else { [0.0, 0.0] };
            }
            let phi = smooth_min(&z[..nj + 1], sm.p, &mut dz[..nj + 1]);
            let wt = w.eq(lay.eq_mode(k), phi - sm.eps);
            grad[lay.c(k)] += wt * dz[0] * c / z[0];
            for j in 0..nj {
                let q = wt * dz[j + 1] / z[j + 1];
                grad[lay.c(k)] += q * (c - s);
                grad[lay.s(k)] += q * (-(c - s) - pp[j][2] * ph.v_c);
                self.add_r(grad, k, q * pp[j][0], u[j][0]);
                self.add_r(grad, k + 1, q * pp[j][1], u[j][1]);
                self.add_r(grad, k, q * pp[j][2], u3);
                self.add_r(grad, k + 1, -q * pp[j][2], u3);
            }
        }

        // Inequalities, each written as g <= 0.
        let v2 = ph.v_d * ph.v_d;
        for k in 0..nseg {
            let (s, c) = (x[lay.s(k)], x[lay.c(k)]);
            // Speed, squared to stay smooth: ||r_{k+1} - r_k||^2 - v_d^2 s_k |s_k| <= 0.
            // For s_k >= 0 this is the paper's squared form. Written with s_k^2 it would also
            // hold for negative durations, which lower the objective and trap the solver; the
            // signed square keeps the constraint violated there and is still C^1.
            let d = sub(self.pos(x, k + 1), self.pos(x, k));
            let wt = w.ineq(k, d[0] * d[0] + d[1] * d[1] - v2 * s * s.abs());
            self.add_r(grad, k + 1, 2.0 * wt, d);
            self.add_r(grad, k, -2.0 * wt, d);
            grad[lay.s(k)] -= 2.0 * wt * v2 * s.abs();
            // Simple bounds, expressed like the dynamics in km of flight so that one penalty
            // parameter fits all constraints.
            // Battery bounds on e_{k+1}.
            let e1 = self.energy(x, k + 1);
            let ie = lay.e(k + 1).unwrap();
            grad[ie] -= range * w.ineq(nseg + k, range * (ph.e_min - e1));
            grad[ie] += range * w.ineq(2 * nseg + k, range * (e1 - ph.e_max));
            // Segment duration bounds.
            grad[lay.s(k)] -= ph.v_d * w.ineq(3 * nseg + k, ph.v_d * (ph.s_min - s));
            grad[lay.s(k)] += ph.v_d * w.ineq(4 * nseg + k, ph.v_d * (s - ph.s_max));
            // Domain of the charging duration (Section II-A).
            grad[lay.c(k)] -= ph.v_d * w.ineq(5 * nseg + k, -ph.v_d * c);
        }
        f
    }
}

/// Weights that are fixed in advance; `val` accumulates sum_i w_i c_i and the raw constraint
/// values are recorded. Used for KKT residuals and gradient checks.
pub struct Recorder<'a> {
    pub w_eq: &'a [f64],
    pub w_ineq: &'a [f64],
    pub h: Vec<f64>,
    pub g: Vec<f64>,
    pub val: f64,
}

impl<'a> Recorder<'a> {
    pub fn new(w_eq: &'a [f64], w_ineq: &'a [f64]) -> Self {
        Recorder { w_eq, w_ineq, h: vec![0.0; w_eq.len()], g: vec![0.0; w_ineq.len()], val: 0.0 }
    }
}

impl Weights for Recorder<'_> {
    fn eq(&mut self, i: usize, v: f64) -> f64 {
        self.h[i] = v;
        self.val += self.w_eq[i] * v;
        self.w_eq[i]
    }
    fn ineq(&mut self, i: usize, v: f64) -> f64 {
        self.g[i] = v;
        self.val += self.w_ineq[i] * v;
        self.w_ineq[i]
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::instance;
    use crate::rng::Rng;

    #[test]
    fn smooth_min_bounds_and_gradient() {
        let z = [0.3, 0.5, 0.31, 2.0];
        let mut d = [0.0; 4];
        for p in [2.0, 6.0, 12.0] {
            let phi = smooth_min(&z, p, &mut d);
            assert!(phi <= 0.3 && phi > 0.3 * (4.0f64).powf(-1.0 / p));
            for i in 0..4 {
                let h = 1e-6;
                let (mut zp, mut zm) = (z, z);
                zp[i] += h;
                zm[i] -= h;
                let mut tmp = [0.0; 4];
                let fd = (smooth_min(&zp, p, &mut tmp) - smooth_min(&zm, p, &mut tmp)) / (2.0 * h);
                assert!((fd - d[i]).abs() < 1e-7, "p={p} i={i}: {fd} vs {}", d[i]);
            }
        }
    }

    /// The analytic gradient of f + sum_i w_i c_i must match central differences.
    #[test]
    fn gradient_matches_finite_differences() {
        let ph = Phys::default();
        let inst = instance::fig1();
        let mut rng = Rng::new(7);
        for sm in [
            Smooth { eps: 0.2, p: 2.0, delta: 1e-3 },
            Smooth { eps: 0.01, p: 6.0, delta: 1e-3 },
        ] {
            let x0 = instance::initial_trajectory(&inst, &ph, &instance::InitOpts::default());
            let n_stamps = x0.r.len();
            let model = Model::new(&inst, &ph, n_stamps, sm);
            let mut x = x0.to_x(&model.lay);
            // Perturb so that no term sits exactly on a kink or at a zero-length segment.
            for v in x.iter_mut() {
                *v += 0.05 * (rng.uniform() - 0.5);
            }
            let w_eq: Vec<f64> = (0..model.lay.n_eq()).map(|_| rng.uniform() - 0.5).collect();
            let w_in: Vec<f64> = (0..model.lay.n_ineq()).map(|_| rng.uniform()).collect();
            let lag = |x: &[f64], grad: &mut [f64]| {
                let mut rec = Recorder::new(&w_eq, &w_in);
                let f = model.eval(x, &mut rec, grad);
                f + rec.val
            };
            let mut g = vec![0.0; x.len()];
            lag(&x, &mut g);
            let mut scratch = vec![0.0; x.len()];
            let mut worst = 0.0f64;
            for i in 0..x.len() {
                let h = 1e-6;
                let xi = x[i];
                x[i] = xi + h;
                let fp = lag(&x, &mut scratch);
                x[i] = xi - h;
                let fm = lag(&x, &mut scratch);
                x[i] = xi;
                let fd = (fp - fm) / (2.0 * h);
                let err = (fd - g[i]).abs() / (1.0 + fd.abs());
                worst = worst.max(err);
                assert!(err < 1e-5, "var {i}: analytic {} vs fd {fd} (eps={})", g[i], sm.eps);
            }
            eprintln!("eps={} p={}: worst relative gradient error {worst:.2e}", sm.eps, sm.p);
        }
    }
}
