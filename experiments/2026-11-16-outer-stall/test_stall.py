import unittest
import stall


def rows(viol,rho=1e8,passed_at=None):
    return [dict(outer=i+1,rho=rho if not callable(rho) else rho(i),violation=v,seconds=float(i+1),stage_pass=(passed_at==i+1)) for i,v in enumerate(viol)]


class TestStall(unittest.TestCase):
    def test_constant_violation_triggers_at_2K(self):
        self.assertEqual(stall.first_trigger(rows([1e-3]*100),20,.1),40)

    def test_fast_decrease_does_not_trigger(self):
        self.assertIsNone(stall.first_trigger(rows([1e-2*.9**i for i in range(100)]),20,.1))

    def test_below_tolerance_does_not_trigger(self):
        self.assertIsNone(stall.first_trigger(rows([5e-7]*100),20,.1))

    def test_rho_below_cap_blocks(self):
        r=rows([1e-3]*100,rho=lambda i:1e7 if i<30 else 1e8)
        self.assertEqual(stall.first_trigger(r,20,.1),70)  # rows 31..70 are the first 2K rows at the cap

    def test_false_stop_and_saved_time(self):
        r=rows([1e-3]*60+[1e-7],passed_at=61);c=stall.classify(r,True,20,.1)
        self.assertEqual(c['kind'],'false_stop');self.assertEqual(stall.verdict([c]),'unsafe')
        c=stall.classify(rows([1e-3]*100),False,20,.1)
        self.assertEqual(c['kind'],'stopped_failure');self.assertEqual(c['saved_seconds'],60.)
        self.assertEqual(stall.verdict([c]),'safe_saves_time')
        self.assertEqual(stall.verdict([stall.classify(rows([1e-2*.5**i for i in range(30)]),False,20,.1)]),'safe_no_effect')


if __name__=='__main__':unittest.main()
