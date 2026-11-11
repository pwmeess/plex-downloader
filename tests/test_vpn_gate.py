"""Settings → VPN → "Home network only": requests through the VPN are refused (1.4.0-beta2)."""
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


class VpnGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.saved = (config.CONFIG_PATH, config.BACKUP_DIR, config._config)
        config.CONFIG_PATH = os.path.join(cls.tmp, "config.json")
        config.BACKUP_DIR = os.path.join(cls.tmp, "backups")
        config._config = None
        config.load()
        appmod.app.secret_key = "test"

    @classmethod
    def tearDownClass(cls):
        (config.CONFIG_PATH, config.BACKUP_DIR, config._config) = cls.saved
        shutil.rmtree(cls.tmp, True)

    def setUp(self):
        config.update(vpn_lan_only=False, make_backup=False)
        self.c = appmod.app.test_client()
        with self.c.session_transaction() as s:
            s["user"] = config.get()["username"]

    def get(self, ip, headers=None):
        return self.c.get("/login", environ_base={"REMOTE_ADDR": ip}, headers=headers or {})

    def test_default_allows_vpn(self):
        self.assertEqual(self.get("100.84.203.117").status_code, 200)

    def test_lan_only(self):
        r = self.c.post("/api/vpn/access", json={"lan_only": True}, headers=H, environ_base={"REMOTE_ADDR": "192.168.1.20"})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(config.get()["vpn_lan_only"])
        self.assertEqual(self.get("192.168.1.20").status_code, 200)
        self.assertEqual(self.get("100.84.203.117").status_code, 403)
        # HTTPS in the VPN arrives through tailscale serve from localhost
        self.assertEqual(self.get("127.0.0.1", {"Host": "raspi400.tail4d031a.ts.net"}).status_code, 403)
        self.assertEqual(self.get("127.0.0.1").status_code, 200)
        r = self.c.get("/api/state", environ_base={"REMOTE_ADDR": "100.84.203.117"})
        self.assertEqual(r.status_code, 403)
        self.assertIn("error", r.get_json())


if __name__ == "__main__":
    unittest.main()
