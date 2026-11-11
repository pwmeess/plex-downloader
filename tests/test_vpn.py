"""VPN tab: Tailscale status parsing, login flow and QR codes (with a fake `tailscale` command)."""
import json
import os
import stat
import sys
import tempfile
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import vpn  # noqa: E402

RUNNING = {
    "Version": "1.76.6-t1234-gabc", "BackendState": "Running", "AuthURL": "",
    "TailscaleIPs": ["100.101.102.103", "fd7a:115c:a1e0::1"],
    "Self": {"HostName": "plexpi", "DNSName": "plexpi.tail1234.ts.net.", "UserID": 7, "Online": True},
    "MagicDNSSuffix": "tail1234.ts.net",
    "CurrentTailnet": {"Name": "user@example.com", "MagicDNSSuffix": "tail1234.ts.net", "MagicDNSEnabled": True},
    "User": {"7": {"LoginName": "user@example.com", "DisplayName": "User"}},
    "Peer": {
        "a": {"HostName": "iPhone", "DNSName": "iphone.tail1234.ts.net.", "OS": "iOS", "Online": True,
              "TailscaleIPs": ["100.80.1.2", "fd7a:115c:a1e0::2"]},
        "b": {"HostName": "laptop", "DNSName": "laptop.tail1234.ts.net.", "OS": "macOS", "Online": False,
              "TailscaleIPs": ["100.80.1.3"]},
    },
    "Health": [],
}

FAKE = """#!/bin/sh
if [ "$1" = "status" ]; then cat "$TS_FAKE_JSON"; exit 0; fi
if [ "$1" = "serve" ]; then
  case "$2" in
    status) cat "$TS_FAKE_SERVE" 2>/dev/null || echo '{}'; exit 0 ;;
    --bg)
      if [ -n "$TS_FAKE_NOHTTPS" ]; then
        echo "Serve is not enabled on your tailnet."; echo "To enable, visit:"; echo
        echo "         https://login.tailscale.com/f/serve?node=n123"; sleep 30; exit 1
      fi
      echo '{"TCP":{"443":{"HTTPS":true}},"Web":{"plexpi.tail1234.ts.net:443":{"Handlers":{"/":{"Proxy":"http://127.0.0.1:8800"}}}}}' > "$TS_FAKE_SERVE"
      echo "Available within your tailnet:"; exit 0 ;;
    --https=443) echo '{}' > "$TS_FAKE_SERVE"; exit 0 ;;
  esac
fi
if [ "$1" = "up" ]; then
  if [ -n "$TS_FAKE_DENY" ]; then echo "Access denied: prefs write access denied"; exit 1; fi
  echo ""; echo "To authenticate, visit:"; echo ""; echo "	https://login.tailscale.com/a/abc123"; sleep 30; exit 0
fi
exit 1
"""


class TestParse(unittest.TestCase):
    def test_running(self):
        v = vpn._parse(RUNNING)
        self.assertEqual(v["state"], "Running")
        self.assertEqual(v["ip"], "100.101.102.103")
        self.assertEqual(v["dns_name"], "plexpi.tail1234.ts.net")
        self.assertEqual(v["version"], "1.76.6")
        self.assertEqual(v["account"], "user@example.com")
        self.assertTrue(v["magic_dns"])
        self.assertEqual([p["name"] for p in v["peers"]], ["iphone", "laptop"])   # online first
        self.assertEqual(v["peers"][0]["ip"], "100.80.1.2")
        self.assertEqual(v["latest"], "")

    def test_outdated(self):
        v = vpn._parse(dict(RUNNING, ClientVersion={"RunningLatest": False, "LatestVersion": "1.80.2"}))
        self.assertEqual(v["latest"], "1.80.2")
        self.assertTrue(vpn._outdated(v["version"], v["latest"], v["running_latest"]))
        self.assertFalse(vpn._outdated("1.104.6", "1.104.6", None))
        self.assertFalse(vpn._outdated("1.104.10", "1.104.9", None))
        self.assertTrue(vpn._outdated("1.104.6", "", False))
        self.assertIsNone(vpn._outdated("1.104.6", "", None))

    def test_needs_login(self):
        v = vpn._parse({"BackendState": "NeedsLogin", "AuthURL": "https://login.tailscale.com/a/x"})
        self.assertEqual(v["state"], "NeedsLogin")
        self.assertEqual(v["ip"], "")
        self.assertEqual(v["auth_url"], "https://login.tailscale.com/a/x")

    def test_via_vpn(self):
        self.assertTrue(vpn.via_vpn("100.80.1.2"))
        self.assertTrue(vpn.via_vpn("::ffff:100.80.1.2"))
        self.assertTrue(vpn.via_vpn("fd7a:115c:a1e0::2"))
        self.assertFalse(vpn.via_vpn("192.168.1.20"))
        self.assertFalse(vpn.via_vpn(""))
        self.assertFalse(vpn.via_vpn("garbage"))

    def test_qr(self):
        svg = vpn.qr_svg("http://100.101.102.103:8800")
        self.assertTrue(svg.startswith("<svg"))
        self.assertIn('fill="#000"', svg)


class TestCli(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = self.tmp.name
        exe = os.path.join(d, "tailscale")
        with open(exe, "w") as f:
            f.write(FAKE)
        os.chmod(exe, os.stat(exe).st_mode | stat.S_IEXEC)
        self.json = os.path.join(d, "status.json")
        self.env = dict(os.environ)
        os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")
        os.environ["TS_FAKE_JSON"] = self.json
        os.environ["TS_FAKE_SERVE"] = os.path.join(d, "serve.json")
        for k in ("TS_FAKE_DENY", "TS_FAKE_NOHTTPS"):
            os.environ.pop(k, None)
        vpn._cache.update(t=0, data=None)
        vpn._login.update(proc=None, url="", error="", denied=False)

    def tearDown(self):
        p = vpn._login.get("proc")
        if p and p.poll() is None:
            p.kill()
            p.wait()
        os.environ.clear()
        os.environ.update(self.env)
        self.tmp.cleanup()

    def write(self, data):
        with open(self.json, "w") as f:
            json.dump(data, f)

    def test_absent(self):
        os.environ["PATH"] = "/nonexistent"
        self.assertEqual(vpn.status(0)["state"], "absent")

    def test_daemon_down(self):
        with open(self.json, "w") as f:
            f.write("")
        self.assertEqual(vpn.status(0)["state"], "daemon_down")

    def test_running_and_cache(self):
        self.write(RUNNING)
        self.assertEqual(vpn.status(0)["ip"], "100.101.102.103")
        self.write({"BackendState": "Stopped"})
        self.assertEqual(vpn.status(30)["state"], "Running")      # cached
        self.assertEqual(vpn.status(0)["state"], "Stopped")

    def test_login_link(self):
        self.write({"BackendState": "NeedsLogin"})
        t0 = time.time()
        v = vpn.login()
        self.assertLess(time.time() - t0, 10)
        self.assertEqual(v["login_url"], "https://login.tailscale.com/a/abc123")
        self.assertTrue(v["login_running"])
        self.assertFalse(v["need_operator"])

    def test_login_denied(self):
        os.environ["TS_FAKE_DENY"] = "1"
        self.write({"BackendState": "NeedsLogin"})
        v = vpn.login()
        self.assertTrue(v["need_operator"])
        self.assertEqual(v["login_url"], "")

    def test_https_on_off(self):
        self.assertFalse(vpn.https_status(8800)["on"])
        r = vpn.set_https(True, 8800)
        self.assertTrue(r["ok"])
        self.assertTrue(r["on"])
        self.assertEqual(r["url"], "https://plexpi.tail1234.ts.net")
        self.assertFalse(vpn.https_status(9999)["on"])          # another port = something else
        self.assertTrue(vpn.https_status(9999)["other"])
        self.assertFalse(r["public"])
        with open(os.environ["TS_FAKE_SERVE"]) as f:
            cfg = json.load(f)
        cfg["AllowFunnel"] = {"plexpi.tail1234.ts.net:443": True}
        with open(os.environ["TS_FAKE_SERVE"], "w") as f:
            json.dump(cfg, f)
        self.assertTrue(vpn.https_status(8800)["public"])
        r = vpn.set_https(False, 8800)
        self.assertTrue(r["ok"])
        self.assertFalse(r["on"])

    def test_https_needs_enabling(self):
        os.environ["TS_FAKE_NOHTTPS"] = "1"
        t0 = time.time()
        r = vpn.set_https(True, 8800)
        self.assertLess(time.time() - t0, 10)
        self.assertFalse(r["ok"])
        self.assertEqual(r["enable_url"], "https://login.tailscale.com/f/serve?node=n123")

    def test_proxy_detection(self):
        self.assertTrue(vpn.via_tailscale_proxy("127.0.0.1", {"Host": "plexpi.tail1234.ts.net"}))
        self.assertTrue(vpn.via_tailscale_proxy("127.0.0.1", {"Host": "127.0.0.1:8800", "Tailscale-User-Login": "u@x"}))
        self.assertFalse(vpn.via_tailscale_proxy("127.0.0.1", {"Host": "127.0.0.1:8800"}))
        self.assertFalse(vpn.via_tailscale_proxy("192.168.1.20", {"Host": "x.ts.net"}))


IP_FAKE = r"""#!/bin/sh
# imitates `ip` on a Raspberry Pi with one WireGuard connection (wg0) – a synthetic test, no real WireGuard
case "$*" in
  "-o link show type wireguard") printf '5: wg0: <POINTOPOINT,NOARP,UP,LOWER_UP> mtu 1420 qdisc noqueue state UNKNOWN mode DEFAULT group default qlen 1000\\    link/none \n' ;;
  "-o addr show dev wg0") printf '5: wg0    inet 10.8.0.1/24 scope global wg0\\       valid_lft forever preferred_lft forever\n5: wg0    inet6 fd00:8::1/64 scope global\n' ;;
esac
"""
SYSTEMCTL_FAKE = "#!/bin/sh\n[ \"$3\" = \"wg-quick@wg0\" ] && exit 0\nexit 3\n"


class TestWireGuard(unittest.TestCase):
    """Synthetic: fake `ip`, `systemctl` and `wg` commands imitate a Raspberry Pi with WireGuard."""
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.environ.get("PATH", "")

    def tearDown(self):
        os.environ["PATH"] = self.path
        self.tmp.cleanup()

    def fake(self, name, body):
        exe = os.path.join(self.tmp.name, name)
        with open(exe, "w") as f:
            f.write(body)
        os.chmod(exe, 0o755)

    def test_interface(self):
        self.fake("ip", IP_FAKE)
        self.fake("systemctl", SYSTEMCTL_FAKE)
        self.fake("wg", "#!/bin/sh\nexit 0\n")
        os.environ["PATH"] = self.tmp.name + os.pathsep + self.path
        w = vpn.wireguard_status()
        self.assertTrue(w["installed"])
        self.assertEqual(w["interfaces"], [{"name": "wg0", "addresses": ["10.8.0.1/24", "fd00:8::1/64"], "service": True}])

    def test_installed_without_connection(self):
        self.fake("ip", "#!/bin/sh\nexit 0\n")
        self.fake("wg", "#!/bin/sh\nexit 0\n")
        os.environ["PATH"] = self.tmp.name + os.pathsep + self.path
        self.assertEqual(vpn.wireguard_status(), {"installed": True, "interfaces": []})

    def test_not_installed(self):
        self.fake("ip", "#!/bin/sh\nexit 0\n")
        os.environ["PATH"] = self.tmp.name
        self.assertEqual(vpn.wireguard_status(), {"installed": False, "interfaces": []})


if __name__ == "__main__":
    unittest.main()
