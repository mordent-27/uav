//! Problem instances and the warm-start trajectory.

use crate::battery::{charge, time_to_charge};
use crate::model::Layout;
use crate::params::*;
use crate::rng::Rng;

/// Charging regions and end points of Fig. 1. The paper gives no numbers; these were read from
/// the vector data of the figure and are round to the extraction precision (about 1e-3 km).
pub fn base() -> Instance {
    Instance {
        r0: [-3.5, 3.5],
        rf: [-5.0, -7.0],
        regions: vec![
            Region { o: [-3.5, 3.5], rho: 1.5 },
            Region { o: [1.5, -2.0], rho: 2.5 },
            Region { o: [8.0, -5.0], rho: 1.5 },
            Region { o: [-5.0, -7.0], rho: 1.5 },
        ],
        tasks: vec![],
    }
}

/// The tau = 7 instance of Fig. 1 (task locations read from the figure, in drawing order).
pub fn fig1() -> Instance {
    let mut inst = base();
    inst.tasks = vec![
        [-1.3103, 6.5381],
        [-7.6599, 4.8716],
        [-4.1123, -0.1235],
        [4.9762, -2.9167],
        [9.1624, -1.2344],
        [6.0938, -7.4380],
        [-4.1433, -9.1665],
    ];
    inst
}

/// Mission time of the paper's solution for the Fig. 1 instance, read from the end of the
/// battery curve in Fig. 2a.
pub const FIG1_REFERENCE_TIME_H: f64 = 1.8932;

/// Vertices of the paper's solution drawn in Fig. 1 (17 time stamps, 4 charging segments).
pub const FIG1_REFERENCE_PATH: [V2; 17] = [
    [-3.500, 3.500],
    [-1.310, 6.538],
    [-3.448, 4.990],
    [-4.715, 4.364],
    [-7.660, 4.872],
    [-4.112, -0.123],
    [0.224, -1.148],
    [2.031, -1.738],
    [4.976, -2.917],
    [9.162, -1.234],
    [7.843, -3.984],
    [7.093, -5.491],
    [6.094, -7.438],
    [2.128, -4.411],
    [1.214, -4.475],
    [-4.143, -9.167],
    [-5.000, -7.001],
];

/// Distance from `a` to the boundary of the nearest region (negative inside) and that region.
pub fn nearest_region(inst: &Instance, a: V2) -> (usize, f64) {
    inst.regions
        .iter()
        .enumerate()
        .map(|(j, r)| (j, dist(a, r.o) - r.rho))
        .min_by(|x, y| x.1.total_cmp(&y.1))
        .unwrap()
}

/// Random task locations. The paper only says "randomly generated"; here they are uniform in
/// `[-half, half]^2`, rejecting points farther than `max_reach` from every charging region (a
/// task farther than half the range v_d / zeta cannot be served at all).
pub fn random(tau: usize, seed: u64, half: f64, max_reach: f64) -> Instance {
    let mut inst = base();
    let mut rng = Rng::new(seed);
    while inst.tasks.len() < tau {
        let a = [rng.range(-half, half), rng.range(-half, half)];
        if nearest_region(&inst, a).1 <= max_reach {
            inst.tasks.push(a);
        }
    }
    inst
}

#[derive(Clone, Copy, Debug, PartialEq)]
pub enum Order {
    /// Visit tasks in index order.
    Index,
    /// Greedy nearest neighbour starting from r0.
    Nearest,
}

#[derive(Clone, Debug)]
pub struct InitOpts {
    pub order: Order,
    /// Battery level each charging stop of the warm start charges up to.
    pub charge_target: f64,
    /// Station stamps are placed this fraction of the radius inside the region boundary.
    pub margin: f64,
}

impl Default for InitOpts {
    fn default() -> Self {
        InitOpts { order: Order::Index, charge_target: 0.9, margin: 0.1 }
    }
}

/// A full trajectory, including the fixed end points and e_1.
#[derive(Clone, Debug)]
pub struct Traj {
    pub r: Vec<V2>,
    pub e: Vec<f64>,
    pub s: Vec<f64>,
    pub c: Vec<f64>,
}

impl Traj {
    pub fn to_x(&self, lay: &Layout) -> Vec<f64> {
        let mut x = vec![0.0; lay.n_var()];
        for k in 0..lay.n {
            if let Some(i) = lay.r(k) {
                x[i] = self.r[k][0];
                x[i + 1] = self.r[k][1];
            }
            if let Some(i) = lay.e(k) {
                x[i] = self.e[k];
            }
        }
        for k in 0..lay.n - 1 {
            x[lay.s(k)] = self.s[k];
            x[lay.c(k)] = self.c[k];
        }
        x
    }

    pub fn from_x(x: &[f64], lay: &Layout, inst: &Instance, ph: &Phys) -> Traj {
        let n = lay.n;
        Traj {
            r: (0..n)
                .map(|k| match lay.r(k) {
                    Some(i) => [x[i], x[i + 1]],
                    None if k == 0 => inst.r0,
                    None => inst.rf,
                })
                .collect(),
            e: (0..n).map(|k| lay.e(k).map_or(ph.e_max, |i| x[i])).collect(),
            s: (0..n - 1).map(|k| x[lay.s(k)]).collect(),
            c: (0..n - 1).map(|k| x[lay.c(k)]).collect(),
        }
    }

    pub fn total_time(&self) -> f64 {
        self.s.iter().sum()
    }
}

pub fn task_order(inst: &Instance, order: Order) -> Vec<usize> {
    let tau = inst.tasks.len();
    match order {
        Order::Index => (0..tau).collect(),
        Order::Nearest => {
            let mut left: Vec<usize> = (0..tau).collect();
            let mut out = Vec::with_capacity(tau);
            let mut at = inst.r0;
            while !left.is_empty() {
                let (pos, _) = left
                    .iter()
                    .enumerate()
                    .map(|(pos, &i)| (pos, dist(at, inst.tasks[i])))
                    .min_by(|a, b| a.1.total_cmp(&b.1))
                    .unwrap();
                let i = left.swap_remove(pos);
                at = inst.tasks[i];
                out.push(i);
            }
            out
        }
    }
}

/// Warm start of Section IV-B: for each task, fly to the nearest charging region, charge, visit
/// the task, return to the same region and charge again. The paper does not give the number of
/// time stamps; this construction uses five per task (arrive, charged, task, back, charged), so
/// N = 5 tau + 2. Battery levels follow the dynamics exactly; bounds may be violated.
pub fn initial_trajectory(inst: &Instance, ph: &Phys, opts: &InitOpts) -> Traj {
    let mut r = vec![inst.r0];
    let mut charging = Vec::new();
    for i in task_order(inst, opts.order) {
        let a = inst.tasks[i];
        let (j, _) = nearest_region(inst, a);
        let reg = &inst.regions[j];
        let d = sub(a, reg.o);
        let len = norm(d);
        let reach = reg.rho * (1.0 - opts.margin);
        let q = if len <= reach { a } else { [reg.o[0] + d[0] / len * reach, reg.o[1] + d[1] / len * reach] };
        r.extend([q, q, a, q, q]);
        charging.extend([false, true, false, false, true]);
    }
    r.push(inst.rf);
    charging.push(false);

    let n = r.len();
    let (mut e, mut s, mut c) = (vec![ph.e_max; n], vec![0.0; n - 1], vec![0.0; n - 1]);
    for k in 0..n - 1 {
        if charging[k] {
            let t = time_to_charge(ph, e[k], opts.charge_target).clamp(ph.s_min, ph.s_max);
            s[k] = t;
            c[k] = t;
            e[k + 1] = charge(ph, e[k], t).0;
        } else {
            s[k] = (dist(r[k], r[k + 1]) / ph.v_d).clamp(ph.s_min, ph.s_max);
            e[k + 1] = e[k] - ph.zeta * s[k];
        }
    }
    Traj { r, e, s, c }
}
