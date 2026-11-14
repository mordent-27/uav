#[path = "/home/mordent/robotech/3A/optimization/uav/src/auglag.rs"] mod auglag;
#[path = "/home/mordent/robotech/3A/optimization/uav/src/battery.rs"] mod battery;
#[path = "/home/mordent/robotech/3A/optimization/uav/src/instance.rs"] mod instance;
#[path = "/home/mordent/robotech/3A/optimization/uav/src/lbfgs.rs"] mod lbfgs;
#[path = "/home/mordent/robotech/3A/optimization/uav/src/metrics.rs"] mod metrics;
#[path = "/home/mordent/robotech/3A/optimization/uav/experiments/2026-11-14-lse/lse-model.rs"] mod model;
#[path = "/home/mordent/robotech/3A/optimization/uav/src/output.rs"] mod output;
#[path = "/home/mordent/robotech/3A/optimization/uav/src/params.rs"] mod params;
#[path = "/home/mordent/robotech/3A/optimization/uav/src/rng.rs"] mod rng;
#[path = "/home/mordent/robotech/3A/optimization/uav/experiments/2026-11-14-validation/cap-comparison/instrumented-solver.rs"] mod solver;

use std::collections::HashMap;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::Mutex;

use instance::Order;
use params::Phys;

const USAGE: &str = "\
uav - smooth NLP trajectory optimization for a UAV with mobile charging (arXiv:2609.40201)

USAGE:
  uav solve [--fig1 | --tau T --seed S] [--out FILE.json] [options]
  uav mc    [--tau-min A --tau-max B --runs R --seed S --threads N] [--out FILE.csv] [options]

INSTANCE:
  --fig1              the tau = 7 instance of Fig. 1 (default for `solve`)
  --tau T --seed S    random instance with T tasks
  --half H            tasks are uniform in [-H, H]^2                      [9]
  --reach D           reject tasks farther than D km from every region    [6]
  --order O           task order of the warm start: index | nearest       [index]

ALGORITHM:
  --stages L          homotopy stages                                     [13]
  --outer K           AL outer iterations per intermediate stage          [10]
  --final-outer K     AL outer iterations in the last stage               [30]
  --inner K           L-BFGS iterations per AL subproblem                 [2000]
  --mem M             L-BFGS memory                                       [20]
  --rho0 R  --rho-mult F  --rho-max R   penalty schedule                  [10, 10, 1e8]
  --tol T             KKT tolerance (stationarity and feasibility)        [1e-6]
  --reset-multipliers reset multipliers and penalty at every stage
  --verbose           print per-stage logs
  --debug             print every AL outer iteration to stderr
";

struct Args {
    flags: HashMap<String, String>,
}

impl Args {
    fn parse(it: impl Iterator<Item = String>) -> Args {
        let mut flags = HashMap::new();
        let mut it = it.peekable();
        while let Some(a) = it.next() {
            let Some(key) = a.strip_prefix("--") else {
                die(&format!("unexpected argument `{a}`"));
            };
            let val = match it.peek() {
                Some(v) if !v.starts_with("--") => it.next().unwrap(),
                _ => String::new(),
            };
            flags.insert(key.to_string(), val);
        }
        Args { flags }
    }
    fn has(&self, k: &str) -> bool {
        self.flags.contains_key(k)
    }
    fn get<T: std::str::FromStr>(&self, k: &str, default: T) -> T {
        match self.flags.get(k) {
            None => default,
            Some(v) => v.parse().unwrap_or_else(|_| die(&format!("bad value for --{k}: `{v}`"))),
        }
    }
    fn str(&self, k: &str) -> Option<&str> {
        self.flags.get(k).map(|s| s.as_str())
    }
}

fn die(msg: &str) -> ! {
    eprintln!("error: {msg}\n\n{USAGE}");
    std::process::exit(2)
}

fn solver_opts(a: &Args) -> solver::Opts {
    let mut o = solver::Opts::default();
    o.hom.stages = a.get("stages", o.hom.stages);
    o.stage_outer = a.get("outer", o.stage_outer);
    o.al.max_outer = a.get("final-outer", o.al.max_outer);
    o.al.inner.max_iter = a.get("inner", o.al.inner.max_iter);
    o.al.inner.mem = a.get("mem", o.al.inner.mem);
    o.al.rho0 = a.get("rho0", o.al.rho0);
    o.al.rho_mult = a.get("rho-mult", o.al.rho_mult);
    o.al.rho_max = a.get("rho-max", o.al.rho_max);
    let tol = a.get("tol", o.al.tol_stat);
    o.al.tol_stat = tol;
    o.al.tol_feas = tol;
    o.keep_multipliers = !a.has("reset-multipliers");
    o.al.debug = a.has("debug");
    o.init.order = match a.str("order").unwrap_or("index") {
        "index" => Order::Index,
        "nearest" => Order::Nearest,
        other => die(&format!("unknown --order `{other}`")),
    };
    o
}

fn cmd_solve(a: &Args) {
    let ph = Phys::default();
    let inst = if a.has("tau") {
        instance::random(a.get("tau", 7), a.get("seed", 0), a.get("half", 9.0), a.get("reach", 6.0))
    } else {
        instance::fig1()
    };
    let o = solver_opts(a);
    let sol = solver::solve(&inst, &ph, &o);

    if a.has("verbose") {
        println!("stage    eps      p  outer  inner   evals      rho    objective     stat     feas     comp  viol(orig)");
        for (i, s) in sol.stages.iter().enumerate() {
            println!(
                "{:>5} {:>7.5} {:>6.2} {:>6} {:>6} {:>7} {:>8.1e} {:>12.6} {:>8.1e} {:>8.1e} {:>8.1e} {:>10.2e}{}",
                i + 1, s.sm.eps, s.sm.p, s.outer, s.inner_iters, s.evals, s.rho, s.f,
                s.kkt.stat, s.kkt.feas, s.kkt.comp, s.viol,
                if s.converged { "  ok" } else { "" },
            );
        }
    }
    let m = &sol.metrics;
    println!("tasks {}  stamps {}  variables {}", inst.tasks.len(), sol.n_stamps, 5 * sol.n_stamps - 7);
    println!(
        "warm start : objective {:.4} h   violation {:.2e}",
        sol.init_metrics.objective, sol.init_metrics.viol
    );
    println!(
        "solution   : objective {:.4} h   violation {:.2e}  (task {:.1e}, mode {:.1e}, dyn {:.1e}, speed {:.1e}, bounds {:.1e})",
        m.objective, m.viol, m.viol_task, m.viol_mode, m.viol_dyn, m.viol_speed, m.viol_bounds
    );
    println!(
        "charging segments {}   visit order {:?}",
        m.modes.iter().filter(|&&j| j >= 0).count(),
        visit_order(m)
    );
    println!("Theorem 1 diagnostics omitted for the modified approximation");
    println!("KKT converged: {}   time {:.3} s", sol.converged, sol.seconds);
    if !a.has("tau") {
        println!("paper (Fig. 2): objective {:.4} h", instance::FIG1_REFERENCE_TIME_H);
    }
    if let Some(path) = a.str("out") {
        let json = output::solution_json(&inst, &ph, &sol, !a.has("tau"));
        std::fs::write(path, json).unwrap_or_else(|e| die(&format!("cannot write {path}: {e}")));
        println!("wrote {path}");
    }
}

/// Task indices in the order they are visited.
fn visit_order(m: &metrics::Metrics) -> Vec<usize> {
    let mut idx: Vec<usize> = (0..m.task_stamp.len()).collect();
    idx.sort_by_key(|&i| m.task_stamp[i]);
    idx.iter().map(|i| i + 1).collect()
}

fn cmd_mc(a: &Args) {
    let ph = Phys::default();
    let o = solver_opts(a);
    let (tau_min, tau_max): (usize, usize) = (a.get("tau-min", 1), a.get("tau-max", 9));
    let runs: usize = a.get("runs", 100);
    let seed: u64 = a.get("seed", 0);
    let threads: usize =
        a.get("threads", std::thread::available_parallelism().map_or(1, |n| n.get()));
    let (half, reach) = (a.get("half", 9.0), a.get("reach", 6.0));

    let jobs: Vec<(usize, usize)> =
        (tau_min..=tau_max).flat_map(|t| (0..runs).map(move |r| (t, r))).collect();
    let next = AtomicUsize::new(0);
    let rows = Mutex::new(Vec::with_capacity(jobs.len()));
    std::thread::scope(|sc| {
        for _ in 0..threads {
            sc.spawn(|| loop {
                let j = next.fetch_add(1, Ordering::Relaxed);
                let Some(&(tau, run)) = jobs.get(j) else { break };
                let inst_seed = seed.wrapping_mul(1_000_003).wrapping_add((tau * 10_000 + run) as u64);
                let inst = instance::random(tau, inst_seed, half, reach);
                let sol = solver::solve(&inst, &ph, &o);
                let m = &sol.metrics;
                let order_changed = visit_order(m)
                    != instance::task_order(&inst, o.init.order).iter().map(|i| i + 1).collect::<Vec<_>>();
                let row = format!(
                    "{tau},{run},{inst_seed},{},{:.6},{:.6},{:.6e},{:.6e},{:.6e},{:.6e},{:.6e},{:.6e},{},{},{},{:.3e},{:.3e},{:.6},{:.6e}",
                    sol.n_stamps, sol.seconds, m.objective, m.viol, m.viol_task, m.viol_mode,
                    m.viol_dyn, m.viol_speed, m.viol_bounds,
                    m.modes.iter().filter(|&&j| j >= 0).count(),
                    sol.converged as u8, order_changed as u8,
                    m.thm_value_dev, m.thm_grad_dev,
                    sol.init_metrics.objective, sol.init_metrics.viol,
                );
                rows.lock().unwrap().push(((tau, run), row));
            });
        }
    });
    let mut rows = rows.into_inner().unwrap();
    rows.sort();
    let mut csv = String::from(
        "tau,run,seed,stamps,seconds,objective,viol,viol_task,viol_mode,viol_dyn,viol_speed,viol_bounds,charges,converged,order_changed,thm_value_dev,thm_grad_dev,init_objective,init_viol\n",
    );
    for (_, r) in &rows {
        csv.push_str(r);
        csv.push('\n');
    }
    match a.str("out") {
        Some(path) => {
            std::fs::write(path, &csv).unwrap_or_else(|e| die(&format!("cannot write {path}: {e}")));
            println!("wrote {path} ({} rows)", rows.len());
        }
        None => print!("{csv}"),
    }
}

fn main() {
    let mut argv = std::env::args().skip(1);
    let cmd = argv.next().unwrap_or_default();
    let args = Args::parse(argv);
    match cmd.as_str() {
        "solve" => cmd_solve(&args),
        "mc" => cmd_mc(&args),
        "" | "help" | "--help" | "-h" => print!("{USAGE}"),
        other => die(&format!("unknown command `{other}`")),
    }
}
