"""No solver: the per-file audit separates strict 1e-10 failures from metrics disagreements."""
import unittest
import audit_outputs as a


class AuditTests(unittest.TestCase):
    def test_strict_failure_keeps_printed_metrics(self):
        out='/x/a.json objective 1.400147428726 original_violation 1.660e-9\n\nthread main panicked\nassertion failed: m.viol < 1e-10\n'
        r=a.classify('/x/a.json',101,out)
        self.assertTrue(r['metrics_agree']);self.assertFalse(r['strict_passed']);self.assertEqual(r['failure'],'assertion failed: m.viol < 1e-10')
        self.assertEqual(r['printed']['original_violation'],1.66e-9)

    def test_metrics_disagreement_prints_nothing(self):
        r=a.classify('/x/b.json',101,'assertion failed: (m.viol - 1e-3).abs() < 1e-9\n')
        self.assertFalse(r['metrics_agree']);self.assertIsNone(r['printed'])

    def test_pass(self):
        r=a.classify('/x/c.json',0,'/x/c.json objective 1.0 original_violation 0.000e0\n')
        self.assertTrue(r['metrics_agree'] and r['strict_passed']);self.assertIsNone(r['failure'])


if __name__=='__main__':unittest.main()
