// Appended to the mode-scaled Model module by compare_scaling.py.
#[cfg(test)]
mod scaling_tests {
    use super::*;
    use crate::instance::{self, Traj};
    use crate::rng::Rng;

    const L0: f64 = 1.0; // km
    const T0: f64 = 1.0 / 36.0; // h

    // Simulate reporting in arbitrary length/time units, then nondimensionalize.
    fn convert(inst: &Instance, ph: &Phys, tr: &Traj, length: f64, time: f64)
        -> (Instance, Phys, Traj)
    {
        let lref=L0*length;
        let tref=T0*time;
        let pos=|r: V2| [r[0]*length/lref,r[1]*length/lref];
        let ih=Instance {r0:pos(inst.r0),rf:pos(inst.rf),
            tasks:inst.tasks.iter().map(|&r|pos(r)).collect(),
            regions:inst.regions.iter().map(|r|Region{o:pos(r.o),rho:r.rho*length/lref}).collect()};
        let mut p=ph.clone();
        p.v_d=(ph.v_d*length/time)*tref/lref;
        p.v_c=(ph.v_c*length/time)*tref/lref;
        p.kappa=(ph.kappa/time)*tref;
        p.zeta=(ph.zeta/time)*tref;
        p.s_min=(ph.s_min*time)/tref;
        p.s_max=(ph.s_max*time)/tref;
        let t=Traj {r:tr.r.iter().map(|&r|pos(r)).collect(),e:tr.e.clone(),
            s:tr.s.iter().map(|s|s*time/tref).collect(),
            c:tr.c.iter().map(|c|c*time/tref).collect()};
        (ih,p,t)
    }

    fn weights(lay: Layout) -> (Vec<f64>,Vec<f64>) {
        ((0..lay.n_eq()).map(|i|0.3*(i as f64+1.).sin()).collect(),
         (0..lay.n_ineq()).map(|i|0.3*(i as f64+2.).cos()).collect())
    }

    fn eval(model: &Model, tr: &Traj) -> (f64,Vec<f64>,Vec<f64>) {
        let (we,wi)=weights(model.lay);
        let mut rec=Recorder::new(&we,&wi);
        let mut g=vec![0.;model.lay.n_var()];
        let f=model.eval(&tr.to_x(&model.lay),&mut rec,&mut g);
        let mut constraints=rec.h;
        constraints.extend(rec.g);
        (f,constraints,g)
    }

    fn near(a: f64,b: f64) { assert!((a-b).abs()/(1.+a.abs()) < 1e-10,"{a} vs {b}"); }

    fn sample(inst: &Instance, ph: &Phys) -> Traj {
        let init=instance::initial_trajectory(inst,ph,&instance::InitOpts::default());
        let lay=Model::new(inst,ph,init.r.len(),Smooth{eps:0.2,p:2.,delta:0.001}).lay;
        let mut x=init.to_x(&lay);
        let scales=Model::new(inst,ph,init.r.len(),Smooth{eps:0.2,p:2.,delta:0.001}).var_scale();
        let mut rng=Rng::new(83);
        for (v,d) in x.iter_mut().zip(scales) { *v+=0.03*d*(rng.uniform()-0.5); }
        Traj::from_x(&x,&lay,inst,ph)
    }

    #[test]
    fn all_constraints_and_physical_gradients_are_unit_invariant() {
        let ph=Phys::default();
        for inst in [instance::fig1(),instance::random(3,1,9.,6.)] {
            let tr=sample(&inst,&ph);
            for sm in [Smooth{eps:0.2,p:2.,delta:0.001},
                       Smooth{eps:0.01,p:6.,delta:0.001},
                       Smooth{eps:0.0005,p:12.,delta:0.001}] {
                let (ih,pp,th)=convert(&inst,&ph,&tr,1.,1.);
                let reference=Model::new(&ih,&pp,th.r.len(),sm);
                let (fr,cr,gr)=eval(&reference,&th);
                for (length,time) in [(1.,1.),(1000.,1.),(1.,3600.),(1000.,3600.)] {
                    let (ih,pp,th)=convert(&inst,&ph,&tr,length,time);
                    let model=Model::new(&ih,&pp,th.r.len(),sm);
                    let (f,c,g)=eval(&model,&th);
                    near(f,fr);
                    for (a,b) in c.iter().zip(&cr) {near(*a,*b);}
                    for k in 0..model.lay.n {
                        if let Some(i)=model.lay.r(k) {
                            // dL/dr_reported, then dL/dr_km.
                            near(g[i]/(L0*length)*length,gr[i]/L0);
                            near(g[i+1]/(L0*length)*length,gr[i+1]/L0);
                        }
                        if let Some(i)=model.lay.e(k) {near(g[i],gr[i]);}
                    }
                    for k in 0..model.lay.n-1 {
                        for i in [model.lay.s(k),model.lay.c(k)] {
                            near(g[i]/(T0*time)*time,gr[i]/T0);
                        }
                    }
                }
            }
        }
    }

    #[test]
    fn physical_mode_scaling_and_dimensionless_constraints_correspond() {
        let inst=instance::fig1();let ph=Phys::default();let tr=sample(&inst,&ph);
        for sm in [Smooth{eps:0.2,p:2.,delta:0.001},Smooth{eps:0.0005,p:12.,delta:0.001}] {
            let physical=Model::new(&inst,&ph,tr.r.len(),sm);
            let (ih,pp,th)=convert(&inst,&ph,&tr,1.,1.);
            let normalized=Model::new(&ih,&pp,th.r.len(),sm);
            let (fp,cp,mut gp)=eval(&physical,&tr);
            let (fh,ch,mut gh)=eval(&normalized,&th);
            near(fh,fp/T0);
            for (a,b) in cp.iter().zip(ch) {near(*a,b);}
            // Remove the differently scaled objective before checking constraint gradients.
            for k in 0..physical.lay.n-1 {
                gp[physical.lay.s(k)]-=1.;gh[normalized.lay.s(k)]-=1.;
            }
            for k in 0..physical.lay.n {
                if let Some(i)=physical.lay.r(k) {near(gp[i],gh[i]/L0);near(gp[i+1],gh[i+1]/L0);}
                if let Some(i)=physical.lay.e(k) {near(gp[i],gh[i]);}
            }
            for k in 0..physical.lay.n-1 {
                near(gp[physical.lay.s(k)],gh[normalized.lay.s(k)]/T0);
                near(gp[physical.lay.c(k)],gh[normalized.lay.c(k)]/T0);
            }
        }
    }

    #[test]
    fn dimensionless_gradient_matches_finite_differences() {
        let inst=instance::fig1();let ph=Phys::default();let tr=sample(&inst,&ph);
        let (ih,pp,th)=convert(&inst,&ph,&tr,1000.,3600.);
        for sm in [Smooth{eps:0.2,p:2.,delta:0.001},Smooth{eps:0.0005,p:12.,delta:0.001}] {
            let model=Model::new(&ih,&pp,th.r.len(),sm);
            let mut x=th.to_x(&model.lay);
            let (we,wi)=weights(model.lay);
            let lag=|x:&[f64],g:&mut[f64]| {
                let mut rec=Recorder::new(&we,&wi);let f=model.eval(x,&mut rec,g);f+rec.val
            };
            let mut g=vec![0.;x.len()];lag(&x,&mut g);
            let mut scratch=vec![0.;x.len()];
            for i in 0..x.len() {
                let old=x[i];let h=1e-6;
                x[i]=old+h;let fp=lag(&x,&mut scratch);
                x[i]=old-h;let fm=lag(&x,&mut scratch);x[i]=old;
                let fd=(fp-fm)/(2.*h);
                assert!((fd-g[i]).abs()/(1.+fd.abs())<1e-5,"var {i}: {} vs {fd}",g[i]);
            }
        }
    }
}
