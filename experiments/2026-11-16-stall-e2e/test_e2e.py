import importlib.util
from pathlib import Path
import unittest

HERE=Path(__file__).resolve().parent;EXP=HERE.parent
spec=importlib.util.spec_from_file_location('outer_stall_rule',EXP/'2026-11-16-outer-stall/stall.py');stall=importlib.util.module_from_spec(spec);spec.loader.exec_module(stall)
BLOCK="""                if stage == 13 and stall.first_trigger(records, STALL_K, STALL_DELTA, h.tolerance(stage), 1e8) == len(records):
                    stop = 'stalled'
                    h.write(folder/'stall.json', dict(trigger=len(records), K=STALL_K, delta=STALL_DELTA,
                        violation=records[-1]['violation'], seconds=records[-1]['seconds']))
                    break
"""


def loop(viol,rho=1e8):
    """The inserted check, run after each appended row as in run_stall.py."""
    records=[]
    for i,v in enumerate(viol):
        records.append(dict(rho=rho,violation=v,seconds=float(i)))
        if stall.first_trigger(records,20,.1,1e-6,1e8)==len(records):return 'stalled',len(records)
    return 'limit',len(records)


class TestE2E(unittest.TestCase):
    def test_run_stall_is_run_py_plus_the_rule(self):
        new=(HERE/'run_stall.py').read_text();old=(EXP/'2026-11-15-r2b-coarse/run.py').read_text()
        self.assertEqual(new.count(BLOCK),1)
        body=new.replace(BLOCK,'').split('STALL_K, STALL_DELTA = 20, 0.1\n',1)[1]
        self.assertEqual(body,old.split('newton = h.load("newton")  # the previous Newton file, unchanged\n',1)[1])

    def test_entry_differs_only_in_the_g_case_command(self):
        new=(HERE/'entry.py').read_text().splitlines();old=(EXP/'2026-11-16-r3a-cohort/solve.py').read_text().splitlines()
        extra=[l for l in new if l not in old];missing=[l for l in old if l not in new]
        self.assertEqual(len(extra),4);self.assertEqual(len(missing),3)
        self.assertTrue(any("g_case_stall.py" in l for l in extra))

    def test_g_case_stall_replaces_only_run(self):
        new=(HERE/'g_case_stall.py').read_text();old=(EXP/'2026-11-16-r2h-g-first/g_case.py').read_text()
        self.assertIn("h.load_from(HERE_STALL,'run_stall')",new);self.assertIn("h.load_from(h.R2A,'restore')",new);self.assertIn("h.load_from(h.R2B,'verify')",new)
        self.assertEqual(old.split('def main():',1)[1].replace("h.load_from(h.R2B,'run')","h.load_from(HERE_STALL,'run_stall')"),new.split('def main():',1)[1])

    def test_inserted_check_stops_at_first_trigger(self):
        self.assertEqual(loop([1e-3]*600),('stalled',40))
        self.assertEqual(loop([1e-2*.8**i for i in range(80)]+[5e-7]*20),('limit',100))
        self.assertEqual(loop([1e-3]*600,rho=1e7),('limit',600))


if __name__=='__main__':unittest.main()
