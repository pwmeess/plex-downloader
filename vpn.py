"""Remote access over VPN – Tailscale status and login for the Settings → VPN tab and the header badge.

Only the `tailscale` command line tool is used (no root needed to read the status). Logging in from
the panel works when the app's system user is the Tailscale "operator" (fix.sh sets this up);
otherwise the panel shows the command to run over SSH. Login itself always happens on the
Tailscale website – the panel never sees or stores those credentials.
"""
import ipaddress
import json
import re
import shutil
import subprocess
import threading
import time

import qrcodegen

_lock = threading.Lock()
_cache = {"t": 0.0, "data": None}
_login = {"proc": None, "url": "", "error": "", "denied": False, "t": 0.0}
URL_RE = re.compile(r"https://login\.tailscale\.com/\S+")
DENIED_RE = re.compile(r"access denied|must be root|permission denied|operator", re.I)
TS_NETS = (ipaddress.ip_network("100.64.0.0/10"), ipaddress.ip_network("fd7a:115c:a1e0::/48"))


def installed():
    return bool(shutil.which("tailscale"))


def _cli(*args, timeout=15):
    return subprocess.run(["tailscale"] + list(args), capture_output=True, text=True, timeout=timeout)


def via_vpn(addr):
    """True when the browser reaches the panel through the Tailscale network."""
    try:
        ip = ipaddress.ip_address((addr or "").split("%")[0])
    except ValueError:
        return False
    if getattr(ip, "ipv4_mapped", None):
        ip = ip.ipv4_mapped
    return any(ip in n for n in TS_NETS)


def _parse(raw):
    """The useful part of `tailscale status --json`."""
    self_ = raw.get("Self") or {}
    ips = raw.get("TailscaleIPs") or self_.get("TailscaleIPs") or []
    users = raw.get("User") or {}
    me = users.get(str(self_.get("UserID"))) or {}
    tailnet = raw.get("CurrentTailnet") or {}
    peers = []
    for p in (raw.get("Peer") or {}).values():
        pips = p.get("TailscaleIPs") or []
        peers.append({
            "name": (p.get("DNSName") or "").split(".")[0] or p.get("HostName") or "?",
            "os": p.get("OS") or "",
            "online": bool(p.get("Online")),
            "ip": next((x for x in pips if ":" not in x), pips[0] if pips else ""),
        })
    peers.sort(key=lambda p: (not p["online"], p["name"].lower()))
    return {
        "state": raw.get("BackendState") or "NoState",
        "version": (raw.get("Version") or "").split("-")[0],
        "ip": next((x for x in ips if ":" not in x), ""),
        "ip6": next((x for x in ips if ":" in x), ""),
        # the name given in the Tailscale console (e.g. raspi400), not the system hostname (raspberrypi)
        "hostname": (self_.get("DNSName") or "").split(".")[0] or self_.get("HostName") or "",
        "dns_name": (self_.get("DNSName") or "").rstrip("."),
        "magic_dns": bool(tailnet.get("MagicDNSEnabled", bool(raw.get("MagicDNSSuffix")))),
        "tailnet": tailnet.get("Name") or "",
        "account": me.get("LoginName") or "",
        "auth_url": raw.get("AuthURL") or "",
        "health": [h for h in (raw.get("Health") or []) if h][:5],
        "peers": peers,
    }


def status(max_age=10.0):
    """Tailscale status; cached so the header (polled every 15 s) does not start the CLI each time."""
    with _lock:
        if _cache["data"] is not None and time.time() - _cache["t"] < max_age:
            return dict(_cache["data"])
    data = _status()
    proc = _login["proc"]
    data["login_running"] = bool(proc and proc.poll() is None)
    if data["state"] == "Running":
        _login.update(url="", error="", denied=False)
    data["login_url"] = data.get("auth_url") or _login["url"]
    data["login_error"] = _login["error"]
    data["need_operator"] = _login["denied"]
    with _lock:
        _cache.update(t=time.time(), data=data)
    return dict(data)


def _status():
    base = {"provider": "tailscale", "installed": installed(), "state": "absent", "peers": [], "health": []}
    if not base["installed"]:
        return base
    try:
        p = _cli("status", "--json")
    except (OSError, subprocess.SubprocessError):
        return dict(base, state="daemon_down")
    try:
        raw = json.loads(p.stdout or "{}")
    except ValueError:
        raw = {}
    if not raw:
        return dict(base, state="daemon_down", detail=(p.stderr or "").strip()[:300])
    base.update(_parse(raw))
    return base


def _reader(proc):
    """Reads `tailscale up` output: the login link, or why it was refused."""
    other = []
    for line in proc.stdout:
        m = URL_RE.search(line)
        if m:
            _login["url"] = m.group(0)
        elif DENIED_RE.search(line):
            _login["denied"] = True
            _login["error"] = line.strip()[:300]
        elif line.strip():
            other.append(line.strip())
    code = proc.wait()
    if code and not _login["error"] and not _login["url"]:
        _login["error"] = (" ".join(other) or "tailscale up: exit %d" % code)[:300]
    with _lock:
        _cache["t"] = 0


def login():
    """Starts `tailscale up` in the background. It prints a login link and then waits (up to
    15 minutes) until someone logs in on the Tailscale website."""
    if not installed():
        return status(0)
    proc = _login["proc"]
    if not (proc and proc.poll() is None):
        _login.update(url="", error="", denied=False, t=time.time())
        try:
            proc = subprocess.Popen(["tailscale", "up", "--timeout=15m"], stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, text=True,
                                    start_new_session=True)
        except OSError as e:
            _login["error"] = str(e)
            return status(0)
        _login["proc"] = proc
        threading.Thread(target=_reader, args=(proc,), daemon=True).start()
    # the link usually appears within a few seconds
    deadline = time.time() + 12
    while time.time() < deadline and not (_login["url"] or _login["denied"]) and proc.poll() is None:
        time.sleep(0.3)
    if proc.poll() is not None:
        time.sleep(0.5)   # let the reader finish
    return status(0)


def qr_svg(text, border=3):
    """QR code as SVG (dark modules on white – phones read it in both themes)."""
    qr = qrcodegen.QrCode.encode_text(text, qrcodegen.QrCode.Ecc.MEDIUM)
    n = qr.get_size()
    parts = []
    for y in range(n):
        for x in range(n):
            if qr.get_module(x, y):
                parts.append("M%d,%dh1v1h-1z" % (x + border, y + border))
    size = n + 2 * border
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {s} {s}" shape-rendering="crispEdges">'
            '<rect width="100%" height="100%" fill="#fff"/><path d="{d}" fill="#000"/></svg>'
            ).format(s=size, d="".join(parts))
