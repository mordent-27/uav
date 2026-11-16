"""Analytic PHR examples and a constructed affine-rounding witness."""
import unittest
import numpy as np
from ledger import decompose


class TestLedger(unittest.TestCase):
    def test_equality_and_linear_objective_known_polynomial(self):
        r=decompose([.375],[.125],[],[.5],[],[2.],[],4.,[3.],np.array([[1.]]))
        self.assertEqual(r['stable'],2.34375)
        self.assertEqual(r['equality_penalty_quadratic'],.28125)
        self.assertEqual(r['weighted_equality_residual'],0.)
        self.assertEqual(r['reconstruction_error'],0.)

    def test_phr_inactive_to_active(self):
        r=decompose([1.],[],[-.25],[],[.75],[],[.5],2.,[0.],np.array([[1.]]))
        self.assertEqual(r['stable'],1.)
        self.assertEqual(r['inequality_nonlinear_remainder'],1.)
        self.assertEqual(r['weighted_inequality_residual'],0.)
        self.assertEqual(r['reconstruction_error'],0.)

    def test_phr_active_to_inactive(self):
        r=decompose([-1.],[],[.75],[],[-.25],[],[.5],2.,[0.],np.array([[1.]]))
        self.assertEqual(r['stable'],-1.)
        self.assertEqual(r['inequality_nonlinear_remainder'],1.)
        self.assertEqual(r['reconstruction_error'],0.)

    def test_no_change(self):
        r=decompose([0.],[.25],[.5],[.25],[.5],[2.],[1.],3.,[4.],np.array([[1.],[2.]]))
        self.assertEqual(r['stable'],0.);self.assertEqual(r['reconstruction_error'],0.)

    def test_rounding_in_affine_constraint_amplified_by_multiplier(self):
        # The affine constraint's true change is 1e-17, but adding it to
        # the double-precision value 1 rounds back to 1.
        self.assertEqual(float(1.+1e-17),1.)
        r=decompose([1e-17],[],[1.],[],[1.],[],[1e8],2.,[0.],np.array([[1.]]))
        self.assertEqual(r['stable'],0.)
        self.assertAlmostEqual(r['weighted_inequality_residual'],-(1e8+2.)*1e-17,places=23)
        self.assertAlmostEqual(r['jacobian_linear'],(1e8+2.)*1e-17,places=23)
        self.assertEqual(r['reconstruction_error'],0.)


if __name__=='__main__':unittest.main()
