import unittest
from profile_step import validate_times


class TimingTests(unittest.TestCase):
    def test_disjoint_accounting(self):
        self.assertEqual(validate_times(100,dict(hessian=60,eigh=20,search=10)),10)

    def test_double_count_rejected(self):
        with self.assertRaises(AssertionError):validate_times(100,dict(hessian=90,nested_part=20))

    def test_negative_rejected(self):
        with self.assertRaises(AssertionError):validate_times(100,dict(hessian=-1))


if __name__=='__main__':unittest.main()
