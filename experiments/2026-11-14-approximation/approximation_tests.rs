// Appended to each experimental Model module; flags set by compare_approximation.py.
#[cfg(test)]
mod approximation_tests {
    use super::*;
    use crate::instance::{self, Traj};

    fn constraints(inst:&Instance,ph:&Phys,tr:&Traj,sm:Smooth)->(Vec<f64>,Vec<f64>) {
        let model=Model::new(inst,ph,tr.r.len(),sm);
        let we=vec![0.;model.lay.n_eq()];let wi=vec![0.;model.lay.n_ineq()];
        let mut rec=Recorder::new(&we,&wi);let mut g=vec![0.;model.lay.n_var()];
        model.eval(&tr.to_x(&model.lay),&mut rec,&mut g);
        (rec.h,rec.g)
    }

    #[test]
    fn scalar_hinge_has_the_intended_zero_set_and_derivative() {
        let d=0.001;
        if super::ZERO_SET_PRESERVED {
            for y in [-2.*d,-d,-d/2.,0.] {assert_eq!(psi(y,d).0,0.);}
            for y in [d/10.,d/2.,d,2.*d] {assert!(psi(y,d).0>0.);}
        } else {assert!((psi(0.,d).0-d/4.).abs()<1e-15);}
        for y in [-2.*d,-d,0.,d/2.,d,2.*d] {
            let h=1e-8;let fd=(psi(y+h,d).0-psi(y-h,d).0)/(2.*h);
            assert!((fd-psi(y,d).1).abs()<1e-5,"y={y}: {fd} vs {}",psi(y,d).1);
        }
    }

    #[test]
    fn original_boundary_charging_fixture_distinguishes_the_changes() {
        let ph=Phys::default();
        let inst=Instance{r0:[1.,0.],rf:[1.,0.],regions:vec![Region{o:[0.,0.],rho:1.}],tasks:vec![[1.,0.]]};
        let tr=Traj{r:vec![[1.,0.];3],e:vec![1.,1.,0.75],s:vec![0.1,0.1],c:vec![0.1,0.]};
        let sm=Smooth{eps:0.0005,p:12.,delta:0.001};
        assert!(crate::metrics::evaluate(&inst,&ph,&tr,sm).viol<1e-12);
        let (h,g)=constraints(&inst,&ph,&tr,sm);
        let hmax=h.iter().map(|x|x.abs()).fold(0.,f64::max);
        let gmax=g.iter().copied().fold(0.,f64::max);
        eprintln!("boundary fixture: zero_set={} inequalities={} equality={hmax:.12e} inequality={gmax:.12e}",super::ZERO_SET_PRESERVED,super::APPROX_INEQUALITIES);
        if !super::APPROX_INEQUALITIES {
            assert!(hmax>1e-6,"Exact task visit remains excluded by the approximate equality");
        } else if !super::ZERO_SET_PRESERVED {
            assert!(hmax<1e-12 && gmax>1e-5,"Original psi still excludes boundary charging");
        } else {assert!(hmax<1e-12 && gmax<1e-12);}
    }

    #[test]
    fn combined_outer_approximation_contains_original_feasible_initials() {
        if !(super::ZERO_SET_PRESERVED && super::APPROX_INEQUALITIES) {return;}
        let ph=Phys::default();let mut instances=vec![instance::fig1()];
        for tau in [1,3,5,7] {for seed in 0..3 {instances.push(instance::random(tau,seed,9.,6.));}}
        let mut checked=0;
        for inst in instances {
            let tr=instance::initial_trajectory(&inst,&ph,&instance::InitOpts::default());
            let last=Smooth{eps:0.0005,p:12.,delta:0.001};
            if crate::metrics::evaluate(&inst,&ph,&tr,last).viol>1e-10 {continue;}
            for sm in [Smooth{eps:0.2,p:2.,delta:0.001},last] {
                let (h,g)=constraints(&inst,&ph,&tr,sm);
                assert!(h.iter().all(|v|v.abs()<1e-10));assert!(g.iter().all(|v|*v<1e-10));
            }
            checked+=1;
        }
        assert_eq!(checked,12);
    }
}
