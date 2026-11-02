"""Dziennik operacji użytkownika (pobrania, przeniesienia, usunięcia, zmiany ustawień).

Plik logs/plexdl.log, limit 1 MB. Po przekroczeniu bieżący plik trafia do
logs/bcup01.log (kolejne: bcup02.log, …), a dziennik zaczyna się od nowa.
Dziennik jest lokalny – nie trafia do kopii zapasowych ustawień ani do repozytorium.
"""
import os
import re
import threading
import time

import config

LIMIT = 1024 * 1024
_lock = threading.Lock()
_BCUP = re.compile(r"^bcup(\d{2,})\.log$")


def log_dir():
    d = os.environ.get("PLEXDL_LOGS") or os.path.join(os.path.dirname(os.path.abspath(config.CONFIG_PATH)), "logs")
    os.makedirs(d, mode=0o700, exist_ok=True)
    return d


def log_path():
    return os.path.join(log_dir(), "plexdl.log")


def backups():
    out = []
    for name in os.listdir(log_dir()):
        m = _BCUP.match(name)
        if m:
            p = os.path.join(log_dir(), name)
            out.append({"name": name, "num": int(m.group(1)), "size": os.path.getsize(p),
                        "mtime": os.path.getmtime(p)})
    return sorted(out, key=lambda b: b["num"])


def _rotate():
    nums = [b["num"] for b in backups()]
    nxt = (max(nums) + 1) if nums else 1
    os.replace(log_path(), os.path.join(log_dir(), "bcup%02d.log" % nxt))


def write(action, message):
    """action: DOWNLOAD, DONE, FAILED, CANCEL, MOVE, DELETE, SETTINGS, RESTORE, POSTERS, LOGIN…"""
    line = "%s  %-8s %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), action, message.replace("\n", " "))
    try:
        with _lock:
            p = log_path()
            if os.path.exists(p) and os.path.getsize(p) + len(line.encode()) > LIMIT:
                _rotate()
            with open(p, "a", encoding="utf-8") as f:
                f.write(line)
            os.chmod(p, 0o600)
    except OSError:
        pass  # dziennik nigdy nie może zatrzymać właściwej operacji


def read(max_bytes=LIMIT):
    p = log_path()
    if not os.path.exists(p):
        return ""
    with open(p, "rb") as f:
        size = os.path.getsize(p)
        if size > max_bytes:
            f.seek(size - max_bytes)
        return f.read().decode("utf-8", "replace")


def clear():
    with _lock:
        open(log_path(), "w").close()


def delete_backups():
    n = 0
    with _lock:
        for b in backups():
            try:
                os.remove(os.path.join(log_dir(), b["name"]))
                n += 1
            except OSError:
                pass
    return n


def info():
    p = log_path()
    return {"size": os.path.getsize(p) if os.path.exists(p) else 0, "limit": LIMIT, "backups": backups()}
