import math
import unittest
from metrics import distribution,missing_median_bounds,failure_aware_cdf,objective_from_point


class TestMetrics(unittest.TestCase):
    def test_linear_quantiles_known_sample(self):
        d=distribution([0.,1.,2.,3.]);self.assertEqual(d['median'],1.5);self.assertEqual(d['q25'],.75);self.assertEqual(d['q75'],2.25)

    def test_empty_and_nonfinite(self):
        self.assertIsNone(distribution([])['median'])
        for x in [float('nan'),float('inf'),-1.]:
            with self.assertRaises(ValueError):distribution([x])

    def test_missing_cases_do_not_become_zero_objectives(self):
        values=list(range(1,99));self.assertEqual(distribution(values)['median'],49.5)
        self.assertEqual(missing_median_bounds(values,100),(48.5,50.5))

    def test_missing_bounds_and_complete_population(self):
        self.assertEqual(missing_median_bounds([2.,4.],2),(3.,3.))
        self.assertEqual(missing_median_bounds([],2),(0.,math.inf))
        with self.assertRaises(ValueError):missing_median_bounds([1.,2.],1)

    def test_cdf_keeps_failed_instances_in_denominator(self):
        self.assertEqual(failure_aware_cdf([1.,2.],3,10.),2/3)
        self.assertEqual(failure_aware_cdf([1.,2.],3,1.),1/3)

    def test_mission_time_is_not_solver_seconds(self):
        point=dict(solution=dict(s=[.25,.75]),metrics=dict(objective=1.,seconds=9999.))
        self.assertEqual(objective_from_point(point,1.),1.)
        with self.assertRaises(ValueError):objective_from_point(point,1.01)


if __name__=='__main__':unittest.main()
