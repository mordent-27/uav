#![allow(dead_code)]
#[path = "../../src/params.rs"] mod params;
#[path = "../../src/rng.rs"] mod rng;
#[path = "../../src/battery.rs"] mod battery;
#[path = "../../src/model.rs"] mod model;
#[path = "../../src/instance.rs"] mod instance;

fn main() {
    for (tau,seed) in [(2,2_000_001u64),(6,6_000_002u64)] {
        let input=instance::random(tau,seed,9.0,6.0);
        println!("{{\"case\":\"tau{}-seed{}\",\"tasks\":{:?}}}",tau,seed,input.tasks);
    }
}
