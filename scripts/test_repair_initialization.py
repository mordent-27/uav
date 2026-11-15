"""Physical invariants and a genuinely unsupported fixed-anchor branch."""
import copy
import json
from pathlib import Path
import unittest

import repair_initialization as repair

ROOT=Path(__file__).resolve().parents[1]


class RepairTests(unittest.TestCase):
    def fixture(self,case):
        return json.loads((ROOT/'experiments/2026-11-15-r2e-position-init/initializations'/case/'input.json').read_text())

    def test_feasible_input_is_preserved_without_mutation(self):
        data=self.fixture('tau1-seed3');before=copy.deepcopy(data)
        output,report=repair.repair(data)
        self.assertEqual(report['action'],'keep_original')
        self.assertEqual(output,before)
        self.assertEqual(data,before)

    def test_overrange_flight_gets_physical_witness_without_branch_change(self):
        data=self.fixture('tau7-seed3');before=copy.deepcopy(data)
        output,report=repair.repair(data)
        self.assertTrue(report['accepted'])
        self.assertTrue(repair.audit(output)['accepted'])
        self.assertEqual(data,before)
        for key in ['modes','task_stamp','instance','phys']:
            self.assertEqual(output[key],data[key])
        self.assertGreater(min(output['solution']['e']),0)
        self.assertEqual(len(output['solution']['r']),len(data['solution']['r']))

    def test_fixed_task_endpoints_cannot_be_moved_to_hide_overrange_flight(self):
        data=self.fixture('tau7-seed3')
        # Arrival is already task 4; freeze the departure as one additional task.
        data['instance']['tasks'].append(list(data['solution']['r'][20]))
        data['task_stamp'].append(20)
        before=copy.deepcopy(data)
        output,report=repair.repair(data)
        self.assertIsNone(output)
        self.assertEqual(report['reason'],'overlong_flight_remains')
        self.assertTrue(report['fixed_endpoints_over_full_range'])
        self.assertFalse(report['unrestricted_infeasibility_proven'])
        self.assertEqual(data,before)


if __name__=='__main__':unittest.main()
