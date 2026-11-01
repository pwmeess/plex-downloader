"""Konfiguracja aplikacji (config.json, wykluczony z repozytorium)."""
import copy
import json
import os
import secrets
import threading

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.environ.get("PLEXDL_CONFIG", os.path.join(BASE_DIR, "config.json"))
EXAMPLE_PATH = os.path.join(BASE_DIR, "config.example.json")

DEFAULTS = {
    "host": "0.0.0.0",
    "port": 8800,
    "username": "admin",
    "password_hash": "",
    "secret_key": "",
    "aria2_rpc_port": 6800,
    "aria2_secret": "",
    "connections_per_file": 6,
    "max_concurrent": 2,
    "max_speed_mbps": 0,
    "require_mount": True,
    "disks": [],
}

_lock = threading.RLock()
_config = None


def _read(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load():
    global _config
    with _lock:
        data = {}
        if os.path.exists(CONFIG_PATH):
            data = _read(CONFIG_PATH)
        elif os.path.exists(EXAMPLE_PATH):
            data = _read(EXAMPLE_PATH)
        cfg = copy.deepcopy(DEFAULTS)
        cfg.update(data)
        changed = not os.path.exists(CONFIG_PATH)
        if not cfg.get("secret_key"):
            cfg["secret_key"] = secrets.token_hex(32)
            changed = True
        if not cfg.get("aria2_secret"):
            cfg["aria2_secret"] = secrets.token_hex(16)
            changed = True
        _config = cfg
        if changed:
            save()
        return _config


def get():
    with _lock:
        return _config if _config is not None else load()


def save(new=None):
    global _config
    with _lock:
        if new is not None:
            _config = new
        tmp = CONFIG_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(_config, f, indent=2, ensure_ascii=False)
        os.chmod(tmp, 0o600)
        os.replace(tmp, CONFIG_PATH)


def update(**changes):
    with _lock:
        cfg = copy.deepcopy(get())
        cfg.update(changes)
        save(cfg)
        return cfg


def disk(disk_id):
    for d in get().get("disks", []):
        if d.get("id") == disk_id:
            return d
    return None
