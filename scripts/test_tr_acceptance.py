import unittest
from tr_acceptance import assess


class TestAcceptance(unittest.TestCase):
    def decide(self,**changes):
        args=dict(value=1.,trial_value=.5,prediction=.5,gradient_norm=2.,
            trial_gradient_norm=1.,radius=1.,step_norm=1.,boundary=True)
        args.update(changes);return assess(**args)

    def test_exact_quadratic_boundary_expands(self):
        # f(x)=x²/2 at x=2, step=-1: actual=model decrease=1.5.
        d=self.decide(value=2.,trial_value=.5,prediction=1.5)
        self.assertTrue(d.accepted);self.assertEqual(d.ratio,1.);self.assertEqual(d.radius,2.)

    def test_exact_quadratic_interior_keeps_radius(self):
        d=self.decide(boundary=False,step_norm=.5)
        self.assertTrue(d.accepted);self.assertEqual(d.radius,1.)

    def test_uphill_trial_rejected_and_radius_uses_step_length(self):
        d=self.decide(trial_value=1.5,step_norm=.4)
        self.assertFalse(d.accepted);self.assertEqual(d.radius,.1)

    def test_acceptance_threshold_is_strict(self):
        for ratio,expected in [(1e-4,False),(1.01e-4,True)]:
            with self.subTest(ratio=ratio):
                d=self.decide(value=0.,trial_value=-ratio,prediction=1.)
                self.assertEqual(d.accepted,expected)

    def test_radius_thresholds_are_strict(self):
        for ratio,expected in [(.249,.25),(.25,1.),(.75,1.),(.751,2.)]:
            with self.subTest(ratio=ratio):
                self.assertEqual(self.decide(value=0.,trial_value=-ratio,prediction=1.).radius,expected)

    def test_growth_has_cap(self):
        self.assertEqual(self.decide(radius=800.,step_norm=800.).radius,1000.)

    def test_gradient_fallback_requires_strict_gradient_decrease(self):
        for norm,accepted in [(1.,True),(2.,False),(3.,False)]:
            with self.subTest(norm=norm):
                d=self.decide(prediction=0.,trial_gradient_norm=norm)
                self.assertTrue(d.gradient_fallback);self.assertEqual(d.accepted,accepted)

    def test_legacy_can_accept_uphill_with_negative_model_prediction(self):
        # This is a recorded policy limitation, not a descent guarantee.
        d=self.decide(trial_value=2.,prediction=-1.)
        self.assertTrue(d.gradient_fallback);self.assertTrue(d.accepted)

    def test_legacy_constant_offset_can_change_decision(self):
        base=self.decide(value=0.,trial_value=1e-6,prediction=1e-6)
        shifted=self.decide(value=1e8,trial_value=1e8+1e-6,prediction=1e-6)
        self.assertFalse(base.accepted);self.assertFalse(base.gradient_fallback)
        self.assertTrue(shifted.accepted);self.assertTrue(shifted.gradient_fallback)

    def test_stable_reduction_changes_ratio_but_not_fallback_branch(self):
        d=self.decide(value=1.,trial_value=1.,prediction=.5,actual_decrease=.5)
        self.assertTrue(d.accepted);self.assertEqual(d.ratio,1.)
        d=self.decide(prediction=0.,trial_gradient_norm=3.,actual_decrease=10.)
        self.assertTrue(d.gradient_fallback);self.assertFalse(d.accepted)

    def test_invalid_inputs(self):
        for changes in [dict(value=float('nan')),dict(prediction=float('inf')),dict(radius=0.),
                        dict(step_norm=2.),dict(gradient_norm=-1.),dict(actual_decrease=float('nan'))]:
            with self.subTest(changes=changes):
                with self.assertRaises(ValueError):self.decide(**changes)


if __name__=='__main__':unittest.main()
