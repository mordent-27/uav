import unittest
from diagnostics import domain_distance,branch_bounds,softmin,psi


class BoundTests(unittest.TestCase):
    def test_free_region_endpoints(self):
        self.assertEqual(domain_distance(dict(center=[0,0],radius=3),dict(center=[10,0],radius=3)),4)

    def test_overlapping_regions(self):
        self.assertEqual(domain_distance(dict(center=[0,0],radius=8),dict(center=[10,0],radius=3)),0)

    def test_task_route_bound(self):
        data=dict(instance=dict(r0=[0,0],rf=[25,0],tasks=[[5,0]],regions=[dict(o=[20,0],rho=1)]),
                  phys=dict(v_d=36,zeta=2.5,e_max=1,e_min=0),modes=[-1,-1,0],task_stamp=[1])
        r=branch_bounds(data)[0];self.assertEqual(r['flight_lower_bound_km'],19)
        self.assertTrue(r['infeasible_branch_proven'])

    def test_smoothing_conventions(self):
        self.assertEqual(psi(-.002),0);self.assertAlmostEqual(psi(0),.00025)
        self.assertAlmostEqual(softmin([1,1],2),2**-.5)


if __name__=='__main__':unittest.main()
