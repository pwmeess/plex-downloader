import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import movieinfo  # noqa: E402


class SplitTitleTests(unittest.TestCase):
    def test_split(self):
        self.assertEqual(movieinfo.split_title("Milczenie owiec (1991)"), ("Milczenie owiec", 1991))
        self.assertEqual(movieinfo.split_title("Blade Runner 2049 (2017)"), ("Blade Runner 2049", 2017))
        self.assertEqual(movieinfo.split_title("Breaking Bad"), ("Breaking Bad", None))
        self.assertEqual(movieinfo.split_title("  1917  "), ("1917", None))


if __name__ == "__main__":
    unittest.main()
