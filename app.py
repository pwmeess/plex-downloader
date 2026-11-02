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

import config
import filemanager as fm
import movieinfo
import naming
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
def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not session.get("user"):
            if request.path.startswith("/api/"):
                return jsonify(error="Sesja wygasła – zaloguj się ponownie."), 401
            return redirect(url_for("login"))
        if request.method == "POST" and request.headers.get("X-PlexDL") != "1":
            return jsonify(error="Brak nagłówka żądania."), 400  # ochrona przed CSRF
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
            return redirect(url_for("index"))
        _failed_logins[ip] = fails + 1
        error = "Nieprawidłowy login lub hasło."
    return render_template("login.html", error=error, no_password=no_password, version=VERSION)


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def index():
    return render_template("index.html", version=VERSION, user=session.get("user"), page="home")


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
        return err("Podaj link zaczynający się od http:// lub https://")
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
        return err("Podaj link zaczynający się od http:// lub https://")
    ext = (data.get("ext") or "").strip().lower()
    if ext and not ext.startswith("."):
        ext = "." + ext
    if ext not in naming.VIDEO_EXTS:
        return err("Nieobsługiwane lub nierozpoznane rozszerzenie pliku: %r" % (ext or "brak"))
    d = config.disk(data.get("disk_id"))
    if not d:
        return err("Wybierz dysk docelowy.")
    cat = config.category(data.get("category") or ("tv" if data.get("kind") == "tv" else "movies"))
    if not cat:
        return err("Wybierz kategorię.")
    base = (d.get("paths") or {}).get(cat["id"])
    if not base:
        return err("Dysk %s nie ma folderu dla kategorii „%s” – uzupełnij go w Ustawieniach." % (d["label"], cat["label"]))
    adv = data.get("advanced") or {}
    ids = {}
    if adv.get("use_id") and adv.get("tmdb_id"):
        ids["tmdb"] = adv.get("tmdb_id")
    try:
        if cat["kind"] == "tv":
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
        return err("Nieznana akcja.", 404)
    try:
        actions[action](job_id)
    except ValueError as e:
        return err(str(e))
    except Exception as e:
        return err("Błąd silnika pobierania: %s" % e, 500)
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
                   tmdb_api_key=cfg.get("tmdb_api_key", ""),
                   plex_servers=cfg.get("plex_servers", []),
                   plex_autodiscover=cfg.get("plex_autodiscover", True),
                   thumbs_mode=cfg.get("thumbs_mode", "online"),
                   pillow=fm.Image is not None,
                   port=cfg.get("port", 8800))


def _abs_path(value, what):
    value = (value or "").strip()
    if not value:
        return ""
    if not value.startswith("/") or ".." in value.split("/"):
        raise ValueError("Ścieżka „%s” musi być bezwzględna (zaczynać się od /)." % what)
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
                raise ValueError("Każda kategoria musi mieć nazwę.")
            cid = (raw.get("id") or "").strip()
            if not re.match(r"^[a-z0-9-]{1,24}$", cid):
                cid = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")[:24] or uuid.uuid4().hex[:6]
            while cid in seen:
                cid = cid[:20] + "-" + uuid.uuid4().hex[:3]
            seen.add(cid)
            cats.append({"id": cid, "label": label[:40], "kind": "tv" if raw.get("kind") == "tv" else "movie",
                         "folder": naming.sanitize(raw.get("folder") or "")[:60]})
        if not cats:
            raise ValueError("Musi zostać co najmniej jedna kategoria.")
        # mapowanie identyfikatorów nowych kategorii (klient używa tymczasowych „new-…”)
        idmap = {}
        for raw, c in zip(data.get("categories") or [], cats):
            idmap[(raw.get("id") or raw.get("tmp") or "").strip()] = c["id"]
        disks = []
        for raw in data.get("disks") or []:
            d = {k: (raw.get(k) or "").strip() for k in ("id", "label", "subtitle")}
            if not d["label"]:
                raise ValueError("Każdy dysk musi mieć nazwę.")
            d["mount"] = _abs_path(raw.get("mount"), "punkt montowania – " + d["label"])
            if not d["mount"]:
                raise ValueError("Podaj punkt montowania dla dysku %s." % d["label"])
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
        if not disks:
            raise ValueError("Musi zostać co najmniej jeden dysk.")
        servers = []
        for raw in data.get("plex_servers") or []:
            host = (raw.get("host") or "").strip()
            if not host:
                continue
            if not re.match(r"^[A-Za-z0-9.\-:]+$", host):
                raise ValueError("Nieprawidłowy adres serwera Plex: %s" % host)
            port = int(raw.get("port") or 32400)
            if not 1 <= port <= 65535:
                raise ValueError("Nieprawidłowy port serwera Plex.")
            servers.append({"id": raw.get("id") or uuid.uuid4().hex[:6],
                            "name": (raw.get("name") or host).strip()[:40], "host": host, "port": port})
        conns = max(1, min(16, int(data.get("connections_per_file", 6))))
        conc = max(1, min(10, int(data.get("max_concurrent", 2))))
        speed = max(0.0, float(data.get("max_speed_mbps") or 0))
    except (TypeError, ValueError) as e:
        return err(str(e) if isinstance(e, ValueError) and str(e) else "Nieprawidłowe wartości.")
    tmdb_key = re.sub(r"\s+", "", data.get("tmdb_api_key") or "")
    mode = data.get("thumbs_mode") if data.get("thumbs_mode") in ("online", "local", "off") else "online"
    config.update(note=data.get("note") or "Zapis ustawień",
                  categories=cats, disks=disks, connections_per_file=conns, max_concurrent=conc,
                  max_speed_mbps=speed, require_mount=bool(data.get("require_mount", True)),
                  tmdb_api_key=tmdb_key, plex_servers=servers,
                  plex_autodiscover=bool(data.get("plex_autodiscover", True)), thumbs_mode=mode)
    manager.apply_settings()
    plexservers.monitor.refresh()
    return jsonify(ok=True)


@app.route("/api/backups")
@login_required
def api_backups():
    return jsonify(backups=config.describe_backups(), keep_days=config.BACKUP_DAYS)


@app.route("/api/backups/restore", methods=["POST"])
@login_required
def api_backup_restore():
    try:
        config.restore((request.get_json(silent=True) or {}).get("name", ""))
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
        return err("Błąd dysku: %s" % e)


@app.route("/api/fm/list")
@login_required
def api_fm_list():
    a = request.args
    return fm_call(fm.list_items, a.get("disk", ""), a.get("cat", ""), manager.busy_paths())


@app.route("/api/fm/plan", methods=["POST"])
@login_required
def api_fm_plan():
    d = request.get_json(silent=True) or {}
    return fm_call(fm.plan_move, d.get("src_disk"), d.get("src_cat"), d.get("names") or [],
                   d.get("dst_disk"), d.get("dst_cat"), manager.busy_paths())


@app.route("/api/fm/move", methods=["POST"])
@login_required
def api_fm_move():
    d = request.get_json(silent=True) or {}

    def run():
        plan = fm.plan_move(d.get("src_disk"), d.get("src_cat"), d.get("names") or [],
                            d.get("dst_disk"), d.get("dst_cat"), manager.busy_paths())
        op = fm.ops.move(plan)
        return {"op": op["id"]}
    return fm_call(run)


@app.route("/api/fm/delete", methods=["POST"])
@login_required
def api_fm_delete():
    d = request.get_json(silent=True) or {}
    if d.get("confirm") != "DELETE":
        return err("Brak potwierdzenia usunięcia.")
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
        return err("Obecne hasło jest nieprawidłowe.")
    new = data.get("new", "")
    if len(new) < 6:
        return err("Nowe hasło musi mieć co najmniej 6 znaków.")
    username = (data.get("username") or cfg["username"]).strip() or cfg["username"]
    config.update(note="Zmiana loginu/hasła", username=username, password_hash=generate_password_hash(new))
    session["user"] = username
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


def _api_version():
    def git(*args):
        return subprocess.run(["git", "-C", BASE_DIR] + list(args), capture_output=True,
                              text=True, timeout=25)
    try:
        if git("rev-parse", "--is-inside-work-tree").returncode != 0:
            return jsonify(version=VERSION, available=None, message="To nie jest repozytorium git.")
        fetch = git("fetch", "--quiet")
        if fetch.returncode != 0:
            return jsonify(version=VERSION, available=None,
                           message="Nie udało się połączyć z GitHubem.")
        behind = git("rev-list", "--count", "HEAD..@{u}").stdout.strip() or "0"
        commit = git("log", "-1", "--format=%h, %cd", "--date=short").stdout.strip()
        n = int(behind) if behind.isdigit() else 0
        return jsonify(version=VERSION, commit=commit, available=n > 0, behind=n,
                       message=("Dostępna aktualizacja (%d zmian). Uruchom ./update.sh na Raspberry Pi." % n)
                       if n else "Masz najnowszą wersję.")
    except Exception as e:
        return jsonify(version=VERSION, available=None, message=str(e))


# ---------------------------------------------------------------- start
def set_password():
    config.load()
    cfg = config.get()
    print("Ustawianie danych logowania do Plex Downloader")
    user = input("Login [%s]: " % cfg.get("username", "admin")).strip() or cfg.get("username", "admin")
    while True:
        p1 = getpass.getpass("Hasło (min. 6 znaków): ")
        p2 = getpass.getpass("Powtórz hasło: ")
        if len(p1) < 6:
            print("Za krótkie.")
        elif p1 != p2:
            print("Hasła się różnią.")
        else:
            break
    config.update(note="Ustawienie hasła (konsola)", username=user, password_hash=generate_password_hash(p1))
    print("Zapisano. Login: %s" % user)


def check_folders():
    """Raport dla setup.sh: czy foldery kategorii istnieją i można w nich zapisywać."""
    cfg = config.load()
    cats = {c["id"]: c["label"] for c in cfg.get("categories", [])}
    for d in cfg.get("disks", []):
        for cid, label in cats.items():
            p = (d.get("paths") or {}).get(cid)
            if not p:
                print("  \033[90m– %-18s %-12s (brak folderu – opcjonalne)\033[0m" % (d["label"], label))
            elif not os.path.isdir(p):
                print("  \033[33m! %-18s %-12s brak folderu: %s\033[0m" % (d["label"], label, p))
            elif not os.access(p, os.W_OK):
                print("  \033[33m! %-18s %-12s brak prawa zapisu: %s\033[0m" % (d["label"], label, p))
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
        sys.exit("Plex Downloader już działa (blokada %s.lock)." % DB_PATH)


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
    parser.add_argument("--set-password", action="store_true", help="ustaw login i hasło")
    parser.add_argument("--check-folders", action="store_true", help="sprawdź foldery bibliotek")
    args = parser.parse_args()
    if args.set_password:
        set_password()
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
        log.warning("Brak pakietu waitress – używam serwera developerskiego Flask.")
        app.run(host=cfg["host"], port=int(cfg["port"]), threaded=True)


if __name__ == "__main__":
    main()
