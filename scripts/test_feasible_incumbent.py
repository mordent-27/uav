"""Prevent branch/input confusion and preserve an already accepted output exactly."""
import copy
import json
from pathlib import Path
import unittest

import feasible_incumbent as incumbent

ROOT=Path(__file__).resolve().parents[1]


def load(path):return json.loads((ROOT/path).read_text())


class IncumbentTests(unittest.TestCase):
    def setUp(self):
        self.initial=load('experiments/2026-11-15-r2f-general-init/initializations/tau5-seed3/solution.json')
        self.restored=load('experiments/2026-11-15-r2d-fallback/cases/direct/tau5-seed3/restored/solution.json')
        self.certificate=load('experiments/2026-11-15-r2f-general-init/diagnostics/tau5-seed3/incumbent.json')

    def test_accepted_output_is_kept_even_if_backup_is_faster(self):
        candidates=dict(restoration=self.restored,initialization=self.initial)
        before=copy.deepcopy(candidates)
        output,report=incumbent.select(self.initial,candidates)
        self.assertEqual(report['selected'],'restoration')
        self.assertEqual(output,self.restored)
        self.assertEqual(candidates,before)

    def test_recomputed_certificate_can_be_returned_after_solver_failure(self):
        output,report=incumbent.select(self.initial,dict(certificate=self.certificate,initialization=self.initial))
        self.assertTrue(report['feasible_available'])
        self.assertEqual(report['selected'],'certificate')
        self.assertEqual(output,self.certificate)

    def test_different_input_and_forged_flags_are_not_accepted(self):
        changed=copy.deepcopy(self.initial);changed['instance']['tasks'][0][0]+=1.
        forged=copy.deepcopy(self.initial);forged['solution']['e'][1]=-1.
        forged['diagnostic']['branch_kkt_pass']=True
        output,report=incumbent.select(self.initial,dict(changed=changed,forged=forged))
        self.assertIsNone(output)
        self.assertEqual(report['candidates']['changed']['reason'],'different_problem')
        self.assertFalse(report['candidates']['forged']['accepted'])

    def test_other_assignment_cannot_reuse_a_certificate(self):
        changed=copy.deepcopy(self.initial);changed['task_stamp'][0]+=1
        self.assertFalse(incumbent.same_branch(self.initial,changed))
        changed=copy.deepcopy(self.initial);changed['modes'][1]=-1
        self.assertFalse(incumbent.same_branch(self.initial,changed))

    def test_truncated_mode_vector_is_rejected(self):
        changed=copy.deepcopy(self.initial);changed['modes'].pop()
        self.assertEqual(incumbent.validate(self.initial,changed)['reason'],'inconsistent_shape')


if __name__=='__main__':unittest.main()
