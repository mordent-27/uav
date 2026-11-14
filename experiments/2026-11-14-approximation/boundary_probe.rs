#![allow(dead_code)]
#[path="/home/mordent/robotech/3A/optimization/uav/src/params.rs"] mod params;
#[path="/home/mordent/robotech/3A/optimization/uav/src/rng.rs"] mod rng;
#[path="/home/mordent/robotech/3A/optimization/uav/src/battery.rs"] mod battery;
#[path="/home/mordent/robotech/3A/optimization/uav/src/instance.rs"] mod instance;
#[path="/home/mordent/robotech/3A/optimization/uav/src/metrics.rs"] mod metrics;
#[path="/home/mordent/robotech/3A/optimization/uav/experiments/2026-11-14-approximation/zero_psi-model.rs"] mod model;
#[path="/home/mordent/robotech/3A/optimization/uav/experiments/2026-11-14-approximation/inequalities-model.rs"] mod inequalities;
#[path="/home/mordent/robotech/3A/optimization/uav/experiments/2026-11-14-approximation/combined-model.rs"] mod combined;

fn main() {
use params::*;
let ph=Phys::default();let sm=Smooth{eps:0.0005,p:12.,delta:0.001};
let inst=Instance{r0:[1.,0.],rf:[1.,0.],regions:vec![Region{o:[0.,0.],rho:1.}],tasks:vec![[1.,0.]]};
let tr=instance::Traj{r:vec![[1.,0.];3],e:vec![1.,1.,0.75],s:vec![0.1,0.1],c:vec![0.1,0.]};
let original=metrics::evaluate(&inst,&ph,&tr,sm);assert!(original.viol<1e-12);
macro_rules! check {($module:ident,$name:expr,$leq:expr)=>{{
let m=$module::Model::new(&inst,&ph,3,sm);let l=m.lay;let mut x=vec![0.;l.n_var()];
for k in 0..3 {if let Some(i)=l.r(k){x[i]=tr.r[k][0];x[i+1]=tr.r[k][1];} if let Some(i)=l.e(k){x[i]=tr.e[k];}}
for k in 0..2 {x[l.s(k)]=tr.s[k];x[l.c(k)]=tr.c[k];}
let we=vec![0.;l.n_eq()];let wi=vec![0.;l.n_ineq()];let mut r=$module::Recorder::new(&we,&wi);let mut g=vec![0.;x.len()];m.eval(&x,&mut r,&mut g);
let h=r.h.iter().map(|v|v.abs()).fold(0.,f64::max);let z=r.g.iter().copied().fold(0.,f64::max);
let task=if $leq {r.g[14]}else{r.h[2]};let mode=if $leq {r.g[15]}else{r.h[3]};
println!("{} {:.12e} {:.12e} {:.12e} {:.12e}",$name,h,z,task,mode);
}};}
check!(model,"P",false);check!(inequalities,"I",true);check!(combined,"PI",true);
}
