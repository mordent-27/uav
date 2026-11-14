//! Problem data and algorithm parameters.
//!
//! Units follow the paper's simulation section: km, hours, battery as a fraction of capacity.

pub type V2 = [f64; 2];

#[inline]
pub fn sub(a: V2, b: V2) -> V2 {
    [a[0] - b[0], a[1] - b[1]]
}
#[inline]
pub fn norm(a: V2) -> f64 {
    (a[0] * a[0] + a[1] * a[1]).sqrt()
}
#[inline]
pub fn dist(a: V2, b: V2) -> f64 {
    norm(sub(a, b))
}

/// Physical parameters (Section IV-A).
#[derive(Clone, Debug)]
pub struct Phys {
    pub e_max: f64,
    pub e_th: f64,
    pub e_min: f64,
    /// Maximum UAV speed [km/h].
    pub v_d: f64,
    /// Maximum charging-station speed [km/h].
    pub v_c: f64,
    /// Charging rate in the CC phase [1/h].
    pub kappa: f64,
    /// Discharging rate [1/h].
    pub zeta: f64,
    pub s_min: f64,
    pub s_max: f64,
}

impl Default for Phys {
    fn default() -> Self {
        Phys {
            e_max: 1.0,
            e_th: 0.7,
            e_min: 0.0,
            v_d: 36.0,
            v_c: 10.8,
            kappa: 4.625,
            zeta: 2.5,
            s_min: 30.0 / 3600.0,
            s_max: 1.0,
        }
    }
}

impl Phys {
    /// Time constant of the CV phase, chosen for slope continuity at the CC-CV transition.
    #[inline]
    pub fn sigma(&self) -> f64 {
        (self.e_max - self.e_th) / self.kappa
    }
}

/// Circular charging region: center `o`, radius `rho`.
#[derive(Clone, Debug)]
pub struct Region {
    pub o: V2,
    pub rho: f64,
}

#[derive(Clone, Debug)]
pub struct Instance {
    pub r0: V2,
    pub rf: V2,
    pub regions: Vec<Region>,
    pub tasks: Vec<V2>,
}

/// Smoothing parameters of one homotopy stage.
#[derive(Clone, Copy, Debug)]
pub struct Smooth {
    pub eps: f64,
    pub p: f64,
    pub delta: f64,
}

/// Algorithm 1 parameters.
#[derive(Clone, Debug)]
pub struct Homotopy {
    pub eps0: f64,
    pub p0: f64,
    pub alpha: f64,
    pub beta: f64,
    pub eps_min: f64,
    pub p_max: f64,
    pub delta: f64,
    /// Number of homotopy stages L. Not given in the paper; 13 is the smallest value for which
    /// both eps and p reach their bounds (eps needs 12 updates, p needs 10).
    pub stages: usize,
}

impl Default for Homotopy {
    fn default() -> Self {
        Homotopy {
            eps0: 0.2,
            p0: 2.0,
            alpha: 1.2,
            beta: 0.6,
            eps_min: 5e-4,
            p_max: 12.0,
            delta: 1e-3,
            stages: 13,
        }
    }
}

impl Homotopy {
    pub fn schedule(&self) -> Vec<Smooth> {
        let mut v = Vec::with_capacity(self.stages);
        let (mut eps, mut p) = (self.eps0, self.p0);
        for _ in 0..self.stages {
            v.push(Smooth { eps, p, delta: self.delta });
            eps = (self.beta * eps).max(self.eps_min);
            p = (self.alpha * p).min(self.p_max);
        }
        v
    }
}
