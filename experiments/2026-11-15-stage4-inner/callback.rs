//! Expose the unchanged repository L-BFGS with a caller-supplied AL evaluator.
#[path = "../../src/lbfgs.rs"] mod lbfgs;
use std::slice;

type Eval = unsafe extern "C" fn(*const f64, *mut f64) -> f64;

#[no_mangle]
pub unsafe extern "C" fn minimize(n: usize, y: *mut f64, eval: Eval, result: *mut f64) {
    let out = lbfgs::minimize(slice::from_raw_parts_mut(y, n),
        |point, gradient| eval(point.as_ptr(), gradient.as_mut_ptr()),
        &lbfgs::Opts { gtol: 1e-8, max_iter: 2000, ..lbfgs::Opts::default() });
    slice::from_raw_parts_mut(result, 5).copy_from_slice(&[out.f, out.gnorm, out.iters as f64,
        out.evals as f64, match out.status { lbfgs::Status::Converged=>0., lbfgs::Status::MaxIter=>1.,
            lbfgs::Status::Stalled=>2., lbfgs::Status::LineSearchFailed=>3. }]);
}
