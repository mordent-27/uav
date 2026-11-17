import unittest
from run import recoveries


class RecoveryTests(unittest.TestCase):
    def test_violation_can_recover(self):self.assertEqual(recoveries([False,True,True,False]),[3])
    def test_nonmonotone_is_preserved(self):self.assertEqual(recoveries([True,False,True,False]),[1,3])
    def test_absence_is_not_recovery(self):self.assertEqual(recoveries([False,False]),[])


if __name__=='__main__':unittest.main()
