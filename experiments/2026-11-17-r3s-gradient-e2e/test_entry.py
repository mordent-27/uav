import ast
from pathlib import Path
import unittest

BASE=Path(__file__).resolve().parent


class EntryTests(unittest.TestCase):
    def test_patch_is_only_in_fast_g_branch(self):
        tree=ast.parse((BASE/'g_case_stall.py').read_text())
        patches=[n for n in ast.walk(tree) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Attribute) and t.attr=='hessian_of_al' for t in n.targets)]
        branches=[n for n in ast.walk(tree) if isinstance(n,ast.If) and ast.unparse(n.test)=="mode == 'fast'"]
        self.assertEqual(len(patches),1);self.assertEqual(len(branches),1)
        self.assertIn(patches[0],list(ast.walk(branches[0])))

    def test_runner_uses_original_entry_without_budget_patch(self):
        text=(BASE/'run.py').read_text()
        self.assertIn('module.STALL_CODE=BASE',text)
        self.assertIn('module.solve_case(case,{},BASE/mode)',text)
        self.assertNotIn('h.outer_cap',text);self.assertNotIn('h.tolerance',text)


if __name__=='__main__':unittest.main()
