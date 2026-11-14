#![allow(dead_code)]
#[path="../../src/params.rs"] mod params;
#[path="../../src/battery.rs"] mod battery;

#[no_mangle]
pub unsafe extern "C" fn charge_value_gradient(e:f64,t:f64,out:*mut f64) {
    let (value,de,dt)=battery::charge(&params::Phys::default(),e,t);
    std::slice::from_raw_parts_mut(out,3).copy_from_slice(&[value,de,dt]);
}
