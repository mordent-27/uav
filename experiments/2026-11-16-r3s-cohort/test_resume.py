"""No optimizer: ensure failed/partial inputs cannot be silently retried or dropped."""
import json
from pathlib import Path
import tempfile
import unittest
import driver


class ResumeTests(unittest.TestCase):
    def test_failure_is_terminal_and_order_is_frozen(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);names=['a','b','c']
            p=root/'runs/a/result.json';p.parent.mkdir(parents=True)
            p.write_text(json.dumps(dict(case='a',error='solver wrapper exception')))
            states=driver.case_states(root,names)
            self.assertEqual(states['a']['state'],'software_error')
            self.assertEqual(driver.choose_batch(names,states),(0,['b','c']))

    def test_partial_stops_other_launches_without_overwriting(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'inputs/a').mkdir(parents=True)
            states=driver.case_states(root,['a','b'])
            with self.assertRaises(RuntimeError):driver.choose_batch(['a','b'],states)
            self.assertFalse((root/'runs/a/result.json').exists())

    def test_recorded_interruption_and_corrupt_result_stay_in_denominator(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'interruptions').mkdir()
            (root/'interruptions/a.json').write_text(json.dumps(dict(confirmed_no_live_processes=True)))
            p=root/'runs/b/result.json';p.parent.mkdir(parents=True);p.write_text('{broken')
            names=['a','b','c'];states=driver.case_states(root,names)
            self.assertEqual([states[n]['state'] for n in names],['interrupted_recorded','unreadable_result','pending'])
            self.assertEqual(driver.choose_batch(names,states),(0,['c']))
            self.assertEqual(p.read_text(),'{broken')


class CarryTests(unittest.TestCase):
    def test_carried_results_are_kept_and_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'new';old=Path(tmp)/'old';root.mkdir()
            p=old/'runs/a/result.json';p.parent.mkdir(parents=True);p.write_text(json.dumps(dict(case='a',error=None)))
            states=driver.case_states(root,['a','b'],old)
            self.assertEqual(states['a']['state'],'finished');self.assertEqual(states['a']['origin'],'old')
            self.assertEqual(states['b']['state'],'pending');self.assertEqual(driver.choose_batch(['a','b'],states),(0,['b']))

    def test_own_partial_output_is_not_masked_by_carry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'new';old=Path(tmp)/'old';(root/'inputs/a').mkdir(parents=True)
            p=old/'runs/a/result.json';p.parent.mkdir(parents=True);p.write_text(json.dumps(dict(case='a',error=None)))
            self.assertEqual(driver.case_states(root,['a'],old)['a']['state'],'partial_unresolved')


if __name__=='__main__':unittest.main()
