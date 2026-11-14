//! JSON serialisation of a solution (hand-written to stay dependency-free).

use std::fmt::Write;

use crate::instance::{self, Traj};
use crate::metrics::history;
use crate::params::*;
use crate::solver::Solution;

fn arr(v: &[f64]) -> String {
    let items: Vec<String> = v.iter().map(|x| format!("{x:.9}")).collect();
    format!("[{}]", items.join(","))
}

fn pts(v: &[V2]) -> String {
    let items: Vec<String> = v.iter().map(|p| format!("[{:.9},{:.9}]", p[0], p[1])).collect();
    format!("[{}]", items.join(","))
}

fn traj(t: &Traj) -> String {
    format!(
        "{{\"r\":{},\"e\":{},\"s\":{},\"c\":{}}}",
        pts(&t.r),
        arr(&t.e),
        arr(&t.s),
        arr(&t.c)
    )
}

pub fn solution_json(inst: &Instance, ph: &Phys, sol: &Solution, with_reference: bool) -> String {
    let m = &sol.metrics;
    let h = history(inst, ph, &sol.traj, &m.modes, 60);
    let mut o = String::new();
    let regions: Vec<String> = inst
        .regions
        .iter()
        .map(|r| format!("{{\"o\":[{},{}],\"rho\":{}}}", r.o[0], r.o[1], r.rho))
        .collect();
    write!(
        o,
        "{{\n\"instance\":{{\"r0\":[{},{}],\"rf\":[{},{}],\"regions\":[{}],\"tasks\":{}}},\n",
        inst.r0[0],
        inst.r0[1],
        inst.rf[0],
        inst.rf[1],
        regions.join(","),
        pts(&inst.tasks)
    )
    .unwrap();
    write!(
        o,
        "\"phys\":{{\"e_max\":{},\"e_th\":{},\"e_min\":{},\"v_d\":{},\"v_c\":{},\"kappa\":{},\"zeta\":{},\"s_min\":{},\"s_max\":{}}},\n",
        ph.e_max, ph.e_th, ph.e_min, ph.v_d, ph.v_c, ph.kappa, ph.zeta, ph.s_min, ph.s_max
    )
    .unwrap();
    writeln!(o, "\"init\":{},", traj(&sol.init)).unwrap();
    writeln!(o, "\"solution\":{},", traj(&sol.traj)).unwrap();
    let modes: Vec<String> = m.modes.iter().map(|j| j.to_string()).collect();
    let stamps: Vec<String> = m.task_stamp.iter().map(|k| k.to_string()).collect();
    writeln!(o, "\"modes\":[{}],", modes.join(",")).unwrap();
    writeln!(o, "\"task_stamp\":[{}],", stamps.join(",")).unwrap();
    writeln!(
        o,
        "\"history\":{{\"t\":{},\"e\":{},\"d\":{},\"stamps\":{}}},",
        arr(&h.t),
        arr(&h.e),
        arr(&h.d),
        arr(&h.stamps)
    )
    .unwrap();
    let stages: Vec<String> = sol
        .stages
        .iter()
        .map(|s| {
            format!(
                "{{\"eps\":{},\"p\":{},\"outer\":{},\"inner\":{},\"evals\":{},\"rho\":{:e},\"f\":{:.9},\"stat\":{:e},\"feas\":{:e},\"comp\":{:e},\"viol\":{:e},\"converged\":{}}}",
                s.sm.eps, s.sm.p, s.outer, s.inner_iters, s.evals, s.rho, s.f, s.kkt.stat,
                s.kkt.feas, s.kkt.comp, s.viol, s.converged
            )
        })
        .collect();
    writeln!(o, "\"stages\":[\n{}\n],", stages.join(",\n")).unwrap();
    if with_reference {
        writeln!(
            o,
            "\"reference\":{{\"objective\":{},\"path\":{}}},",
            instance::FIG1_REFERENCE_TIME_H,
            pts(&instance::FIG1_REFERENCE_PATH)
        )
        .unwrap();
    }
    write!(
        o,
        "\"metrics\":{{\"objective\":{:.9},\"init_objective\":{:.9},\"viol\":{:e},\"viol_task\":{:e},\"viol_mode\":{:e},\"viol_dyn\":{:e},\"viol_speed\":{:e},\"viol_bounds\":{:e},\"thm_value_dev\":{:e},\"thm_grad_dev\":{:e},\"seconds\":{:.6},\"converged\":{},\"stamps\":{}}}\n}}\n",
        m.objective, sol.init_metrics.objective, m.viol, m.viol_task, m.viol_mode, m.viol_dyn,
        m.viol_speed, m.viol_bounds, m.thm_value_dev, m.thm_grad_dev, sol.seconds, sol.converged,
        sol.n_stamps
    )
    .unwrap();
    o
}
