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
        # newest version, as told by the Tailscale servers (only when logged in)
        "latest": ((raw.get("ClientVersion") or {}).get("LatestVersion") or "").split("-")[0],
        "running_latest": (raw.get("ClientVersion") or {}).get("RunningLatest"),
        "urgent": bool((raw.get("ClientVersion") or {}).get("UrgentSecurityUpdate")),
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
    if not base.get("latest"):
        base["latest"] = upstream_version()
    base["outdated"] = _outdated(base.get("version"), base.get("latest"), base.get("running_latest"))
    return base


def _vt(v):
    return tuple(int(x) for x in re.findall(r"\d+", v or "")[:3])


def _outdated(cur, latest, running_latest):
    """True / False, or None when it is not known."""
    if cur and latest:
        return _vt(cur) < _vt(latest)
    if running_latest is not None:
        return not running_latest
    return None


_upstream = {"t": 0.0, "v": ""}


def upstream_version():
    """Newest Tailscale version from pkgs.tailscale.com (`tailscale version --upstream`), checked at most
    every 6 hours – used when the status has no ClientVersion (e.g. not logged in)."""
    if time.time() - _upstream["t"] < 6 * 3600:
        return _upstream["v"]
    _upstream["t"] = time.time()
    try:
        p = _cli("version", "--upstream", "--json", timeout=15)
        _upstream["v"] = (json.loads(p.stdout or "{}").get("upstream") or "").split("-")[0]
    except (OSError, subprocess.SubprocessError, ValueError):
        _upstream["v"] = ""
    return _upstream["v"]


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


# ---------------------------------------------------------------- HTTPS inside the VPN (tailscale serve)
# Tailscale issues a real certificate for <name>.<tailnet>.ts.net and proxies HTTPS (port 443) to the
# panel on this Raspberry Pi. Only devices in your Tailscale network can reach it (serve, not funnel).
ENABLE_RE = re.compile(r"https://login\.tailscale\.com/f/\S+")


def https_status(port):
    """{"on": bool, "url": "https://…", "other": bool} – other = serve is used for something else on 443."""
    out = {"on": False, "url": "", "other": False, "public": False}
    if not installed():
        return out
    try:
        p = _cli("serve", "status", "--json", timeout=10)
        cfg = json.loads(p.stdout or "{}") or {}
    except (OSError, subprocess.SubprocessError, ValueError):
        return out
    for host, web in (cfg.get("Web") or {}).items():
        if not host.endswith(":443"):
            continue
        h = ((web or {}).get("Handlers") or {}).get("/") or {}
        target = h.get("Proxy") or ""
        if re.search(r"(127\.0\.0\.1|localhost):%d/?$" % int(port), target):
            # Funnel would publish the panel on the internet – the panel never turns it on, but warns
            out.update(on=True, url="https://" + host[:-4], public=bool((cfg.get("AllowFunnel") or {}).get(host)))
        else:
            out["other"] = True
    return out


def _watch(args, timeout=20):
    """Runs a tailscale command that may stop to wait for a confirmation link.
    Returns (exit code or None if still waiting, output, link)."""
    try:
        proc = subprocess.Popen(["tailscale"] + args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                stdin=subprocess.DEVNULL, text=True, start_new_session=True)
    except OSError as e:
        return 1, str(e), ""
    lines, link = [], [""]

    def read():
        for line in proc.stdout:
            lines.append(line.rstrip())
            m = ENABLE_RE.search(line)
            if m:
                link[0] = m.group(0)
    t = threading.Thread(target=read, daemon=True)
    t.start()
    deadline = time.time() + timeout
    while time.time() < deadline and proc.poll() is None and not link[0]:
        time.sleep(0.2)
    code = proc.poll()
    if code is None:          # waiting for HTTPS to be enabled in the console – ask the user, try again later
        time.sleep(0.5)
        proc.kill()
        proc.wait()
    t.join(1)
    return code, "\n".join(x for x in lines if x.strip())[:600], link[0]


def set_https(on, port):
    """Switches HTTPS in the VPN on or off. Returns {"ok", "enable_url", "denied", "error"} plus the status."""
    res = {"ok": False, "enable_url": "", "denied": False, "error": ""}
    if on:
        code, out, link = _watch(["serve", "--bg", "--https=443", "http://127.0.0.1:%d" % int(port)])
    else:
        code, out, link = _watch(["serve", "--https=443", "off"], timeout=15)
    if link:
        res["enable_url"] = link
    elif code == 0:
        res["ok"] = True
    elif DENIED_RE.search(out):
        res["denied"] = True
    else:
        res["error"] = out or "tailscale serve: exit %s" % code
    res.update(https_status(port))
    with _lock:
        _cache["t"] = 0
    return res


def via_tailscale_proxy(remote_addr, headers):
    """A request that came through `tailscale serve` (HTTPS in the VPN): it arrives from localhost and
    Tailscale adds the user's login and the .ts.net host."""
    if remote_addr not in ("127.0.0.1", "::1", "::ffff:127.0.0.1"):
        return False
    host = (headers.get("X-Forwarded-Host") or headers.get("Host") or "").split(":")[0]
    return bool(headers.get("Tailscale-User-Login")) or host.endswith(".ts.net")


def logout():
    """Logs this Raspberry Pi out of Tailscale (e.g. to log in to another account)."""
    res = {"ok": False, "denied": False, "error": ""}
    try:
        p = _cli("logout", timeout=30)
    except (OSError, subprocess.SubprocessError) as e:
        res["error"] = str(e)
        return res
    out = ((p.stdout or "") + (p.stderr or "")).strip()
    if p.returncode == 0:
        res["ok"] = True
    elif DENIED_RE.search(out):
        res["denied"] = True
    else:
        res["error"] = out[:300] or "tailscale logout: exit %d" % p.returncode
    _login.update(url="", error="", denied=False)
    with _lock:
        _cache["t"] = 0
    return res


# ---------------------------------------------------------------- WireGuard (status only)
def wireguard_status():
    """WireGuard interfaces on this Raspberry Pi, read without root (`ip`); peers need `sudo wg show`."""
    out = {"installed": bool(shutil.which("wg") or shutil.which("wg-quick")), "interfaces": []}
    try:
        p = subprocess.run(["ip", "-o", "link", "show", "type", "wireguard"], capture_output=True, text=True, timeout=5)
        names = [ln.split(":")[1].strip().split("@")[0] for ln in p.stdout.splitlines() if ln.count(":") >= 2]
    except (OSError, subprocess.SubprocessError):
        names = []
    for n in names:
        addrs = []
        try:
            a = subprocess.run(["ip", "-o", "addr", "show", "dev", n], capture_output=True, text=True, timeout=5).stdout
            addrs = re.findall(r"inet6? (\S+)", a)
        except (OSError, subprocess.SubprocessError):
            pass
        up = False
        try:
            up = subprocess.run(["systemctl", "is-active", "--quiet", "wg-quick@%s" % n], timeout=5).returncode == 0
        except (OSError, subprocess.SubprocessError):
            pass
        out["interfaces"].append({"name": n, "addresses": addrs, "service": up})
    if names:
        out["installed"] = True
    return out
