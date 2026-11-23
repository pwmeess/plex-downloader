"""Version order used by the update check: 1.4.0 < 1.5.0-beta2 < 1.5.0-beta3 < 1.5.0."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import _ver_key  # noqa: E402


class TestVerKey(unittest.TestCase):
    def test_order(self):
        seq = ["1.3.1", "1.4.0", "1.5.0-beta0", "1.5.0-beta2", "1.5.0-beta3", "1.5.0", "1.5.1-beta1", "1.10.0"]
        self.assertEqual(sorted(seq, key=_ver_key), seq)

    def test_garbage(self):
        self.assertEqual(_ver_key(""), (0, 0, 0, 0, 0))
        self.assertEqual(_ver_key("1.5.0-beta"), (1, 5, 0, 0, 0))


if __name__ == "__main__":
    unittest.main()
