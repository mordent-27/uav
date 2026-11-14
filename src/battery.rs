//! CC-CV charging map f_c (eq. 26) and its inverse in time.

use crate::params::Phys;

/// Largest exponent passed to exp(); keeps wild line-search trial points finite.
const EXP_CAP: f64 = 60.0;

/// f_c(e, c): battery level after charging for duration `c` from level `e`.
/// Returns (value, d/de, d/dc).
///
/// For c >= 0 this is eq. (26). The paper defines it only there, and read literally for c < 0
/// it jumps across e = e_th, which stalls a solver that keeps c >= 0 only through a penalty.
/// Here f_c(e, c) is the flow of the charging ODE (de/dt = kappa below e_th, (e_max - e) / sigma
/// above) for a signed time c, which agrees with (26) for c >= 0 and is C^1 everywhere.
pub fn charge(ph: &Phys, e: f64, c: f64) -> (f64, f64, f64) {
    let sigma = ph.sigma();
    let span = ph.e_max - ph.e_th;
    let cv = |c: f64| {
        let ex = (-c / sigma).min(EXP_CAP).exp();
        (ph.e_max - (ph.e_max - e) * ex, ex, (ph.e_max - e) / sigma * ex)
    };
    if c >= 0.0 {
        if e >= ph.e_th {
            return cv(c);
        }
        let tau = (ph.e_th - e) / ph.kappa;
        if c <= tau {
            (e + ph.kappa * c, 1.0, ph.kappa)
        } else {
            let ex = (-(c - tau) / sigma).exp();
            (ph.e_max - span * ex, ex, ph.kappa * ex)
        }
    } else {
        if e <= ph.e_th {
            return (e + ph.kappa * c, 1.0, ph.kappa);
        }
        // Time the CV phase takes from e_th up to e; flowing back longer than that re-enters CC.
        let back = if e < ph.e_max { sigma * (span / (ph.e_max - e)).ln() } else { f64::INFINITY };
        if -c <= back {
            cv(c)
        } else {
            (ph.e_th + ph.kappa * (c + back), span / (ph.e_max - e), ph.kappa)
        }
    }
}

/// Unified dynamics (eq. 6): f(e, s, c) = f_c(e, c) + f_d(e, s - c) - e.
pub fn step(ph: &Phys, e: f64, s: f64, c: f64) -> f64 {
    charge(ph, e, c).0 - ph.zeta * (s - c)
}

/// Charging time needed to go from `e` to `target` (< e_max).
pub fn time_to_charge(ph: &Phys, e: f64, target: f64) -> f64 {
    if e >= target {
        return 0.0;
    }
    let sigma = ph.sigma();
    let cv = |from: f64| sigma * ((ph.e_max - from) / (ph.e_max - target)).ln();
    if e >= ph.e_th {
        cv(e)
    } else if target <= ph.e_th {
        (target - e) / ph.kappa
    } else {
        (ph.e_th - e) / ph.kappa + cv(ph.e_th)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn identity_at_zero_duration() {
        let ph = Phys::default();
        for e in [0.0, 0.3, 0.7, 0.9] {
            assert!((charge(&ph, e, 0.0).0 - e).abs() < 1e-14);
        }
    }

    #[test]
    fn semigroup() {
        // Charging for a then b equals charging for a + b: splitting a segment changes nothing.
        let ph = Phys::default();
        for e in [0.05, 0.5, 0.69, 0.8] {
            for (a, b) in [(0.01, 0.02), (0.1, 0.05), (0.2, 0.3)] {
                let two = charge(&ph, charge(&ph, e, a).0, b).0;
                let one = charge(&ph, e, a + b).0;
                assert!((two - one).abs() < 1e-12, "e={e} a={a} b={b}");
            }
        }
    }

    #[test]
    fn derivatives_match_finite_differences() {
        let ph = Phys::default();
        let h = 1e-6;
        for e in [0.1, 0.5, 0.69, 0.71, 0.9] {
            for c in [-0.3, -0.05, -0.01, 0.01, 0.05, 0.1, 0.3] {
                let (_, de, dc) = charge(&ph, e, c);
                let fe = (charge(&ph, e + h, c).0 - charge(&ph, e - h, c).0) / (2.0 * h);
                let fc = (charge(&ph, e, c + h).0 - charge(&ph, e, c - h).0) / (2.0 * h);
                assert!((de - fe).abs() < 1e-5, "de e={e} c={c}: {de} vs {fe}");
                assert!((dc - fc).abs() < 1e-4, "dc e={e} c={c}: {dc} vs {fc}");
            }
        }
    }

    #[test]
    fn continuous_across_threshold_for_any_sign_of_c() {
        let ph = Phys::default();
        for c in [-0.2, -0.01, 0.0, 0.01, 0.2] {
            let lo = charge(&ph, ph.e_th - 1e-9, c).0;
            let hi = charge(&ph, ph.e_th + 1e-9, c).0;
            assert!((lo - hi).abs() < 1e-7, "c={c}: {lo} vs {hi}");
        }
    }

    #[test]
    fn negative_duration_inverts_charging() {
        let ph = Phys::default();
        for e in [0.1, 0.6, 0.75, 0.95] {
            for c in [0.01, 0.05, 0.2] {
                let up = charge(&ph, e, c).0;
                assert!((charge(&ph, up, -c).0 - e).abs() < 1e-12, "e={e} c={c}");
            }
        }
    }

    #[test]
    fn time_to_charge_inverts_charge() {
        let ph = Phys::default();
        for e in [0.0, 0.4, 0.75] {
            for target in [0.5, 0.7, 0.9, 0.99] {
                if target <= e {
                    continue;
                }
                let t = time_to_charge(&ph, e, target);
                assert!((charge(&ph, e, t).0 - target).abs() < 1e-12);
            }
        }
    }
}
