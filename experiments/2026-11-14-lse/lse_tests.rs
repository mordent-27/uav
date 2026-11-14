#[cfg(test)]
mod lse_tests {
    use super::*;

    #[test]
    fn calibration_and_tie_gradients_match_the_intended_bounds() {
        for n in [1,3,5,37] {for eps in [0.2,0.0005] {for p in [2.,12.] {
            let tied=eps*(n as f64).powf(1./p);let z=vec![tied;n];
            let mut d=vec![0.;n];let value=matched_lse(&z,p,eps,&mut d);
            assert!((value-eps).abs()<1e-12);
            for v in &d {assert!((*v-1./n as f64).abs()<1e-12);}
            if super::SCALE_LSE_RESIDUAL {
                let mut lp=vec![0.;n];smooth_min(&z,p,&mut lp);
                let beta=(n as f64).powf(-1./p);
                for (a,b) in d.iter().zip(lp) {assert!((beta*a-b).abs()<1e-12);}
            }
            if n>1 {
                let tau=lse_temperature(n,p,eps);
                assert!((eps+tau*(n as f64).ln()-tied).abs()<1e-12);
            }
        }}}
    }

    #[test]
    fn shifted_lse_is_finite_and_its_gradient_matches_differences() {
        let eps=0.0005;
        for z in [vec![eps,eps,eps],vec![eps,eps*1.1,eps*3.],vec![1000.,1001.,1e6]] {
            for p in [2.,12.] {
                let mut d=vec![0.;z.len()];let v=matched_lse(&z,p,eps,&mut d);
                let m=z.iter().copied().fold(f64::INFINITY,f64::min);
                let tau=lse_temperature(z.len(),p,eps);
                assert!(v.is_finite() && d.iter().all(|x|x.is_finite()));
                assert!(v<=m+1e-12 && v>=m-tau*(z.len() as f64).ln()-1e-12);
                assert!((d.iter().sum::<f64>()-1.).abs()<1e-12);
                for i in 0..z.len() {
                    let mut a=z.clone();let mut b=z.clone();let h=1e-7;a[i]+=h;b[i]-=h;
                    let mut scratch=vec![0.;z.len()];
                    let fd=(matched_lse(&a,p,eps,&mut scratch)-matched_lse(&b,p,eps,&mut scratch))/(2.*h);
                    assert!((fd-d[i]).abs()/(1.+fd.abs())<1e-5,"p={p} i={i}: {} vs {fd}",d[i]);
                }
            }
        }
    }

    #[test]
    fn task_constraint_uses_lse_in_the_actual_model() {
        let ph=Phys::default();let sm=Smooth{eps:0.0005,p:12.,delta:0.001};
        let inst=Instance{r0:[1.,0.],rf:[1.,0.],regions:vec![Region{o:[0.,0.],rho:1.}],tasks:vec![[1.,0.]]};
        let tr=crate::instance::Traj{r:vec![[1.,0.];3],e:vec![1.,1.,0.75],s:vec![0.1,0.1],c:vec![0.1,0.]};
        let model=Model::new(&inst,&ph,3,sm);let we=vec![0.;model.lay.n_eq()];let wi=vec![0.;model.lay.n_ineq()];
        let mut rec=Recorder::new(&we,&wi);let mut g=vec![0.;model.lay.n_var()];
        model.eval(&tr.to_x(&model.lay),&mut rec,&mut g);
        let beta=if super::SCALE_LSE_RESIDUAL {(3.0f64).powf(-1./sm.p)}else{1.};
        let expected=-beta*lse_temperature(3,sm.p,sm.eps)*(3.0f64).ln();
        assert!((rec.g[model.lay.ineq_task(0)]-expected).abs()<1e-12);
    }
}
