"""Konfiguracja aplikacji (config.json, wykluczony z repozytorium) + punkty przywracania."""
import copy
import json
import os
import re
import secrets
import threading
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.environ.get("PLEXDL_CONFIG", os.path.join(BASE_DIR, "config.json"))
EXAMPLE_PATH = os.path.join(BASE_DIR, "config.example.json")
BACKUP_DIR = os.environ.get("PLEXDL_BACKUPS",
                            os.path.join(os.path.dirname(os.path.abspath(CONFIG_PATH)), "backups"))
BACKUP_DAYS = 30
BACKUP_MAX = 300

# Kategorie domyślne. "kind" decyduje o nazewnictwie: movie → Tytuł (Rok)/…, tv → Serial/Season 01/…
# kind: movie → Tytuł (Rok)/…, tv → Serial/Season 01/…, other → nazwa bez zmian (np. nagrania domowe)
DEFAULT_CATEGORIES = [
    {"id": "movies", "label": "Movies", "kind": "movie", "folder": "Movies", "tmdb": True},
    {"id": "tv", "label": "TV Shows", "kind": "tv", "folder": "TV Shows", "tmdb": True},
    {"id": "kids", "label": "Kids", "kind": "movie", "folder": "Kids", "tmdb": True},
]
BUILTIN_LABELS = {"movies": "Movies", "tv": "TV Shows", "kids": "Kids"}

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
    "tmdb_api_key": "",
    "categories": DEFAULT_CATEGORIES,
    "disks": [],
    "plex_servers": [],          # [{"id","name","host","port"}] – dodane ręcznie
    "plex_autodiscover": True,   # wykrywanie serwerów Plex w sieci (GDM) + localhost
    "thumbs_mode": "online",     # online | local | off
    "language": "",              # "" = jeszcze nie wybrano (ekran wyboru przy logowaniu)
    "theme": "dark",             # dark | light
    "vpn": {"enabled": False, "provider": "tailscale", "listen": "lan"},  # zarezerwowane (wkrótce)
}

# Klucze, których przywrócenie kopii NIE nadpisuje (konto i sekrety bieżącej instalacji)
KEEP_ON_RESTORE = ("username", "password_hash", "secret_key", "aria2_secret")

_lock = threading.RLock()
_config = None


def _read(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _slug(text, fallback):
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")[:24]
    return s or fallback


def normalize(cfg):
    """Migracja starszych konfiguracji (1.0/1.1: disks.movies/tv) do kategorii (1.2)."""
    cats = cfg.get("categories")
    if not isinstance(cats, list) or not cats:
        cats = copy.deepcopy(DEFAULT_CATEGORIES)
    clean, seen = [], set()
    for c in cats:
        cid = _slug(c.get("id") or c.get("label"), "cat%d" % len(clean))
        if cid in seen:
            continue
        seen.add(cid)
        kind = c.get("kind") if c.get("kind") in ("movie", "tv", "other") else "movie"
        tmdb = c.get("tmdb")
        if tmdb is None:
            tmdb = cid in BUILTIN_LABELS
        clean.append({"id": cid, "label": (c.get("label") or cid).strip()[:40], "kind": kind,
                      "folder": (c.get("folder") or "").strip()[:60], "tmdb": bool(tmdb and kind != "other")})
    cfg["categories"] = clean
    for d in cfg.get("disks", []):
        paths = d.get("paths")
        if not isinstance(paths, dict):
            paths = {}
            if d.get("movies"):
                paths["movies"] = d["movies"]
            if d.get("tv"):
                paths["tv"] = d["tv"]
        # Kategoria bez ścieżki: podpowiedź „folder obok Movies”, jeśli taki istnieje na dysku
        root = os.path.dirname((paths.get("movies") or "").rstrip("/"))
        for c in clean:
            if not paths.get(c["id"]) and root and c.get("folder"):
                guess = os.path.join(root, c["folder"])
                if os.path.isdir(guess):
                    paths[c["id"]] = guess
        d["paths"] = {k: v for k, v in paths.items() if k in seen and v}
        d.pop("movies", None)
        d.pop("tv", None)
    return cfg


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
        before = json.dumps(data, sort_keys=True)
        normalize(cfg)
        changed = not os.path.exists(CONFIG_PATH)
        if not cfg.get("secret_key"):
            cfg["secret_key"] = secrets.token_hex(32)
            changed = True
        if not cfg.get("aria2_secret"):
            cfg["aria2_secret"] = secrets.token_hex(16)
            changed = True
        migrated = before != json.dumps({k: cfg.get(k) for k in data}, sort_keys=True)
        _config = cfg
        if changed or migrated:
            save(note="Configuration migrated" if migrated and not changed else "First run")
        return _config


def get():
    with _lock:
        return _config if _config is not None else load()


def save(new=None, note="", note_args=None):
    global _config
    with _lock:
        if new is not None:
            _config = new
        tmp = CONFIG_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(_config, f, indent=2, ensure_ascii=False)
        os.chmod(tmp, 0o600)
        os.replace(tmp, CONFIG_PATH)
        backup(note, note_args)


def update(note="", note_args=None, **changes):
    with _lock:
        cfg = copy.deepcopy(get())
        cfg.update(changes)
        normalize(cfg)
        save(cfg, note=note, note_args=note_args)
        return cfg


def disk(disk_id):
    for d in get().get("disks", []):
        if d.get("id") == disk_id:
            return d
    return None


def category(cat_id):
    for c in get().get("categories", []):
        if c.get("id") == cat_id:
            return c
    return None


# ------------------------------------------------------------------ punkty przywracania
_NAME = re.compile(r"^config-(\d{8}-\d{6})(?:-\d+)?\.json$")


def backup(note="", note_args=None):
    """Zapisuje migawkę konfiguracji po każdej zmianie; usuwa kopie starsze niż 30 dni
    (ostatnia kopia zostaje zawsze)."""
    try:
        os.makedirs(BACKUP_DIR, mode=0o700, exist_ok=True)
        files = list_backups()
        if files:
            try:
                last = _read(os.path.join(BACKUP_DIR, files[0]["name"]))
                if last.get("config") == _config:
                    return  # brak faktycznej zmiany
            except (OSError, ValueError):
                pass
        stamp = time.strftime("%Y%m%d-%H%M%S")
        name = "config-%s.json" % stamp
        n = 1
        while os.path.exists(os.path.join(BACKUP_DIR, name)):
            name = "config-%s-%d.json" % (stamp, n)
            n += 1
        path = os.path.join(BACKUP_DIR, name)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"created": time.time(), "note": note or "Settings changed",
                       "note_args": note_args or {}, "config": _config},
                      f, indent=1, ensure_ascii=False)
        os.chmod(path, 0o600)
        prune()
    except OSError:
        pass  # kopia zapasowa nigdy nie może zablokować zapisu ustawień


def list_backups():
    if not os.path.isdir(BACKUP_DIR):
        return []
    out = []
    for name in os.listdir(BACKUP_DIR):
        if not _NAME.match(name):
            continue
        path = os.path.join(BACKUP_DIR, name)
        try:
            st = os.stat(path)
        except OSError:
            continue
        out.append({"name": name, "mtime": st.st_mtime, "size": st.st_size})
    out.sort(key=lambda b: (b["mtime"], b["name"]), reverse=True)
    return out


def describe_backups():
    from i18n import _
    items = []
    for b in list_backups():
        note = ""
        try:
            data = _read(os.path.join(BACKUP_DIR, b["name"]))
            note = _(data.get("note", ""), **(data.get("note_args") or {}))
        except (OSError, ValueError):
            pass
        items.append(dict(b, note=note))
    return items


def delete_backups(names):
    """Usuwa wybrane kopie. Najnowsza (bieżąca) kopia nie może zostać usunięta."""
    files = list_backups()
    newest = files[0]["name"] if files else None
    removed = 0
    for name in names or []:
        if not _NAME.match(name or "") or name == newest:
            continue
        try:
            os.remove(os.path.join(BACKUP_DIR, name))
            removed += 1
        except OSError:
            pass
    return removed


def prune():
    files = list_backups()
    limit = time.time() - BACKUP_DAYS * 86400
    for i, b in enumerate(files):
        if i == 0:
            continue  # najnowsza kopia zostaje zawsze
        if b["mtime"] < limit or i >= BACKUP_MAX:
            try:
                os.remove(os.path.join(BACKUP_DIR, b["name"]))
            except OSError:
                pass


def restore(name):
    from i18n import _
    if not _NAME.match(name or ""):
        raise ValueError(_("Invalid backup name."))
    path = os.path.join(BACKUP_DIR, name)
    if not os.path.isfile(path):
        raise ValueError(_("No such backup."))
    snap = _read(path).get("config")
    if not isinstance(snap, dict):
        raise ValueError(_("The backup is damaged."))
    with _lock:
        cfg = copy.deepcopy(DEFAULTS)
        cfg.update(snap)
        for k in KEEP_ON_RESTORE:
            cfg[k] = get().get(k)
        normalize(cfg)
        save(cfg, note="Restored backup from {date}", note_args={"date": time.strftime(
            "%d.%m.%Y %H:%M", time.localtime(os.path.getmtime(path)))})
        return cfg


def set_language(code):
    """Zmienia język i tłumaczy nazwy wbudowanych kategorii, jeśli użytkownik ich nie zmienił."""
    from i18n import gettext, available
    known = {}
    for cid, en in BUILTIN_LABELS.items():
        known[cid] = {en} | {gettext(en, lang=l["code"]) for l in available()}
    with _lock:
        cfg = copy.deepcopy(get())
        cfg["language"] = code
        for c in cfg.get("categories", []):
            if c["id"] in known and c["label"] in known[c["id"]]:
                c["label"] = gettext(BUILTIN_LABELS[c["id"]], lang=code)
        normalize(cfg)
        save(cfg, note="Language changed")
        return cfg
