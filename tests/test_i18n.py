"""Every user-visible English string in the code must have a Polish translation,
and the Polish catalog must not keep strings that are no longer used."""
import glob
import json
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATTERNS = [r'\b_\(\s*"((?:[^"\\]|\\.)*)"', r"\b_\(\s*'((?:[^'\\]|\\.)*)'", r'\bt\(\s*"((?:[^"\\]|\\.)*)"',
            r'\bnote="((?:[^"\\]|\\.)*)"']
# strings used indirectly (variables, config notes, BETA-only templates)
INDIRECT = {
    "Movies", "TV Shows", "Kids", "Directed by", "Created by", "First run", "Settings saved", "Settings changed",
    "Configuration migrated", "Theme changed", "Language changed",
}
BETA_ONLY = re.compile(r"VPN|Tailscale|soon|QR|Home network|Panel port|Panel available|Provider|setup-vpn|step-by-step", re.I)


def used_strings():
    out = set()
    files = glob.glob(os.path.join(ROOT, "*.py")) + glob.glob(os.path.join(ROOT, "templates", "*.html")) + \
        glob.glob(os.path.join(ROOT, "static", "*.js"))
    for f in files:
        s = open(f, encoding="utf-8").read()
        for p in PATTERNS:
            for m in re.finditer(p, s):
                txt = m.group(1)
                try:
                    txt = json.loads('"' + txt.replace("\\'", "'") + '"')
                except ValueError:
                    pass
                if txt:
                    out.add(txt)
    return out


class TestI18n(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(ROOT, "locales", "pl.json"), encoding="utf-8") as f:
            self.pl = json.load(f)
        self.used = used_strings()

    def test_all_strings_translated(self):
        missing = sorted(s for s in self.used | INDIRECT if s not in self.pl)
        self.assertEqual(missing, [], "Missing Polish translations")

    def test_no_unused_translations(self):
        unused = sorted(k for k in self.pl if k != "_meta" and k not in self.used and k not in INDIRECT
                        and not BETA_ONLY.search(k))
        self.assertEqual(unused, [], "Unused strings in pl.json")

    def test_placeholders_match(self):
        ph = re.compile(r"\{\w+\}|%[-.\d]*[sdrf]")
        bad = [k for k, v in self.pl.items() if k != "_meta" and sorted(ph.findall(k)) != sorted(ph.findall(v))]
        self.assertEqual(bad, [], "Placeholders differ between English and Polish")


if __name__ == "__main__":
    unittest.main()
