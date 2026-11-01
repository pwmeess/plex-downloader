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

from flask import Flask, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

import config
import naming
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
    return render_template("index.html", version=VERSION, user=session.get("user"))


# ---------------------------------------------------------------- API
def err(message, code=400):
    return jsonify(error=message), code


def disks_payload():
    return [disk_status(d) for d in config.get().get("disks", [])]


@app.route("/api/state")
@login_required
def api_state():
    return jsonify(jobs=manager.list(), disks=disks_payload(),
                   engine={"ok": manager.engine_ok, "error": manager.engine_error},
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
    if not info["ext"]:
        info["ext"] = info["guess"]["ext"]
    return jsonify(info)


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
    kind = "tv" if data.get("kind") == "tv" else "movie"
    try:
        if kind == "tv":
            folder, filename = naming.tv_target(d["tv"], data.get("show"), data.get("season"),
                                                data.get("episode"), data.get("episode_title"), ext)
        else:
            folder, filename = naming.movie_target(d["movies"], data.get("name"), ext)
        size = data.get("size")
        size = int(size) if isinstance(size, (int, float)) and size > 0 else None
        job = manager.add(url, d["id"], folder, filename, kind,
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
    return jsonify(disks=cfg.get("disks", []), username=cfg.get("username"),
                   connections_per_file=cfg.get("connections_per_file"),
                   max_concurrent=cfg.get("max_concurrent"),
                   max_speed_mbps=cfg.get("max_speed_mbps"),
                   require_mount=cfg.get("require_mount"))


@app.route("/api/settings", methods=["POST"])
@login_required
def api_settings_post():
    data = request.get_json(silent=True) or {}
    disks = []
    for raw in data.get("disks") or []:
        d = {k: (raw.get(k) or "").strip() for k in ("id", "label", "subtitle", "mount", "movies", "tv")}
        if not d["label"]:
            return err("Każdy dysk musi mieć nazwę.")
        for k in ("mount", "movies", "tv"):
            if not d[k].startswith("/") or ".." in d[k].split("/"):
                return err("Ścieżka „%s” dla %s musi być bezwzględna." % (k, d["label"]))
            d[k] = d[k].rstrip("/") or "/"
        if not d["id"] or not re.match(r"^[a-z0-9_-]{1,32}$", d["id"]):
            d["id"] = uuid.uuid4().hex[:8]
        disks.append(d)
    if not disks:
        return err("Musi zostać co najmniej jeden dysk.")
    try:
        conns = max(1, min(16, int(data.get("connections_per_file", 6))))
        conc = max(1, min(10, int(data.get("max_concurrent", 2))))
        speed = max(0.0, float(data.get("max_speed_mbps") or 0))
    except (TypeError, ValueError):
        return err("Nieprawidłowe wartości liczbowe.")
    config.update(disks=disks, connections_per_file=conns, max_concurrent=conc,
                  max_speed_mbps=speed, require_mount=bool(data.get("require_mount", True)))
    manager.apply_settings()
    return jsonify(ok=True)


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
    config.update(username=username, password_hash=generate_password_hash(new))
    session["user"] = username
    return jsonify(ok=True)


@app.route("/api/version")
@login_required
def api_version():
    """Sprawdza, czy w repozytorium GitHub są nowsze commity."""
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
    config.update(username=user, password_hash=generate_password_hash(p1))
    print("Zapisano. Login: %s" % user)


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
    return app


def main():
    parser = argparse.ArgumentParser(description="Plex Downloader")
    parser.add_argument("--set-password", action="store_true", help="ustaw login i hasło")
    args = parser.parse_args()
    if args.set_password:
        set_password()
        return
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    create_app()
    cfg = config.get()

    def shutdown(*_):
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
