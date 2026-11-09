#!/usr/bin/env python3
"""Plex Downloader – webowy menedżer pobierania do biblioteki Plex (Raspberry Pi)."""
import argparse
import getpass
import logging
import os
import re
import signal
import subprocess
import sys
import threading
import time
import uuid
from datetime import timedelta
from functools import wraps
from urllib.parse import urlparse

from flask import Flask, jsonify, redirect, render_template, request, send_file, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

import actlog
import config
import filemanager as fm
import i18n
from i18n import _
import movieinfo
import naming
import wizard
import plexservers
from downloader import Manager, disk_status, probe

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("PLEXDL_DB", os.path.join(BASE_DIR, "plexdl.db"))


def read_version():
    try:
        with open(os.path.join(BASE_DIR, "VERSION")) as f:
            return f.read().strip()
    except OSError:
        return "dev"


VERSION = read_version()
log = logging.getLogger("plexdl")
app = Flask(__name__)
manager = None
_failed_logins = {}


# ---------------------------------------------------------------- autoryzacja
def _same_origin():
    """Zwykły formularz HTML (bez nagłówka X-PlexDL): Origin/Referer musi wskazywać ten sam host."""
    src = request.headers.get("Origin") or request.headers.get("Referer") or ""
    return bool(src) and urlparse(src).netloc == request.host


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not session.get("user"):
            if request.path.startswith("/api/"):
                return jsonify(error=_("Session expired – please log in again.")), 401
            return redirect(url_for("login"))
        if request.method == "POST" and request.headers.get("X-PlexDL") != "1" and not (
                getattr(view, "form_post", False) and _same_origin()):
            return jsonify(error=_("Missing request header.")), 400  # ochrona przed CSRF
        return view(*args, **kwargs)
    return wrapper


@app.route("/login", methods=["GET", "POST"])
def login():
    cfg = config.get()
    no_password = not cfg.get("password_hash")
    error = ""
    if request.method == "POST" and not no_password:
        ip = request.remote_addr or "?"
        fails = _failed_logins.get(ip, 0)
        if fails >= 3:
            time.sleep(min(10, fails))  # spowolnienie zgadywania hasła
        user = request.form.get("username", "").strip()
        pwd = request.form.get("password", "")
        if user == cfg.get("username") and check_password_hash(cfg["password_hash"], pwd):
            _failed_logins.pop(ip, None)
            session.clear()
            session["user"] = user
            session.permanent = bool(request.form.get("remember"))
            actlog.write("LOGIN", "%s (%s)" % (user, ip))
            return redirect(url_for("index"))
        _failed_logins[ip] = fails + 1
        error = _("Invalid username or password.")
    return render_template("login.html", error=error, no_password=no_password, version=VERSION)


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.context_processor
def inject_i18n():
    cfg = config.get()
    return {"_": _, "lang": i18n.current(), "theme": cfg.get("theme", "dark"),
            "i18n_catalog": i18n.catalog(), "languages": i18n.available()}


def _welcome():
    """Wybór języka przy pierwszym logowaniu."""
    if request.method == "POST":
        code = request.form.get("language", "en")
        if code in {l["code"] for l in i18n.available()}:
            config.set_language(code)
            actlog.write("SETTINGS", "language = %s" % code)
        return redirect(url_for("index"))
    return render_template("welcome.html", version=VERSION)


_welcome.form_post = True
welcome = app.route("/welcome", methods=["GET", "POST"], endpoint="welcome")(login_required(_welcome))


@app.route("/")
@login_required
def index():
    if not config.get().get("wizard_done"):
        return redirect(url_for("setup_wizard"))
    if not config.get().get("language"):
        return redirect(url_for("welcome"))
    return render_template("index.html", version=VERSION, user=session.get("user"), page="home")


@app.route("/setup")
@login_required
def setup_wizard():
    """Kreator pierwszego uruchomienia (także ponownie z Ustawień)."""
    return render_template("wizard.html", version=VERSION, user=session.get("user"), page="wizard")


@app.route("/files")
@login_required
def files_page():
    return render_template("files.html", version=VERSION, user=session.get("user"), page="files")


# ---------------------------------------------------------------- API
def err(message, code=400):
    return jsonify(error=message), code


def disks_payload():
    return [disk_status(d) for d in config.get().get("disks", [])]


@app.route("/api/state")
@login_required
def api_state():
    return jsonify(jobs=manager.list(), disks=disks_payload(),
                   categories=config.get().get("categories", []),
                   engine={"ok": manager.engine_ok, "error": manager.engine_error},
                   version=VERSION)


@app.route("/api/status")
@login_required
def api_status():
    """Dane do paska nagłówka: adres Downloadera, serwery Plex, operacje, VPN."""
    cfg = config.get()
    return jsonify(server={"ip": plexservers.lan_ip(), "port": int(cfg.get("port", 8800)),
                           "hostname": plexservers.socket.gethostname()},
                   plex=plexservers.monitor.snapshot(),
                   engine={"ok": manager.engine_ok},
                   downloads=sum(1 for j in manager.list() if j["status"] in ("downloading", "queued")),
                   ops=fm.ops.active(),
                   vpn={"available": False, "planned": True},
                   version=VERSION)


@app.route("/api/probe", methods=["POST"])
@login_required
def api_probe():
    url = (request.get_json(silent=True) or {}).get("url", "").strip()
    if urlparse(url).scheme not in ("http", "https"):
        return err(_("Enter a link starting with http:// or https://"))
    info = {"filename": naming.filename_from_url(url), "size": None, "resumable": None,
            "ext": "", "reachable": False, "probe_error": ""}
    try:
        info.update(probe(url))
        info["reachable"] = True
    except Exception as e:
        info["probe_error"] = str(e)
        info["ext"] = naming.split_ext(info["filename"])[1]
    info["guess"] = naming.guess(info["filename"] or "")
    info["editions"] = naming.EDITIONS
    info["versions"] = naming.VERSIONS
    if not info["ext"]:
        info["ext"] = info["guess"]["ext"]
    return jsonify(info)


@app.route("/api/info")
@login_required
def api_info():
    """Poglądowe dane o filmie/serialu z TMDB (nic nie jest zapisywane)."""
    if not movieinfo.configured():
        return jsonify(configured=False)
    a = request.args
    kind = "tv" if a.get("kind") == "tv" else "movie"
    title, year = movieinfo.split_title(a.get("title", ""))
    if a.get("year", "").isdigit():
        year = int(a["year"])

    def num(k):
        v = a.get(k, "")
        return int(v) if v.isdigit() else None
    try:
        data = movieinfo.lookup(kind, title, year, num("id"), num("season"), num("episode"))
    except movieinfo.InfoError as e:
        return jsonify(configured=True, error=str(e))
    data["configured"] = True
    data["query"] = {"title": title, "year": year}
    return jsonify(data)


@app.route("/api/jobs", methods=["POST"])
@login_required
def api_add():
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    if urlparse(url).scheme not in ("http", "https"):
        return err(_("Enter a link starting with http:// or https://"))
    ext = (data.get("ext") or "").strip().lower()
    if ext and not ext.startswith("."):
        ext = "." + ext
    if ext not in naming.VIDEO_EXTS:
        return err(_("Unsupported or unrecognized file extension: %r") % (ext or "brak"))
    d = config.disk(data.get("disk_id"))
    if not d:
        return err(_("Choose a target disk."))
    cat = config.category(data.get("category") or ("tv" if data.get("kind") == "tv" else "movies"))
    if not cat:
        return err(_("Choose a category."))
    base = (d.get("paths") or {}).get(cat["id"])
    if not base:
        return err(_("Disk %s has no folder for the category “%s” – add it in Settings.") % (d["label"], cat["label"]))
    adv = data.get("advanced") or {}
    ids = {}
    if adv.get("use_id") and adv.get("tmdb_id"):
        ids["tmdb"] = adv.get("tmdb_id")
    try:
        if cat["kind"] == "other":
            folder, filename = naming.movie_target(base, data.get("name"), ext)
        elif cat["kind"] == "tv":
            folder, filename = naming.tv_target(base, data.get("show"), data.get("season"),
                                                data.get("episode"), data.get("episode_title"), ext,
                                                ids=ids)
        else:
            folder, filename = naming.movie_target(base, data.get("name"), ext,
                                                   edition=adv.get("edition"), version=adv.get("version"),
                                                   ids=ids)
        size = data.get("size")
        size = int(size) if isinstance(size, (int, float)) and size > 0 else None
        job = manager.add(url, d["id"], cat["id"], folder, filename, cat["kind"],
                          os.path.splitext(filename)[0], size)
    except ValueError as e:
        return err(str(e))
    return jsonify(job=job)


@app.route("/api/jobs/<job_id>/<action>", methods=["POST"])
@login_required
def api_job_action(job_id, action):
    actions = {"pause": manager.pause, "resume": manager.resume, "cancel": manager.cancel,
               "retry": manager.retry, "remove": manager.remove}
    if action not in actions:
        return err(_("Unknown action."), 404)
    try:
        actions[action](job_id)
    except ValueError as e:
        return err(str(e))
    except Exception as e:
        return err(_("Download engine error: %s") % e, 500)
    return jsonify(ok=True)


@app.route("/api/jobs/clear", methods=["POST"])
@login_required
def api_clear():
    manager.clear_finished()
    return jsonify(ok=True)


@app.route("/api/settings", methods=["GET"])
@login_required
def api_settings_get():
    cfg = config.get()
    return jsonify(disks=cfg.get("disks", []), categories=cfg.get("categories", []),
                   username=cfg.get("username"),
                   connections_per_file=cfg.get("connections_per_file"),
                   max_concurrent=cfg.get("max_concurrent"),
                   max_speed_mbps=cfg.get("max_speed_mbps"),
                   require_mount=cfg.get("require_mount"),
                   # klucz TMDB nie trafia do przeglądarki – tylko maska (pełny: /api/settings/tmdb-key)
                   tmdb_key_set=bool(cfg.get("tmdb_api_key")),
                   tmdb_key_mask=_mask_key(cfg.get("tmdb_api_key", "")),
                   plex_servers=cfg.get("plex_servers", []),
                   plex_autodiscover=cfg.get("plex_autodiscover", True),
                   thumbs_mode=cfg.get("thumbs_mode", "online"),
                   port=cfg.get("port", 8800), language=i18n.current(), theme=cfg.get("theme", "dark"),
                   app_dir=BASE_DIR, system_user=getpass.getuser(), ip=plexservers.lan_ip(),
                   home=wizard.home_dir(), log=actlog.info())


def _mask_key(key):
    key = key or ""
    return ("•" * 10 + key[-3:]) if len(key) > 6 else ("•" * len(key))


@app.route("/api/settings/tmdb-key")
@login_required
def api_tmdb_key():
    """Pełny klucz – tylko na żądanie (pole „Pokaż klucz”)."""
    return jsonify(key=config.get().get("tmdb_api_key", ""))


def _abs_path(value, what):
    value = (value or "").strip()
    if not value:
        return ""
    if not value.startswith("/") or ".." in value.split("/"):
        raise ValueError(_("The path “%s” must be absolute (start with /).") % what)
    return value.rstrip("/") or "/"


@app.route("/api/settings", methods=["POST"])
@login_required
def api_settings_post():
    data = request.get_json(silent=True) or {}
    try:
        cats, seen = [], set()
        for raw in data.get("categories") or []:
            label = (raw.get("label") or "").strip()
            if not label:
                raise ValueError(_("Every category must have a name."))
            cid = (raw.get("id") or "").strip()
            if not re.match(r"^[a-z0-9-]{1,24}$", cid):
                cid = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")[:24] or uuid.uuid4().hex[:6]
            while cid in seen:
                cid = cid[:20] + "-" + uuid.uuid4().hex[:3]
            seen.add(cid)
            kind = raw.get("kind") if raw.get("kind") in ("movie", "tv", "other") else "movie"
            cats.append({"id": cid, "label": label[:40], "kind": kind,
                         "folder": naming.sanitize(raw.get("folder") or "")[:60],
                         "tmdb": bool(raw.get("tmdb", True)) and kind != "other"})
        if not cats:
            raise ValueError(_("At least one category must remain."))
        # mapowanie identyfikatorów nowych kategorii (klient używa tymczasowych „new-…”)
        idmap = {}
        for raw, c in zip(data.get("categories") or [], cats):
            idmap[(raw.get("id") or raw.get("tmp") or "").strip()] = c["id"]
        disks = []
        for raw in data.get("disks") or []:
            d = {k: (raw.get(k) or "").strip() for k in ("id", "label", "subtitle")}
            if not d["label"]:
                raise ValueError(_("Every disk must have a name."))
            d["mount"] = _abs_path(raw.get("mount"), "punkt montowania – " + d["label"])
            if not d["mount"]:
                raise ValueError(_("Enter the mount point for disk %s.") % d["label"])
            paths = {}
            for key, val in (raw.get("paths") or {}).items():
                cid = idmap.get(key, key)
                if cid in seen:
                    p = _abs_path(val, "%s – %s" % (d["label"], cid))
                    if p:
                        paths[cid] = p
            d["paths"] = paths
            if not re.match(r"^[a-z0-9_-]{1,32}$", d["id"]):
                d["id"] = uuid.uuid4().hex[:8]
            disks.append(d)
        servers = []
        for raw in data.get("plex_servers") or []:
            host = (raw.get("host") or "").strip()
            if not host:
                continue
            if not re.match(r"^[A-Za-z0-9.\-:]+$", host):
                raise ValueError(_("Invalid Plex server address: %s") % host)
            port = int(raw.get("port") or 32400)
            if not 1 <= port <= 65535:
                raise ValueError(_("Invalid Plex server port."))
            servers.append({"id": raw.get("id") or uuid.uuid4().hex[:6],
                            "name": (raw.get("name") or host).strip()[:40], "host": host, "port": port})
        conns = max(1, min(16, int(data.get("connections_per_file", 6))))
        conc = max(1, min(10, int(data.get("max_concurrent", 2))))
        speed = max(0.0, float(data.get("max_speed_mbps") or 0))
    except (TypeError, ValueError) as e:
        return err(str(e) if isinstance(e, ValueError) and str(e) else _("Invalid values."))
    # None = pole nie było zmieniane → zostaje zapisany klucz
    raw_key = data.get("tmdb_api_key")
    tmdb_key = config.get().get("tmdb_api_key", "") if raw_key is None else re.sub(r"\s+", "", raw_key)
    mode = data.get("thumbs_mode") if data.get("thumbs_mode") in ("online", "local", "off") else "online"
    config.update(note=data.get("note") or "Settings saved",
                  categories=cats, disks=disks, connections_per_file=conns, max_concurrent=conc,
                  max_speed_mbps=speed, require_mount=bool(data.get("require_mount", True)),
                  tmdb_api_key=tmdb_key, plex_servers=servers,
                  plex_autodiscover=bool(data.get("plex_autodiscover", True)), thumbs_mode=mode)
    manager.apply_settings()
    plexservers.monitor.refresh()
    actlog.write("SETTINGS", _("Settings saved"))
    return jsonify(ok=True)


# ---------------------------------------------------------------- eksport / import ustawień
EXPORT_KEYS = ("categories", "disks", "plex_servers", "plex_autodiscover", "connections_per_file", "max_concurrent",
               "max_speed_mbps", "require_mount", "thumbs_mode", "language", "theme")
IMPORT_SECTIONS = {
    "disks": ("disks",),
    "categories": ("categories",),
    "plex": ("plex_servers", "plex_autodiscover"),
    "downloads": ("connections_per_file", "max_concurrent", "max_speed_mbps", "require_mount"),
    "preview": ("thumbs_mode", "tmdb_api_key"),
    "interface": ("language", "theme"),
}


@app.route("/api/settings/export")
@login_required
def api_settings_export():
    """Plik JSON z ustawieniami – bez loginu, hasła i kluczy sesji (klucz TMDB tylko na życzenie)."""
    from flask import Response
    import json as _json
    cfg = config.get()
    out = {"_plexdl": {"app": "plex-downloader", "version": VERSION, "exported": time.strftime("%Y-%m-%d %H:%M")}}
    for k in EXPORT_KEYS:
        out[k] = cfg.get(k)
    if request.args.get("tmdb") == "1" and cfg.get("tmdb_api_key"):
        out["tmdb_api_key"] = cfg["tmdb_api_key"]
    actlog.write("SETTINGS", "settings exported%s" % (" (with TMDB key)" if "tmdb_api_key" in out else ""))
    name = "plexdl-settings-%s.json" % time.strftime("%Y%m%d-%H%M")
    return Response(_json.dumps(out, indent=2, ensure_ascii=False), mimetype="application/json",
                    headers={"Content-Disposition": "attachment; filename=%s" % name})


def _import_clean(data):
    """Sprawdza plik importu; zwraca słownik gotowych wartości (tylko klucze, które są w pliku)."""
    if not isinstance(data, dict) or not isinstance(data.get("_plexdl"), dict):
        raise ValueError(_("This is not a Plex Downloader settings file."))
    out = {}
    if isinstance(data.get("categories"), list):
        cats, seen = [], set()
        for raw in data["categories"]:
            if not isinstance(raw, dict) or not str(raw.get("label") or "").strip():
                continue
            label = str(raw["label"]).strip()[:40]
            cid = str(raw.get("id") or "")
            if not re.match(r"^[a-z0-9-]{1,24}$", cid) or cid in seen:
                cid = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")[:20] or "cat"
                while cid in seen:
                    cid = cid[:20] + "-" + uuid.uuid4().hex[:3]
            seen.add(cid)
            kind = raw.get("kind") if raw.get("kind") in ("movie", "tv", "other") else "movie"
            cats.append({"id": cid, "label": label, "kind": kind,
                         "folder": naming.sanitize(str(raw.get("folder") or ""))[:60],
                         "tmdb": bool(raw.get("tmdb", True)) and kind != "other"})
        if cats:
            out["categories"] = cats
    if isinstance(data.get("disks"), list):
        disks = []
        for raw in data["disks"]:
            if not isinstance(raw, dict):
                continue
            label = str(raw.get("label") or "").strip()[:40]
            mount = _abs_path(str(raw.get("mount") or ""), label or "?")
            if not label or not mount:
                continue
            paths = {}
            for cid, val in (raw.get("paths") or {}).items():
                p = _abs_path(str(val or ""), "%s – %s" % (label, cid))
                if p:
                    paths[str(cid)] = p
            did = str(raw.get("id") or "")
            disks.append({"id": did if re.match(r"^[a-z0-9_-]{1,32}$", did) else uuid.uuid4().hex[:8],
                          "label": label, "subtitle": str(raw.get("subtitle") or "")[:40], "mount": mount, "paths": paths})
        out["disks"] = disks
    if isinstance(data.get("plex_servers"), list):
        servers = []
        for raw in data["plex_servers"]:
            host = str((raw or {}).get("host") or "").strip()
            if host and re.match(r"^[A-Za-z0-9.\-:]+$", host):
                port = int(raw.get("port") or 32400)
                if 1 <= port <= 65535:
                    servers.append({"id": str(raw.get("id") or uuid.uuid4().hex[:6])[:12],
                                    "name": str(raw.get("name") or host)[:40], "host": host, "port": port})
        out["plex_servers"] = servers
    if "plex_autodiscover" in data:
        out["plex_autodiscover"] = bool(data["plex_autodiscover"])
    if "connections_per_file" in data:
        out["connections_per_file"] = max(1, min(16, int(data["connections_per_file"])))
    if "max_concurrent" in data:
        out["max_concurrent"] = max(1, min(10, int(data["max_concurrent"])))
    if "max_speed_mbps" in data:
        out["max_speed_mbps"] = max(0.0, float(data["max_speed_mbps"] or 0))
    if "require_mount" in data:
        out["require_mount"] = bool(data["require_mount"])
    if data.get("thumbs_mode") in ("online", "local", "off"):
        out["thumbs_mode"] = data["thumbs_mode"]
    if isinstance(data.get("tmdb_api_key"), str) and data["tmdb_api_key"].strip():
        out["tmdb_api_key"] = re.sub(r"\s+", "", data["tmdb_api_key"])
    if data.get("language") in {l["code"] for l in i18n.available()}:
        out["language"] = data["language"]
    if data.get("theme") in ("dark", "light"):
        out["theme"] = data["theme"]
    return out


@app.route("/api/settings/import/preview", methods=["POST"])
@login_required
def api_settings_import_preview():
    try:
        new = _import_clean((request.get_json(silent=True) or {}).get("data"))
    except (TypeError, ValueError) as e:
        return err(str(e) or _("Invalid values."))
    cfg = config.get()
    meta = ((request.get_json(silent=True) or {}).get("data") or {}).get("_plexdl") or {}
    sections = {}
    for sec, keys in IMPORT_SECTIONS.items():
        present = [k for k in keys if k in new]
        if not present:
            continue
        changes = [{"key": k, "old": cfg.get(k) if k != "tmdb_api_key" else bool(cfg.get(k)),
                    "new": new[k] if k != "tmdb_api_key" else True}
                   for k in present if (cfg.get(k) != new[k])]
        sections[sec] = {"changes": changes}
    # dyski: czy foldery z pliku istnieją na tym urządzeniu
    if "disks" in new:
        paths = [p for d in new["disks"] for p in d["paths"].values()]
        status = {x["path"]: x for x in wizard.check(paths)}
        sections["disks"]["disks"] = [{"label": d["label"], "mount": d["mount"], "mounted": os.path.isdir(d["mount"]),
                                       "paths": [dict(status.get(p, {}), cat=c) for c, p in d["paths"].items()]}
                                      for d in new["disks"]]
    return jsonify(meta=meta, sections=sections)


@app.route("/api/settings/import", methods=["POST"])
@login_required
def api_settings_import():
    d = request.get_json(silent=True) or {}
    try:
        new = _import_clean(d.get("data"))
    except (TypeError, ValueError) as e:
        return err(str(e) or _("Invalid values."))
    chosen = [s for s in (d.get("sections") or []) if s in IMPORT_SECTIONS]
    changes = {k: new[k] for s in chosen for k in IMPORT_SECTIONS[s] if k in new}
    if not changes:
        return err(_("Nothing selected."))
    lang = changes.pop("language", None)
    config.update(note="Settings imported", **changes)
    if lang and lang != config.get().get("language"):
        config.set_language(lang)
    manager.apply_settings()
    plexservers.monitor.refresh()
    actlog.write("SETTINGS", "settings imported: %s" % ", ".join(chosen))
    return jsonify(ok=True, reload=bool(lang) or "theme" in changes)


# ---------------------------------------------------------------- dyski: kolejność i nazwa (strona główna, Menedżer plików)
DISK_LABEL_MAX = 16


@app.route("/api/disks/order", methods=["POST"])
@login_required
def api_disks_order():
    ids = (request.get_json(silent=True) or {}).get("ids") or []
    disks = config.get().get("disks", [])
    pos = {i: n for n, i in enumerate(ids)}
    ordered = sorted(disks, key=lambda d: pos.get(d.get("id"), len(pos)))
    if [d["id"] for d in ordered] != [d["id"] for d in disks]:
        config.update(make_backup=False, disks=ordered)   # kolejność – bez punktu przywracania
    return jsonify(ok=True)


@app.route("/api/disks/rename", methods=["POST"])
@login_required
def api_disks_rename():
    d = request.get_json(silent=True) or {}
    label = re.sub(r"\s+", " ", (d.get("label") or "")).strip()[:DISK_LABEL_MAX]
    if not label:
        return err(_("Every disk must have a name."))
    disks = [dict(x) for x in config.get().get("disks", [])]
    hit = next((x for x in disks if x.get("id") == d.get("id")), None)
    if not hit:
        return err(_("Unknown disk."))
    old, hit["label"] = hit.get("label"), label
    config.update(note="Disk renamed", disks=disks)
    actlog.write("SETTINGS", "disk renamed: %s → %s" % (old, label))
    return jsonify(ok=True, label=label)


# ---------------------------------------------------------------- kreator
@app.route("/api/wizard/state")
@login_required
def api_wizard_state():
    cfg = config.get()
    return jsonify(mounts=wizard.mounts(), home=wizard.home_dir(), system_user=getpass.getuser(),
                   ip=plexservers.lan_ip(), port=cfg.get("port", 8800), categories=cfg["categories"],
                   disks=cfg.get("disks", []), language=cfg.get("language") or i18n.current(),
                   theme=cfg.get("theme", "dark"), wizard_done=bool(cfg.get("wizard_done")),
                   tmdb_key_set=bool(cfg.get("tmdb_api_key")), tmdb_key_mask=_mask_key(cfg.get("tmdb_api_key", "")),
                   plex_servers=cfg.get("plex_servers", []), plex_autodiscover=cfg.get("plex_autodiscover", True))


@app.route("/api/wizard/scan", methods=["POST"])
@login_required
def api_wizard_scan():
    d = request.get_json(silent=True) or {}
    return fm_call(lambda: {"result": fm.scan_paths(d.get("mount", ""), config.get()["categories"])})


@app.route("/api/wizard/check", methods=["POST"])
@login_required
def api_wizard_check():
    paths = (request.get_json(silent=True) or {}).get("paths") or []
    return jsonify(result=wizard.check([str(p) for p in paths][:100]))


@app.route("/api/wizard/create", methods=["POST"])
@login_required
def api_wizard_create():
    paths = (request.get_json(silent=True) or {}).get("paths") or []
    created, problems = wizard.create([str(p) for p in paths][:100])
    for p in created:
        actlog.write("CREATE", "folder %s" % p)
    return jsonify(created=created, problems=problems, result=wizard.check([str(p) for p in paths][:100]))


@app.route("/api/wizard/finish", methods=["POST"])
@login_required
def api_wizard_finish():
    data = request.get_json(silent=True) or {}
    cfg = config.get()
    seen = {c["id"] for c in cfg["categories"]}
    try:
        disks = []
        for raw in data.get("disks") or []:
            label = (raw.get("label") or "").strip()[:40]
            if not label:
                raise ValueError(_("Every disk must have a name."))
            mount = _abs_path(raw.get("mount"), label)
            if not mount:
                raise ValueError(_("Enter the mount point for disk %s.") % label)
            paths = {}
            for cid, val in (raw.get("paths") or {}).items():
                p = _abs_path(val, "%s – %s" % (label, cid))
                if cid in seen and p:
                    paths[cid] = p
            disks.append({"id": uuid.uuid4().hex[:8], "label": label,
                          "subtitle": (raw.get("subtitle") or "").strip()[:40], "mount": mount, "paths": paths})
        if not disks and not data.get("skip_disks"):
            raise ValueError(_("At least one disk must remain."))
        if data.get("skip_disks"):
            # „Pomiń”: przy pierwszym uruchomieniu bez dysków (przykładowe ścieżki znikają),
            # przy ponownym kreatorze dotychczasowe dyski zostają
            disks = cfg.get("disks", []) if cfg.get("wizard_done") else []
        servers = []
        for raw in data.get("plex_servers") or []:
            host = (raw.get("host") or "").strip()
            if not host:
                continue
            if not re.match(r"^[A-Za-z0-9.\-:]+$", host):
                raise ValueError(_("Invalid Plex server address: %s") % host)
            port = int(raw.get("port") or 32400)
            if not 1 <= port <= 65535:
                raise ValueError(_("Invalid Plex server port."))
            servers.append({"id": uuid.uuid4().hex[:6], "name": (raw.get("name") or host).strip()[:40],
                            "host": host, "port": port})
    except (TypeError, ValueError) as e:
        return err(str(e) if str(e) else _("Invalid values."))
    raw_key = data.get("tmdb_api_key")
    tmdb_key = cfg.get("tmdb_api_key", "") if raw_key is None else re.sub(r"\s+", "", raw_key)
    config.update(note="Setup wizard", disks=disks, plex_servers=servers,
                  plex_autodiscover=bool(data.get("plex_autodiscover", True)), tmdb_api_key=tmdb_key,
                  require_mount=bool(data.get("require_mount", True)), wizard_done=True)
    manager.apply_settings()
    plexservers.monitor.refresh()
    actlog.write("SETTINGS", "setup wizard finished (%d disk(s))" % len(disks))
    return jsonify(ok=True)


@app.route("/api/interface", methods=["POST"])
@login_required
def api_interface():
    data = request.get_json(silent=True) or {}
    cfg = config.get()
    code = data.get("language")
    if code and code != cfg.get("language") and code in {l["code"] for l in i18n.available()}:
        config.set_language(code)
        actlog.write("SETTINGS", "language = %s" % code)
    theme = data.get("theme")
    if theme in ("dark", "light") and theme != cfg.get("theme"):
        config.update(note="Theme changed", theme=theme)
    return jsonify(ok=True)


@app.route("/api/log")
@login_required
def api_log():
    return jsonify(text=actlog.read(), **actlog.info())


@app.route("/api/log/export")
@login_required
def api_log_export():
    from flask import Response
    name = "plexdl-%s.log" % time.strftime("%Y%m%d-%H%M")
    return Response(actlog.read(), mimetype="text/plain; charset=utf-8",
                    headers={"Content-Disposition": "attachment; filename=%s" % name})


@app.route("/api/log/clear", methods=["POST"])
@login_required
def api_log_clear():
    actlog.clear()
    actlog.write("LOG", _("Log cleared"))
    return jsonify(ok=True, **actlog.info())


@app.route("/api/log/delete-backups", methods=["POST"])
@login_required
def api_log_delete_backups():
    n = actlog.delete_backups()
    return jsonify(ok=True, removed=n, **actlog.info())


@app.route("/api/disks/scan", methods=["POST"])
@login_required
def api_disks_scan():
    d = request.get_json(silent=True) or {}
    try:
        return jsonify(result=fm.scan_paths((d.get("mount") or "").strip(), d.get("categories") or [],
                                            d.get("paths") or {}))
    except fm.FMError as e:
        return err(str(e))


@app.route("/api/backups")
@login_required
def api_backups():
    return jsonify(backups=config.describe_backups(), keep_days=config.BACKUP_DAYS)


@app.route("/api/backups/delete", methods=["POST"])
@login_required
def api_backups_delete():
    names = (request.get_json(silent=True) or {}).get("names") or []
    if not isinstance(names, list):
        return err(_("Invalid values."))
    n = config.delete_backups([str(x) for x in names])
    if n:
        actlog.write("DELETE", "settings backups: %d" % n)
    return jsonify(removed=n)


@app.route("/api/backups/restore", methods=["POST"])
@login_required
def api_backup_restore():
    try:
        name = (request.get_json(silent=True) or {}).get("name", "")
        config.restore(name)
        actlog.write("RESTORE", name)
    except (ValueError, OSError) as e:
        return err(str(e))
    manager.apply_settings()
    plexservers.monitor.refresh()
    return jsonify(ok=True)


@app.route("/api/plex/discover", methods=["POST"])
@login_required
def api_plex_discover():
    found = plexservers.monitor.discover_now()
    return jsonify(found=found, status=plexservers.monitor.snapshot())


# ---------------------------------------------------------------- menedżer plików
def fm_call(fn, *args):
    try:
        return jsonify(fn(*args))
    except fm.FMError as e:
        return err(str(e))
    except OSError as e:
        return err(_("Disk error: %s") % e)


@app.route("/api/fm/list")
@login_required
def api_fm_list():
    a = request.args
    return fm_call(fm.list_items, a.get("disk", ""), a.get("cat", ""), manager.busy_paths())


def _plan(d):
    if d.get("show"):
        return fm.plan_episodes(d.get("src_disk"), d.get("src_cat"), d.get("show"), d.get("rels") or [],
                                d.get("dst_disk"), d.get("dst_cat"), manager.busy_paths())
    return fm.plan_move(d.get("src_disk"), d.get("src_cat"), d.get("names") or [],
                        d.get("dst_disk"), d.get("dst_cat"), manager.busy_paths())


@app.route("/api/fm/plan", methods=["POST"])
@login_required
def api_fm_plan():
    d = request.get_json(silent=True) or {}
    return fm_call(lambda: _plan(d))


@app.route("/api/fm/move", methods=["POST"])
@login_required
def api_fm_move():
    d = request.get_json(silent=True) or {}
    return fm_call(lambda: {"op": fm.ops.move(_plan(d), verify=not d.get("skip_verify"))["id"]})


@app.route("/api/fm/episodes")
@login_required
def api_fm_episodes():
    a = request.args
    return fm_call(fm.list_episodes, a.get("disk", ""), a.get("cat", ""), a.get("name", ""))


@app.route("/api/fm/delete", methods=["POST"])
@login_required
def api_fm_delete():
    d = request.get_json(silent=True) or {}
    if d.get("confirm") != "DELETE":
        return err(_("Deletion not confirmed."))
    return fm_call(fm.delete, d.get("disk"), d.get("cat"), d.get("names") or [], manager.busy_paths())


@app.route("/api/fm/ops")
@login_required
def api_fm_ops():
    return jsonify(ops=fm.ops.public())


@app.route("/api/fm/ops/<op_id>/cancel", methods=["POST"])
@login_required
def api_fm_cancel(op_id):
    return fm_call(lambda: fm.ops.cancel(op_id) or {"ok": True})


@app.route("/api/fm/ops/clear", methods=["POST"])
@login_required
def api_fm_clear():
    fm.ops.clear()
    return jsonify(ok=True)


@app.route("/api/fm/thumb")
@login_required
def api_fm_thumb():
    a = request.args
    try:
        path = fm.get_thumb(a.get("disk", ""), a.get("cat", ""), a.get("name", ""))
    except (fm.FMError, OSError):
        return ("", 404)
    resp = send_file(path, max_age=86400)
    return resp


@app.route("/api/fm/thumbs/refresh", methods=["POST"])
@login_required
def api_fm_thumbs_refresh():
    d = request.get_json(silent=True) or {}
    return fm_call(lambda: {"op": fm.ops.refresh_thumbs(d.get("disk"))["id"]})


@app.route("/api/fm/thumbs/delete", methods=["POST"])
@login_required
def api_fm_thumbs_delete():
    d = request.get_json(silent=True) or {}
    return fm_call(lambda: {"removed": fm.delete_thumbs(d.get("disk"))})


@app.route("/api/password", methods=["POST"])
@login_required
def api_password():
    data = request.get_json(silent=True) or {}
    cfg = config.get()
    if not check_password_hash(cfg["password_hash"], data.get("current", "")):
        return err(_("The current password is incorrect."))
    new = data.get("new", "")
    if len(new) < 6:
        return err(_("The new password must have at least 6 characters."))
    username = (data.get("username") or cfg["username"]).strip() or cfg["username"]
    config.update(note="Username/password changed", username=username, password_hash=generate_password_hash(new))
    session["user"] = username
    actlog.write("ACCOUNT", _("Username/password changed"))
    return jsonify(ok=True)


_version_cache = {"t": 0, "data": None}


@app.route("/api/version")
@login_required
def api_version():
    """Sprawdza (najwyżej co 10 min), czy w repozytorium GitHub są nowsze commity."""
    if _version_cache["data"] and time.time() - _version_cache["t"] < 600 and not request.args.get("force"):
        return jsonify(_version_cache["data"])
    resp = _api_version()
    _version_cache.update(t=time.time(), data=resp.get_json())
    return resp


def _ver_tuple(v):
    m = re.match(r"\s*(\d+)\.(\d+)\.(\d+)", v or "")
    return tuple(int(x) for x in m.groups()) if m else (0, 0, 0)


def _api_version():
    """Sprawdza tylko linię stabilną (gałąź main na GitHubie) – wersje beta nie są ogłaszane."""
    def git(*args):
        return subprocess.run(["git", "-C", BASE_DIR] + list(args), capture_output=True,
                              text=True, timeout=25)
    try:
        if git("rev-parse", "--is-inside-work-tree").returncode != 0:
            return jsonify(version=VERSION, available=None, message=_("This is not a git repository."))
        fetch = git("fetch", "--quiet", "origin", "+refs/heads/main:refs/remotes/origin/main")
        if fetch.returncode != 0:
            return jsonify(version=VERSION, available=None,
                           message=_("Could not connect to GitHub."))
        stable = git("show", "origin/main:VERSION").stdout.strip()
        beta = "beta" in VERSION.lower()
        newer = bool(stable) and _ver_tuple(stable) > _ver_tuple(VERSION)
        cmd = "./fix.sh" if beta else "./update.sh"
        return jsonify(version=VERSION, latest=stable if newer else VERSION, available=newer, cmd=cmd,
                       message=(_("Update available (%s). Run %s on the Raspberry Pi.") % (stable, cmd))
                       if newer else _("You have the latest version."))
    except Exception as e:
        return jsonify(version=VERSION, available=None, message=str(e))


# ---------------------------------------------------------------- start
def set_password():
    config.load()
    cfg = config.get()
    print(_("Plex Downloader login setup"))
    user = input(_("Username [%s]: ") % cfg.get("username", "admin")).strip() or cfg.get("username", "admin")
    while True:
        p1 = getpass.getpass(_("Password (min. 6 characters): "))
        p2 = getpass.getpass(_("Repeat password: "))
        if len(p1) < 6:
            print(_("Too short."))
        elif p1 != p2:
            print(_("Passwords do not match."))
        else:
            break
    config.update(note="Password set (console)", username=user, password_hash=generate_password_hash(p1))
    print(_("Saved. Username: %s") % user)


def check_folders():
    """Raport dla setup.sh: czy foldery kategorii istnieją i można w nich zapisywać."""
    cfg = config.load()
    if not cfg.get("wizard_done"):
        # nowa instalacja: przykładowe ścieżki z config.example.json nie mają tu znaczenia
        print("  \033[36m%s\033[0m" % _("Disks and folders are set in the setup wizard after the first login."))
        return
    if not cfg.get("disks"):
        print("  \033[33m%s\033[0m" % _("No disks configured yet – add them in Settings → Disks or run the setup wizard."))
        return
    cats = {c["id"]: c["label"] for c in cfg.get("categories", [])}
    for d in cfg.get("disks", []):
        for cid, label in cats.items():
            p = (d.get("paths") or {}).get(cid)
            if not p:
                print("  \033[90m– %-18s %-12s %s\033[0m" % (d["label"], label, _("(no folder – optional)")))
            elif not os.path.isdir(p):
                print("  \033[33m! %-18s %-12s %s %s\033[0m" % (d["label"], label, _("missing folder:"), p))
            elif not os.access(p, os.W_OK):
                print("  \033[33m! %-18s %-12s %s %s\033[0m" % (d["label"], label, _("no write permission:"), p))
            else:
                print("  \033[32m✔ %-18s %-12s %s\033[0m" % (d["label"], label, p))


_instance_lock = None


def single_instance():
    """Blokada: tylko jedna instancja może sterować aria2 i bazą zadań."""
    global _instance_lock
    import fcntl
    _instance_lock = open(DB_PATH + ".lock", "w")
    try:
        fcntl.flock(_instance_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        sys.exit("Plex Downloader is already running (lock %s.lock)." % DB_PATH)


def create_app():
    global manager
    single_instance()
    cfg = config.load()
    app.secret_key = cfg["secret_key"]
    app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
                      PERMANENT_SESSION_LIFETIME=timedelta(days=30))
    manager = Manager(DB_PATH)
    manager.start()
    fm.cleanup_tmp()
    plexservers.monitor.start()
    return app


def main():
    parser = argparse.ArgumentParser(description="Plex Downloader")
    parser.add_argument("--set-password", action="store_true", help="set username and password")
    parser.add_argument("--check-folders", action="store_true", help="check library folders")
    parser.add_argument("--set-language", metavar="CODE", help="set interface language (en, pl, …)")
    args = parser.parse_args()
    if args.set_password:
        set_password()
        return
    if args.set_language:
        config.load()
        codes = {l["code"] for l in i18n.available()}
        config.set_language(args.set_language if args.set_language in codes else "en")
        return
    if args.check_folders:
        check_folders()
        return
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    create_app()
    cfg = config.get()

    def shutdown(*_):
        plexservers.monitor.stop()
        manager.stop()
        sys.exit(0)
    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    log.info("Plex Downloader %s – http://%s:%s", VERSION, cfg["host"], cfg["port"])
    try:
        from waitress import serve
        serve(app, host=cfg["host"], port=int(cfg["port"]), threads=8, ident="PlexDownloader")
    except ImportError:
        log.warning("waitress not installed – using the Flask development server.")
        app.run(host=cfg["host"], port=int(cfg["port"]), threaded=True)


if __name__ == "__main__":
    main()
