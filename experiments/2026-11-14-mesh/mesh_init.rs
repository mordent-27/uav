//! Initial-trajectory transformations, isolated from the solver and model.
use crate::battery::step;
use crate::instance::Traj;
use crate::model::{Model, Recorder};
use crate::params::*;

pub fn refine(original: &Traj, ph: &Phys) -> Traj {
    let mut tr=Traj {r:vec![original.r[0]],e:vec![original.e[0]],s:vec![],c:vec![]};
    for k in 0..original.s.len() {
        let (s,c)=(original.s[k],original.c[k]);
        assert!(c==0. || c==s,"Refine only a pure-mode initial trajectory");
        if s>=2.*ph.s_min {
            tr.r.push([(original.r[k][0]+original.r[k+1][0])/2.,
                       (original.r[k][1]+original.r[k+1][1])/2.]);
            tr.e.push(step(ph,original.e[k],s/2.,c/2.));
            tr.s.extend([s/2.,s/2.]);tr.c.extend([c/2.,c/2.]);
        } else {tr.s.push(s);tr.c.push(c);}
        tr.r.push(original.r[k+1]);tr.e.push(original.e[k+1]);
    }
    tr
}

pub fn log_smoothing(inst: &Instance,ph: &Phys,tr: &Traj,schedule: &[Smooth]) {
    for sm in [schedule[0],*schedule.last().unwrap()] {
        let model=Model::new(inst,ph,tr.r.len(),sm);
        let we=vec![0.;model.lay.n_eq()];let wi=vec![0.;model.lay.n_ineq()];
        let mut rec=Recorder::new(&we,&wi);let mut grad=vec![0.;model.lay.n_var()];
        model.eval(&tr.to_x(&model.lay),&mut rec,&mut grad);
        let ns=tr.s.len();
        let task=rec.h[ns..ns+inst.tasks.len()].iter().fold(0.0f64,|a,b|a.max(b.abs()));
        let mode=rec.h[ns+inst.tasks.len()..].iter().fold(0.0f64,|a,b|a.max(b.abs()));
        eprintln!("INITSMOOTH eps={:.12e} p={:.12e} task={:.12e} mode={:.12e}",sm.eps,sm.p,task,mode);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::instance::{self,InitOpts};

    fn at(tr:&Traj,ph:&Phys,t:f64)->(V2,f64) {
        let mut elapsed=0.;
        for k in 0..tr.s.len() {
            if t<=elapsed+tr.s[k]+1e-14 || k+1==tr.s.len() {
                let dt=(t-elapsed).clamp(0.,tr.s[k]);let a=dt/tr.s[k];
                let r=[tr.r[k][0]+a*(tr.r[k+1][0]-tr.r[k][0]),
                       tr.r[k][1]+a*(tr.r[k+1][1]-tr.r[k][1])];
                let c=if tr.c[k]==0. {0.} else {dt};
                return (r,step(ph,tr.e[k],dt,c));
            }
            elapsed+=tr.s[k];
        }
        unreachable!()
    }

    #[test]
    fn legal_refinement_preserves_the_entire_physical_history() {
        let ph=Phys::default();
        for inst in [instance::fig1(),instance::random(3,1,9.,6.)] {
            let original=instance::initial_trajectory(&inst,&ph,&InitOpts::default());
            let refined=refine(&original,&ph);
            let split=original.s.iter().filter(|&&s|s>=2.*ph.s_min).count();
            assert_eq!(refined.r.len(),original.r.len()+split);
            assert!((refined.total_time()-original.total_time()).abs()<1e-12);
            assert!(refined.s.iter().all(|s|*s>=ph.s_min && *s<=ph.s_max));
            for i in 0..=400 {
                let t=original.total_time()*i as f64/400.;
                let (r,e)=at(&original,&ph,t);let (rr,ee)=at(&refined,&ph,t);
                assert!(dist(r,rr)<1e-10);assert!((e-ee).abs()<1e-10);
            }
            let sm=Smooth{eps:0.0005,p:12.,delta:0.001};
            let before=crate::metrics::evaluate(&inst,&ph,&original,sm);
            let after=crate::metrics::evaluate(&inst,&ph,&refined,sm);
            assert!(after.viol<=before.viol+1e-10);
        }
    }

    #[test]
    fn original_event_stamps_and_energy_are_retained() {
        let ph=Phys::default();let inst=instance::fig1();
        let tr=instance::initial_trajectory(&inst,&ph,&InitOpts::default());let rr=refine(&tr,&ph);
        let mut j=0;
        for k in 0..tr.r.len() {
            assert_eq!(tr.r[k],rr.r[j]);assert_eq!(tr.e[k],rr.e[j]);
            if k<tr.s.len() {j+=if tr.s[k]>=2.*ph.s_min {2} else {1};}
        }
        assert_eq!(j+1,rr.r.len());
    }

    #[test]
    fn refined_layout_gradient_matches_finite_differences() {
        let inst=instance::fig1();let ph=Phys::default();
        let tr=refine(&instance::initial_trajectory(&inst,&ph,&InitOpts::default()),&ph);
        let model=Model::new(&inst,&ph,tr.r.len(),Smooth{eps:0.01,p:6.,delta:0.001});
        let mut x=tr.to_x(&model.lay);let mut rng=crate::rng::Rng::new(41);
        for (v,d) in x.iter_mut().zip(model.var_scale()) {*v+=0.03*d*(rng.uniform()-0.5);}
        let we:Vec<f64>=(0..model.lay.n_eq()).map(|_|rng.uniform()-0.5).collect();
        let wi:Vec<f64>=(0..model.lay.n_ineq()).map(|_|rng.uniform()).collect();
        let lag=|x:&[f64],g:&mut[f64]| {let mut rec=Recorder::new(&we,&wi);let f=model.eval(x,&mut rec,g);f+rec.val};
        let mut g=vec![0.;x.len()];let mut scratch=vec![0.;x.len()];lag(&x,&mut g);
        let scales=model.var_scale();
        for i in 0..x.len() {
            // Differentiate in the same preconditioned coordinates as L-BFGS.
            // A common physical step mixes km, hours and battery fractions.
            let old=x[i];let h=1e-6;x[i]=old+h*scales[i];let fp=lag(&x,&mut scratch);
            x[i]=old-h*scales[i];let fm=lag(&x,&mut scratch);x[i]=old;
            let fd=(fp-fm)/(2.*h);let analytic=g[i]*scales[i];
            assert!((fd-analytic).abs()/(1.+fd.abs())<1e-5,"{i}: {analytic} vs {fd}");
        }
    }
}
