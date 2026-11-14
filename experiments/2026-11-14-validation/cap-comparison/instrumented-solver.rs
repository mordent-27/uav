//! Algorithm 1: homotopy over the smoothing parameters, each stage solved by the augmented
//! Lagrangian method and warm-started from the previous stage.

use std::time::Instant;

use crate::auglag::{self, Kkt};
use crate::instance::{initial_trajectory, InitOpts, Traj};
use crate::metrics::{evaluate, Metrics};
use crate::model::Model;
use crate::params::*;

#[derive(Clone, Debug)]
pub struct Opts {
    pub hom: Homotopy,
    pub al: auglag::Opts,
    /// Outer-iteration limit of the intermediate stages (`al.max_outer` applies to the last one).
    pub stage_outer: usize,
    /// Keep multipliers and penalty between stages instead of resetting them.
    pub keep_multipliers: bool,
    pub init: InitOpts,
}

impl Default for Opts {
    fn default() -> Self {
        Opts {
            hom: Homotopy::default(),
            al: auglag::Opts::default(),
            stage_outer: 10,
            keep_multipliers: true,
            init: InitOpts::default(),
        }
    }
}

#[derive(Clone, Debug)]
pub struct StageLog {
    pub sm: Smooth,
    pub outer: usize,
    pub inner_iters: usize,
    pub evals: usize,
    pub rho: f64,
    pub f: f64,
    pub kkt: Kkt,
    pub converged: bool,
    /// Violation of the original constraints (11)-(12) after the stage.
    pub viol: f64,
}

pub struct Solution {
    pub n_stamps: usize,
    pub init: Traj,
    pub traj: Traj,
    pub stages: Vec<StageLog>,
    pub metrics: Metrics,
    pub init_metrics: Metrics,
    pub seconds: f64,
    pub converged: bool,
}

pub fn solve(inst: &Instance, ph: &Phys, o: &Opts) -> Solution {
    let init = initial_trajectory(inst, ph, &o.init);
    solve_from(inst, ph, o, init)
}

pub fn solve_from(inst: &Instance, ph: &Phys, o: &Opts, init: Traj) -> Solution {
    let start = Instant::now();
    let n_stamps = init.r.len();
    let schedule = o.hom.schedule();
    let last = *schedule.last().unwrap();
    let lay = Model::new(inst, ph, n_stamps, last).lay;
    let mut x = init.to_x(&lay);
    let mut st = auglag::State::new(lay.n_eq(), lay.n_ineq(), o.al.rho0);
    let mut stages = Vec::with_capacity(schedule.len());
    let mut converged = false;

    for (l, &sm) in schedule.iter().enumerate() {
        let is_last = l + 1 == schedule.len();
        let model = Model::new(inst, ph, n_stamps, sm);
        if !o.keep_multipliers {
            st = auglag::State::new(lay.n_eq(), lay.n_ineq(), o.al.rho0);
        }
        let al = auglag::Opts {
            max_outer: if is_last { o.al.max_outer } else { o.stage_outer },
            ..o.al.clone()
        };
        let res = auglag::solve(&model, &mut x, &mut st, &al);
        let viol = evaluate(inst, ph, &Traj::from_x(&x, &lay, inst, ph), sm).viol;
        stages.push(StageLog {
            sm,
            outer: res.outer,
            inner_iters: res.inner_iters,
            evals: res.evals,
            rho: st.rho,
            f: res.f,
            kkt: res.kkt,
            converged: res.converged,
            viol,
        });
        let probe = Traj::from_x(&x, &lay, inst, ph);
        let over = probe.c.iter().zip(&probe.s).map(|(c,s)| (c-s).max(0.)).fold(0., f64::max);
        let below = probe.c.iter().map(|c| (-c).max(0.)).fold(0., f64::max);
        eprintln!("DOMAIN stage={} over_sec={:.12e} below_sec={:.12e}", l+1, 3600.*over, 3600.*below);
        converged = res.converged;
    }
    let seconds = start.elapsed().as_secs_f64();

    let traj = Traj::from_x(&x, &lay, inst, ph);
    let metrics = evaluate(inst, ph, &traj, last);
    let init_metrics = evaluate(inst, ph, &init, last);
    Solution { n_stamps, init, traj, stages, metrics, init_metrics, seconds, converged }
}
