import unittest
from analyze import blockers, hessian_counts, next_penalty, target


class DiagnosisTests(unittest.TestCase):
    def test_carried_cases_excluded(self):
        row=dict(origin='2026-11-16-r3s-cohort',G=dict(stage=1,stop='timeout'))
        self.assertTrue(target(row))
        self.assertFalse(target(dict(row,origin='2026-11-16-r3a-cohort')))
        self.assertFalse(target(dict(row,G=dict(stage=13,stop='timeout'))))

    def test_kkt_components_overlap(self):
        self.assertEqual(blockers(dict(stat=1e-3,feas=1e-4,comp=1e-6,dual=0)),dict(stat=True,feas=True,comp=False,dual=False))

    def test_finite_difference_count(self):
        self.assertTrue(hessian_counts(2,dict(hessian_gradient_calls=15,jacobian_calls=3)))
        self.assertFalse(hessian_counts(2,dict(hessian_gradient_calls=12,jacobian_calls=3)))

    def test_penalty_gate_requires_inner_accuracy(self):
        self.assertEqual(next_penalty(1e4,.1,.1,1e-3,False),1e4)
        self.assertEqual(next_penalty(1e4,.1,.1,1e-7,False),1e5)
        self.assertEqual(next_penalty(1e4,.1,float('inf'),1e-7,False),1e4)
        self.assertEqual(next_penalty(1e8,.1,.1,1e-7,False),1e8)


if __name__=='__main__':
    unittest.main()
