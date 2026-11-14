//! Evaluation of a trajectory against the original constraints (11) and (12), the tightness
//! terms of Theorem 1, and dense histories for plotting.

use crate::battery::{charge, step};
use crate::instance::Traj;
use crate::params::*;

#[derive(Clone, Debug, Default)]
pub struct Metrics {
    pub objective: f64,
    /// Infinity norm of the violations of all constraints in (11) and (12). As in the paper this
    /// mixes km, hours and battery fractions.
    pub viol: f64,
    pub viol_task: f64,
    pub viol_mode: f64,
    pub viol_dyn: f64,
    pub viol_speed: f64,
    pub viol_bounds: f64,
    /// Selected case of the mode disjunction per segment: -1 discharge, j >= 0 charge in region j.
    pub modes: Vec<i32>,
    /// Stamp that realises each task visit.
    pub task_stamp: Vec<usize>,
    /// Largest deviation from 1 of the bound factors in (21) and (22) over all smooth-min
    /// constraints.
    pub thm_value_dev: f64,
    pub thm_grad_dev: f64,
}

/// Violation of g_j(r_k, r_{k+1}, s_k) <= 0 (eq. 24), as the largest positive component.
fn region_violation(reg: &Region, ph: &Phys, ra: V2, rb: V2, s: f64) -> f64 {
    (dist(ra, reg.o) - reg.rho)
        .max(dist(rb, reg.o) - reg.rho)
        .max(dist(ra, rb) - ph.v_c * s)
        .max(0.0)
}

/// 1 - exp((m - n) / (scale * m * t^power)) for the tie-free case m = 1, where t = z_2nd / z_min.
fn thm_dev(n: usize, scale: f64, t: f64, power: f64) -> f64 {
    -((1.0 - n as f64) / (scale * t.powf(power))).exp_m1()
}

pub fn evaluate(inst: &Instance, ph: &Phys, tr: &Traj, sm: Smooth) -> Metrics {
    let n = tr.r.len();
    let mut m = Metrics { objective: tr.total_time(), ..Metrics::default() };
    let mut thm = |z: &mut Vec<f64>| {
        z.sort_by(|a, b| a.total_cmp(b));
        let t = z[1] / z[0];
        m.thm_value_dev = m.thm_value_dev.max(thm_dev(z.len(), sm.p, t, sm.p));
        m.thm_grad_dev = m.thm_grad_dev.max(thm_dev(z.len(), 2.0, t, 2.0 * sm.p + 2.0));
    };

    for &a in &inst.tasks {
        let (k, v) = (0..n)
            .map(|k| {
                let d = sub(tr.r[k], a);
                (k, d[0].abs().max(d[1].abs()))
            })
            .min_by(|x, y| x.1.total_cmp(&y.1))
            .unwrap();
        m.task_stamp.push(k);
        m.viol_task = m.viol_task.max(v);
        let mut z: Vec<f64> = (0..n).map(|k| dist(tr.r[k], a).hypot(sm.eps)).collect();
        thm(&mut z);
    }

    for k in 0..n - 1 {
        let (s, c) = (tr.s[k], tr.c[k]);
        let (ra, rb) = (tr.r[k], tr.r[k + 1]);
        let mut best = (-1, c.abs());
        let mut z = vec![c.hypot(sm.eps)];
        for (j, reg) in inst.regions.iter().enumerate() {
            let v = (c - s).abs().max(region_violation(reg, ph, ra, rb, s));
            if v < best.1 {
                best = (j as i32, v);
            }
            let p1 = crate::model::psi(dist(ra, reg.o) - reg.rho, sm.delta).0;
            let p2 = crate::model::psi(dist(rb, reg.o) - reg.rho, sm.delta).0;
            let p3 = crate::model::psi(dist(ra, rb) - ph.v_c * s, sm.delta).0;
            z.push(((c - s).powi(2) + p1 * p1 + p2 * p2 + p3 * p3 + sm.eps * sm.eps).sqrt());
        }
        m.modes.push(best.0);
        m.viol_mode = m.viol_mode.max(best.1);
        thm(&mut z);

        m.viol_dyn = m.viol_dyn.max((tr.e[k + 1] - step(ph, tr.e[k], s, c)).abs());
        m.viol_speed = m.viol_speed.max(dist(ra, rb) - ph.v_d * s);
        let e = tr.e[k + 1];
        m.viol_bounds = m
            .viol_bounds
            .max(ph.e_min - e)
            .max(e - ph.e_max)
            .max(ph.s_min - s)
            .max(s - ph.s_max);
    }
    m.viol_speed = m.viol_speed.max(0.0);
    m.viol = m.viol_task.max(m.viol_mode).max(m.viol_dyn).max(m.viol_speed).max(m.viol_bounds);
    m
}

/// Dense samples for Fig. 2: time, battery level and distance to the closest charging region.
pub struct History {
    pub t: Vec<f64>,
    pub e: Vec<f64>,
    pub d: Vec<f64>,
    /// Cumulative time at each stamp.
    pub stamps: Vec<f64>,
}

pub fn history(inst: &Instance, ph: &Phys, tr: &Traj, modes: &[i32], per_seg: usize) -> History {
    let mut h = History { t: vec![], e: vec![], d: vec![], stamps: vec![0.0] };
    let mut t0 = 0.0;
    for k in 0..tr.s.len() {
        for i in 0..=per_seg {
            let a = i as f64 / per_seg as f64;
            let dt = a * tr.s[k];
            let r = [
                tr.r[k][0] + a * (tr.r[k + 1][0] - tr.r[k][0]),
                tr.r[k][1] + a * (tr.r[k + 1][1] - tr.r[k][1]),
            ];
            let e = if modes[k] >= 0 { charge(ph, tr.e[k], dt).0 } else { tr.e[k] - ph.zeta * dt };
            let d = inst.regions.iter().map(|g| dist(r, g.o) - g.rho).fold(f64::INFINITY, f64::min);
            h.t.push(t0 + dt);
            h.e.push(e);
            h.d.push(d.max(0.0));
        }
        t0 += tr.s[k];
        h.stamps.push(t0);
    }
    h
}
