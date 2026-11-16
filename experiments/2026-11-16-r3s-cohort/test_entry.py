"""No optimizer: the R3s entry files are exactly the versions compared end to end in stall-e2e."""
from pathlib import Path
import unittest

HERE=Path(__file__).resolve().parent;E2E=HERE.parent/'2026-11-16-stall-e2e'


class EntryTests(unittest.TestCase):
    def test_stage_loop_and_g_case_are_the_tested_copies(self):
        for name in ['run_stall.py','g_case_stall.py']:self.assertEqual((HERE/name).read_bytes(),(E2E/name).read_bytes(),name)

    def test_solve_differs_from_tested_entry_only_in_docstring_and_default(self):
        new=(HERE/'solve.py').read_text().splitlines();old=(E2E/'entry.py').read_text().splitlines()
        self.assertEqual(len(new),len(old));diff=[(a,b) for a,b in zip(old,new) if a!=b]
        self.assertEqual(len(diff),2);self.assertIn('stall=True',diff[1][1]);self.assertIn('stall=False',diff[1][0])


if __name__=='__main__':unittest.main()
