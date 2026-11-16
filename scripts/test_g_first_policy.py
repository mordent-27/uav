"""Preserve G and precision semantics; fallback must not be evaluated on acceptance."""
import copy
import unittest
import g_first_policy as policy


class PolicyTests(unittest.TestCase):
    def valid(self):
        return dict(last_restoration_solver_accepted=True,final_common_kkt=True,
            final_both_scales_kkt=False,physical_point_available=True,
            selected_same_final_branch_kkt=True,selected_hours=2.)

    def test_g_is_kept_without_calling_or_comparing_fallback(self):
        g=self.valid();before=copy.deepcopy(g)
        def forbidden():raise AssertionError('must not evaluate a second route')
        result=policy.select(g,forbidden)
        self.assertEqual(result['route'],'G')
        self.assertFalse(result['fallback_called'])
        self.assertEqual(result['outcome'],before)
        self.assertFalse(result['outcome']['final_both_scales_kkt'])
        self.assertEqual(g,before)

    def test_g_failure_calls_fallback_once_without_promoting_kkt(self):
        g=self.valid();g['last_restoration_solver_accepted']=False
        calls=[];fallback=dict(physical_point_available=True,final_common_kkt=False)
        def supply():calls.append(1);return fallback
        result=policy.select(g,supply)
        self.assertEqual(calls,[1])
        self.assertEqual(result['route'],'fallback')
        self.assertFalse(result['outcome']['final_common_kkt'])

    def test_inconsistent_accepted_g_is_an_error(self):
        g=self.valid();g['selected_same_final_branch_kkt']=False
        with self.assertRaises(ValueError):policy.select(g,lambda:None)

    def test_failed_fallback_does_not_become_success(self):
        g=self.valid();g['last_restoration_solver_accepted']=False
        result=policy.select(g,lambda:dict(physical_point_available=False))
        self.assertFalse(result['outcome']['physical_point_available'])


if __name__=='__main__':unittest.main()
