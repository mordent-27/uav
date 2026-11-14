#![allow(dead_code)]
#[path = "../../src/params.rs"] mod params;
#[path = "../../src/battery.rs"] mod battery;
#[path = "../../src/model.rs"] mod model;

#[no_mangle]
pub unsafe extern "C" fn trace_min(z: *const f64, n: usize, p: f64, derivative: *mut f64) -> f64 {
    model::smooth_min(std::slice::from_raw_parts(z, n), p, std::slice::from_raw_parts_mut(derivative, n))
}
#[no_mangle]
pub unsafe extern "C" fn trace_psi(y: f64, delta: f64, output: *mut f64) {
    let (value, derivative) = model::psi(y, delta);
    std::slice::from_raw_parts_mut(output, 2).copy_from_slice(&[value, derivative]);
}
