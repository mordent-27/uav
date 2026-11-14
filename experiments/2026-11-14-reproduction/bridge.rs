//! Diagnostic C ABI over the unmodified Rust model, for independent inner solvers.
#![allow(dead_code)]
#[path = "../../src/params.rs"] mod params;
#[path = "../../src/rng.rs"] mod rng;
#[path = "../../src/battery.rs"] mod battery;
#[path = "../../src/instance.rs"] mod instance;
#[path = "../../src/model.rs"] mod model;
#[path = "../../src/lbfgs.rs"] mod lbfgs;
#[path = "../../src/auglag.rs"] mod auglag;
#[path = "../../src/metrics.rs"] mod metrics;
#[path = "../../src/solver.rs"] mod solver;
#[path = "../../src/output.rs"] mod output;

use std::slice;
use params::*;
use model::{Model, Weights};

pub struct Context {
    inst: Instance, ph: Phys, init: instance::Traj, sm: Smooth, d: Vec<f64>, fig1: bool,
}
impl Context {
    fn model(&self) -> Model<'_> { Model::new(&self.inst, &self.ph, self.init.r.len(), self.sm) }
}

#[no_mangle]
pub extern "C" fn uav_create(tau: usize, seed: u64) -> *mut Context {
    let inst = if tau == 0 { instance::fig1() } else { instance::random(tau, seed, 9., 6.) };
    let ph = Phys::default();
    let init = instance::initial_trajectory(&inst, &ph, &instance::InitOpts::default());
    let sm = Homotopy::default().schedule()[0];
    let d = Model::new(&inst, &ph, init.r.len(), sm).var_scale();
    Box::into_raw(Box::new(Context { inst, ph, init, sm, d, fig1: tau==0 }))
}
#[no_mangle]
pub unsafe extern "C" fn uav_free(ctx: *mut Context) { drop(Box::from_raw(ctx)); }
#[no_mangle]
pub unsafe extern "C" fn uav_dims(ctx: *const Context, dims: *mut usize) {
    let c = &*ctx; let l = c.model().lay;
    slice::from_raw_parts_mut(dims,4).copy_from_slice(&[l.n_var(),l.n_eq(),l.n_ineq(),l.n]);
}
#[no_mangle]
pub unsafe extern "C" fn uav_initial(ctx: *const Context, y: *mut f64, d: *mut f64) {
    let c = &*ctx;
    let x = c.init.to_x(&c.model().lay);
    for (j,v) in slice::from_raw_parts_mut(y,x.len()).iter_mut().enumerate() { *v=x[j]/c.d[j]; }
    slice::from_raw_parts_mut(d,x.len()).copy_from_slice(&c.d);
}
#[no_mangle]
pub unsafe extern "C" fn uav_stage(ctx: *mut Context, eps: f64, p: f64, delta: f64) {
    (*ctx).sm = Smooth { eps,p,delta };
}

struct Sink<'a> { lam: &'a [f64], mu: &'a [f64], rho: f64, h: &'a mut [f64], g: &'a mut [f64], val: f64 }
impl Weights for Sink<'_> {
    fn eq(&mut self,i: usize,v: f64)->f64 {
        self.h[i]=v;
        self.val+=(self.lam[i]+0.5*self.rho*v)*v;
        self.lam[i]+self.rho*v
    }
    fn ineq(&mut self,i: usize,v: f64)->f64 {
        self.g[i]=v;
        if self.rho==0. { self.val+=self.mu[i]*v; return self.mu[i]; }
        let w=(self.mu[i]+self.rho*v).max(0.);
        self.val+=(w*w-self.mu[i]*self.mu[i])/(2.*self.rho);
        w
    }
}
fn evaluate(c: &Context,y: &[f64],lam: &[f64],mu: &[f64],rho: f64,
            grad: &mut [f64],h: &mut [f64],g: &mut [f64])->(f64,f64) {
    let x: Vec<f64> = y.iter().zip(&c.d).map(|(y,d)|y*d).collect();
    let mut sink=Sink {lam,mu,rho,h,g,val:0.};
    let f=c.model().eval(&x,&mut sink,grad);
    for (v,d) in grad.iter_mut().zip(&c.d) { *v*=d; }
    (f+sink.val,f)
}
#[no_mangle]
pub unsafe extern "C" fn uav_eval(ctx: *const Context,y: *const f64,lam: *const f64,mu: *const f64,
                                  rho: f64,grad: *mut f64,h: *mut f64,g: *mut f64,f: *mut f64)->f64 {
    let c=&*ctx; let l=c.model().lay;
    let (value,obj)=evaluate(c,slice::from_raw_parts(y,l.n_var()),slice::from_raw_parts(lam,l.n_eq()),
        slice::from_raw_parts(mu,l.n_ineq()),rho,slice::from_raw_parts_mut(grad,l.n_var()),
        slice::from_raw_parts_mut(h,l.n_eq()),slice::from_raw_parts_mut(g,l.n_ineq()));
    *f=obj; value
}
#[no_mangle]
pub unsafe extern "C" fn uav_jacobian(ctx: *const Context,y: *const f64,jac: *mut f64) {
    let c=&*ctx; let m=c.model(); let l=m.lay; let nv=l.n_var();
    let x: Vec<f64> = slice::from_raw_parts(y,nv).iter().zip(&c.d).map(|(y,d)|y*d).collect();
    let rows=slice::from_raw_parts_mut(jac,(l.n_eq()+l.n_ineq())*nv);
    let mut lam=vec![0.;l.n_eq()]; let mut mu=vec![0.;l.n_ineq()];
    let mut obj=vec![0.;nv]; m.eval(&x,&mut model::Recorder::new(&lam,&mu),&mut obj);
    for i in 0..l.n_eq()+l.n_ineq() {
        if i<l.n_eq() {lam[i]=1.;} else {mu[i-l.n_eq()]=1.;}
        let row=&mut rows[i*nv..(i+1)*nv];
        m.eval(&x,&mut model::Recorder::new(&lam,&mu),row);
        for j in 0..nv {row[j]=(row[j]-obj[j])*c.d[j];}
        if i<l.n_eq() {lam[i]=0.;} else {mu[i-l.n_eq()]=0.;}
    }
}
#[no_mangle]
pub unsafe extern "C" fn uav_rust_inner(ctx: *const Context,y: *mut f64,lam: *const f64,mu: *const f64,
                                        rho: f64,max_iter: usize,res: *mut f64) {
    let c=&*ctx; let l=c.model().lay;
    let mut h=vec![0.;l.n_eq()]; let mut g=vec![0.;l.n_ineq()];
    let lam=slice::from_raw_parts(lam,l.n_eq()); let mu=slice::from_raw_parts(mu,l.n_ineq());
    let result=lbfgs::minimize(slice::from_raw_parts_mut(y,l.n_var()),
        |y,grad| evaluate(c,y,lam,mu,rho,grad,&mut h,&mut g).0,
        &lbfgs::Opts {max_iter,..lbfgs::Opts::default()});
    slice::from_raw_parts_mut(res,5).copy_from_slice(&[result.f,result.gnorm,result.iters as f64,
        result.evals as f64,match result.status {lbfgs::Status::Converged=>0.,lbfgs::Status::MaxIter=>1.,
        lbfgs::Status::Stalled=>2.,lbfgs::Status::LineSearchFailed=>3.}]);
}
#[no_mangle]
pub unsafe extern "C" fn uav_json(ctx: *const Context,y: *const f64,buf: *mut u8,capacity: usize)->usize {
    let c=&*ctx; let l=c.model().lay;
    let x: Vec<f64> = slice::from_raw_parts(y,l.n_var()).iter().zip(&c.d).map(|(y,d)|y*d).collect();
    let traj=instance::Traj::from_x(&x,&l,&c.inst,&c.ph);
    let sol=solver::Solution {n_stamps:l.n, init:c.init.clone(),
        metrics:metrics::evaluate(&c.inst,&c.ph,&traj,c.sm),
        init_metrics:metrics::evaluate(&c.inst,&c.ph,&c.init,c.sm),traj,
        stages:vec![],seconds:0.,converged:false};
    let json=output::solution_json(&c.inst,&c.ph,&sol,c.fig1);
    if capacity>=json.len() {std::ptr::copy_nonoverlapping(json.as_ptr(),buf,json.len());}
    json.len()
}
