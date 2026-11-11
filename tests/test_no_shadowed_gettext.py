"""A function that calls _() (translation) must not assign to "_" – the call would then crash
(1.4.0-beta2: moving TV shows without season folders failed with error 500)."""
import ast
import glob
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestNoShadowedGettext(unittest.TestCase):
    def test_no_assignment_to_underscore(self):
        bad = []
        for f in glob.glob(os.path.join(ROOT, "*.py")):
            tree = ast.parse(open(f, encoding="utf-8").read())
            for fn in ast.walk(tree):
                if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                stores = [n for n in ast.walk(fn) if isinstance(n, ast.Name) and n.id == "_" and isinstance(n.ctx, ast.Store)]
                calls = [n for n in ast.walk(fn) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "_"]
                if stores and calls:
                    bad.append("%s:%d %s" % (os.path.basename(f), stores[0].lineno, fn.name))
        self.assertEqual(bad, [])


if __name__ == "__main__":
    unittest.main()
