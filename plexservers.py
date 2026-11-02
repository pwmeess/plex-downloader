"""Wykrywanie i monitorowanie serwerów Plex w sieci lokalnej (tylko odczyt statusu)."""
import logging
import re
import socket
import threading
import time
import urllib.request
import xml.etree.ElementTree as ET

import config

log = logging.getLogger("plexdl")
GDM_ADDR = ("239.0.0.250", 32414)
CHECK_EVERY = 30      # s – sprawdzanie stanu
DISCOVER_EVERY = 300  # s – ponowne wyszukiwanie w sieci
_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def lan_ip():
    """Adres IP Raspberry Pi w sieci lokalnej (bez wysyłania jakiegokolwiek ruchu)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("192.0.2.1", 9))  # TEST-NET – tylko wybór interfejsu
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def identity(host, port, timeout=3):
    """Zapytanie /identity – nie wymaga logowania ani tokenu."""
    url = "http://%s:%d/identity" % (host, int(port))
    with _opener.open(url, timeout=timeout) as resp:
        root = ET.fromstring(resp.read())
    return {"machine_id": root.get("machineIdentifier", ""), "version": root.get("version", "")}


def gdm_discover(timeout=2.0):
    """Wyszukuje serwery Plex w sieci protokołem GDM (jak aplikacje Plex)."""
    found = {}
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
        sock.settimeout(0.4)
        msg = b"M-SEARCH * HTTP/1.1\r\n\r\n"
        for addr in (GDM_ADDR, ("255.255.255.255", 32414)):
            try:
                sock.sendto(msg, addr)
            except OSError:
                pass
        end = time.time() + timeout
        while time.time() < end:
            try:
                data, (ip, _) = sock.recvfrom(4096)
            except socket.timeout:
                continue
            except OSError:
                break
            text = data.decode("utf-8", "replace")
            if "plex/media-server" not in text.lower():
                continue
            hdr = dict(re.findall(r"^([A-Za-z-]+):\s*(.*?)\s*$", text, re.M))
            mid = hdr.get("Resource-Identifier") or ip
            found[mid] = {"name": hdr.get("Name") or ip, "host": ip,
                          "port": int(hdr.get("Port") or 32400), "machine_id": mid,
                          "version": hdr.get("Version", "")}
    finally:
        sock.close()
    return list(found.values())


class Monitor:
    def __init__(self):
        self.lock = threading.Lock()
        self.discovered = []
        self.status = []
        self.last_discover = 0
        self._stop = threading.Event()
        self._wake = threading.Event()

    def start(self):
        threading.Thread(target=self._loop, name="plexdl-plex", daemon=True).start()

    def stop(self):
        self._stop.set()
        self._wake.set()

    def refresh(self, discover=False):
        if discover:
            self.last_discover = 0
        self._wake.set()

    def discover_now(self):
        try:
            found = gdm_discover()
        except OSError as e:
            log.warning("GDM: %s", e)
            found = []
        with self.lock:
            self.discovered = found
            self.last_discover = time.time()
        self._check()
        return found

    def _loop(self):
        while not self._stop.is_set():
            try:
                cfg = config.get()
                if cfg.get("plex_autodiscover", True) and time.time() - self.last_discover > DISCOVER_EVERY:
                    self.discover_now()
                else:
                    self._check()
            except Exception:
                log.exception("Monitor Plex")
            self._wake.wait(CHECK_EVERY)
            self._wake.clear()

    def _candidates(self):
        cfg = config.get()
        items, ip = [], lan_ip()
        for s in cfg.get("plex_servers", []):
            items.append({"id": s.get("id"), "name": s.get("name") or s.get("host"),
                          "host": s.get("host"), "port": int(s.get("port") or 32400), "source": "manual"})
        if cfg.get("plex_autodiscover", True):
            items.append({"id": "local", "name": socket.gethostname(), "host": "127.0.0.1",
                          "port": 32400, "source": "local", "display_host": ip})
            with self.lock:
                for d in self.discovered:
                    items.append({"id": "gdm-" + d["machine_id"][:12], "name": d["name"],
                                  "host": d["host"], "port": d["port"], "source": "auto"})
        return items

    def _check(self):
        out, seen = [], {}
        for c in self._candidates():
            st = dict(c, online=False, version="", machine_id="")
            st.setdefault("display_host", c["host"])
            try:
                st.update(identity(c["host"], c["port"]), online=True)
            except Exception:
                if c["source"] == "local":
                    continue  # brak Plexa na tym Pi – nie pokazujemy
            key = st["machine_id"] or "%s:%s" % (st["display_host"], st["port"])
            if key in seen:  # ten sam serwer wykryty kilkoma drogami
                prev = seen[key]
                if c["source"] == "manual":
                    prev.update(name=c["name"], source="manual", id=c["id"])
                elif c["source"] == "auto" and prev["source"] == "local":
                    prev["name"] = c["name"]  # nazwa serwera z Plexa zamiast nazwy hosta
                continue
            seen[key] = st
            out.append(st)
        for s in out:
            if s["display_host"] == "127.0.0.1":
                s["display_host"] = lan_ip()
        with self.lock:
            self.status = out

    def snapshot(self):
        with self.lock:
            return [dict(s) for s in self.status]


monitor = Monitor()
