"""Settings export / import (1.3.0-beta2): the file never carries secrets, imports are validated."""
import json
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import app as appmod  # noqa: E402
import config  # noqa: E402


H = {"X-PlexDL": "1"}


class _Stub:
    def __getattr__(self, name):
        return lambda *a, **k: None


class SettingsIOTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.saved = (config.CONFIG_PATH, config.BACKUP_DIR, config._config, appmod.manager, appmod.plexservers.monitor)
        config.CONFIG_PATH = os.path.join(cls.tmp, "config.json")
        config.BACKUP_DIR = os.path.join(cls.tmp, "backups")
        config._config = None
        config.load()
        appmod.app.secret_key = "test"
        appmod.manager = _Stub()
        appmod.plexservers.monitor = _Stub()

    @classmethod
    def tearDownClass(cls):
        (config.CONFIG_PATH, config.BACKUP_DIR, config._config, appmod.manager, appmod.plexservers.monitor) = cls.saved
        shutil.rmtree(cls.tmp, True)

    def setUp(self):
        config.update(password_hash="hash-secret", secret_key="sess-secret", aria2_secret="aria-secret",
                      tmdb_api_key="tmdb-secret-123", make_backup=False)
        self.c = appmod.app.test_client()
        with self.c.session_transaction() as s:
            s["user"] = config.get()["username"]

    def test_export_has_no_secrets(self):
        body = self.c.get("/api/settings/export").get_data(as_text=True)
        for secret in ("hash-secret", "sess-secret", "aria-secret", "tmdb-secret-123", "password", "username"):
            self.assertNotIn(secret, body)
        data = json.loads(body)
        self.assertEqual(data["_plexdl"]["app"], "plex-downloader")
        self.assertIn("categories", data)
        with_key = json.loads(self.c.get("/api/settings/export?tmdb=1").get_data(as_text=True))
        self.assertEqual(with_key["tmdb_api_key"], "tmdb-secret-123")

    def test_clean_rejects_foreign_and_bad_values(self):
        with self.assertRaises(ValueError):
            appmod._import_clean({"disks": []})
        with self.assertRaises(ValueError):
            appmod._import_clean({"_plexdl": {}, "disks": [{"label": "X", "mount": "../etc"}]})
        out = appmod._import_clean({"_plexdl": {}, "password_hash": "x", "username": "evil",
                                    "max_concurrent": 99, "theme": "neon", "language": "xx",
                                    "plex_servers": [{"host": "bad host;rm", "port": 1}, {"host": "192.168.1.10"}]})
        self.assertNotIn("password_hash", out)
        self.assertNotIn("username", out)
        self.assertNotIn("theme", out)
        self.assertNotIn("language", out)
        self.assertEqual(out["max_concurrent"], 10)
        self.assertEqual([s["host"] for s in out["plex_servers"]], ["192.168.1.10"])

    def test_preview_and_selected_import(self):
        before = config.get()
        data = json.loads(self.c.get("/api/settings/export").get_data(as_text=True))
        data["max_concurrent"] = 5
        data["theme"] = "light" if before.get("theme") != "light" else "dark"
        data["disks"] = [{"id": "sd", "label": "SD", "mount": "/", "paths": {"movies": "/home/nobody/Plex/Movies"}}]
        pv = self.c.post("/api/settings/import/preview", json={"data": data}, headers=H).get_json()
        self.assertEqual([c["key"] for c in pv["sections"]["downloads"]["changes"]], ["max_concurrent"])
        self.assertFalse(pv["sections"]["disks"]["disks"][0]["paths"][0]["exists"])
        r = self.c.post("/api/settings/import", json={"data": data, "sections": ["downloads"]}, headers=H).get_json()
        self.assertTrue(r["ok"])
        after = config.get()
        self.assertEqual(after["max_concurrent"], 5)
        self.assertEqual(after["theme"], before.get("theme"))      # interface not chosen
        self.assertEqual(after["disks"], before.get("disks"))      # disks not chosen
        self.assertEqual(after["password_hash"], "hash-secret")
        self.assertEqual(self.c.post("/api/settings/import", json={"data": data, "sections": []}, headers=H).status_code, 400)


if __name__ == "__main__":
    unittest.main()
