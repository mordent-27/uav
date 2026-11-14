#![allow(dead_code)]
#[path="/home/mordent/robotech/3A/optimization/uav/src/params.rs"] mod params;
#[path="/home/mordent/robotech/3A/optimization/uav/src/rng.rs"] mod rng;
#[path="/home/mordent/robotech/3A/optimization/uav/src/battery.rs"] mod battery;
#[path="/home/mordent/robotech/3A/optimization/uav/src/instance.rs"] mod instance;
#[path="/home/mordent/robotech/3A/optimization/uav/src/metrics.rs"] mod metrics;
#[path="/home/mordent/robotech/3A/optimization/uav/experiments/2026-11-14-scaling/mode-model.rs"] mod model;
#[path="/home/mordent/robotech/3A/optimization/uav/experiments/2026-11-14-mesh/mesh_init.rs"] mod mesh_init;

fn main() {
use params::*;use model::*;
let inst=instance::fig1();let ph=Phys::default();
let tr=mesh_init::refine(&instance::initial_trajectory(&inst,&ph,&instance::InitOpts::default()),&ph);
let model=Model::new(&inst,&ph,tr.r.len(),Smooth{eps:0.01,p:6.,delta:0.001});
let mut x=tr.to_x(&model.lay);let mut rng=rng::Rng::new(41);
for (v,d) in x.iter_mut().zip(model.var_scale()) {*v+=0.03*d*(rng.uniform()-0.5);}
let we:Vec<f64>=(0..model.lay.n_eq()).map(|_|rng.uniform()-0.5).collect();
let wi:Vec<f64>=(0..model.lay.n_ineq()).map(|_|rng.uniform()).collect();
let lag=|x:&[f64],g:&mut[f64]| {let mut rec=Recorder::new(&we,&wi);let f=model.eval(x,&mut rec,g);f+rec.val};
let mut g=vec![0.;x.len()];let mut scratch=vec![0.;x.len()];lag(&x,&mut g);
let i=332;let old=x[i];
println!("N={} c-segment={} analytic_x={:.12e}",tr.r.len(),i-model.lay.c(0),g[i]);
for h in [1e-6,3e-7,1e-7,3e-8] {
x[i]=old+h;let fp=lag(&x,&mut scratch);x[i]=old-h;let fm=lag(&x,&mut scratch);x[i]=old;
let fd=(fp-fm)/(2.*h);let err=(fd-g[i]).abs()/(1.+fd.abs());
println!("h_x={:.3e} finite_difference={:.12e} relative_error={:.6e}",h,fd,err);
if h==1e-7 {assert!(err<1e-6);}
}
}
