"""Silnik pobierania: sterowanie aria2c przez JSON-RPC, kolejka, finalizacja i sprzątanie."""
import errno
import json
import logging
import os
import shutil
import sqlite3
import subprocess
import threading
import time
import urllib.error
import urllib.request
import uuid
from urllib.parse import urlparse

import actlog
import config
from i18n import _
import naming

log = logging.getLogger("plexdl")

TMP_DIRNAME = ".plexdl-tmp"
ACTIVE = ("queued", "downloading", "paused")
UA = "Mozilla/5.0 (X11; Linux aarch64) PlexDownloader/1.0"

CONTENT_TYPES = {
    "video/mp4": ".mp4", "video/x-matroska": ".mkv", "video/x-msvideo": ".avi",
    "video/avi": ".avi", "video/webm": ".webm", "video/quicktime": ".mov",
    "video/x-m4v": ".m4v", "video/mp2t": ".ts", "video/mpeg": ".mpg",
}


class Aria2Error(Exception):
    pass


class Aria2:
    """Minimalny klient JSON-RPC aria2 (tylko localhost, bez proxy)."""

    def __init__(self, port, secret):
        self.url = "http://127.0.0.1:%d/jsonrpc" % int(port)
        self.secret = secret
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def call(self, method, *params):
        payload = {"jsonrpc": "2.0", "id": "plexdl", "method": "aria2." + method,
                   "params": ["token:" + self.secret] + list(params)}
        req = urllib.request.Request(self.url, data=json.dumps(payload).encode(),
                                     headers={"Content-Type": "application/json"})
        try:
            with self._opener.open(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            try:
                data = json.loads(e.read().decode())
            except ValueError:
                raise Aria2Error("HTTP %s" % e.code)
        if "error" in data:
            raise Aria2Error(data["error"].get("message", "aria2 error"))
        return data.get("result")

    def alive(self):
        try:
            self.call("getVersion")
            return True
        except Exception:
            return False


def _human_error(msg):
    m = (msg or "").lower()
    if "404" in m or "not found" in m:
        return _("The server returned 404 – the link has expired or is wrong.")
    if "403" in m or "forbidden" in m:
        return _("Access denied (403) – the link may have expired.")
    if "no space" in m or "disk" in m and "full" in m:
        return _("No space left on the disk.")
    if "timeout" in m or "timed out" in m:
        return _("Connection to the server timed out.")
    if "resolve" in m or "name or service" in m:
        return _("Cannot resolve the server name (DNS).")
    return msg or _("Unknown download error.")


def probe(url, timeout=12):
    """Sprawdza link: nazwę pliku, rozmiar, obsługę wznawiania (Range)."""
    headers = {"User-Agent": UA}
    resp = None
    try:
        resp = urllib.request.urlopen(urllib.request.Request(url, method="HEAD", headers=headers),
                                      timeout=timeout)
    except urllib.error.HTTPError as e:
        if e.code not in (400, 403, 405, 501):
            raise
    if resp is None:  # serwer nie lubi HEAD – próbujemy GET z Range na 1 bajt
        h = dict(headers, Range="bytes=0-0")
        resp = urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=timeout)
    with resp:
        hdr = resp.headers
        final_url = resp.geturl()
        size = None
        cr = hdr.get("Content-Range")
        if cr and "/" in cr:
            tail = cr.rsplit("/", 1)[1].strip()
            size = int(tail) if tail.isdigit() else None
        elif hdr.get("Content-Length", "").isdigit():
            size = int(hdr["Content-Length"])
        resumable = hdr.get("Accept-Ranges", "").lower() == "bytes" or bool(cr)
        ctype = (hdr.get("Content-Type") or "").split(";")[0].strip().lower()
        # strona WWW zamiast pliku (logowanie, weryfikacja wieku, wygasły link) – zwykle po przekierowaniu
        page = ctype in ("text/html", "application/xhtml+xml")
        from_final = naming.filename_from_url(final_url)
        from_url = naming.filename_from_url(url)
        # nazwa z adresu po przekierowaniu tylko wtedy, gdy wygląda na plik wideo
        # (inaczej np. „L2Rsb2Fk…” – zakodowany adres strony logowania)
        if page or not naming.split_ext(from_final)[1]:
            from_final = ""
        fname = (("" if page else naming.filename_from_content_disposition(hdr.get("Content-Disposition")))
                 or from_final or from_url)
    _, ext = naming.split_ext(fname)
    if not ext:
        ext = CONTENT_TYPES.get(ctype, "")
    return {"filename": fname, "size": None if page else size, "resumable": False if page else resumable,
            "content_type": ctype, "ext": ext, "page": page}


def disk_status(d):
    """Stan dysku: zamontowany?, wolne/całkowite miejsce, czy foldery istnieją."""
    cfg = config.get()
    mount = d.get("mount") or ""
    paths = d.get("paths") or {}
    info = {"id": d.get("id"), "label": d.get("label"), "subtitle": d.get("subtitle", ""),
            "mount": mount, "paths": paths,
            "folders": {cid: os.path.isdir(p) for cid, p in paths.items()},
            "mounted": False, "free": None, "total": None, "ok": False, "problem": ""}
    if not mount or not os.path.isdir(mount):
        info["problem"] = _("Mount point not found")
        return info
    info["mounted"] = os.path.ismount(mount)
    if cfg.get("require_mount", True) and not info["mounted"]:
        info["problem"] = _("Disk not mounted")
        return info
    try:
        u = shutil.disk_usage(mount)
        info["free"], info["total"] = u.free, u.total
    except OSError as e:
        info["problem"] = str(e)
        return info
    info["ok"] = True
    return info


class Manager:
    def __init__(self, db_path, aria2_bin=None):
        self.db_path = db_path
        self.aria2_bin = aria2_bin or os.environ.get("PLEXDL_ARIA2C") or shutil.which("aria2c") or "aria2c"
        self.lock = threading.RLock()
        self.jobs = {}
        self.proc = None
        self.aria2 = None
        self.engine_ok = False
        self.engine_error = ""
        self._stop = threading.Event()
        self._db = sqlite3.connect(db_path, check_same_thread=False)
        self._db.execute("CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, created REAL, data TEXT)")
        self._db.commit()

    # ---------- persistencja ----------
    def _save(self, job):
        with self.lock:
            self._db.execute("INSERT OR REPLACE INTO jobs (id, created, data) VALUES (?, ?, ?)",
                             (job["id"], job["created"], json.dumps(job)))
            self._db.commit()

    def _delete(self, job_id):
        with self.lock:
            self.jobs.pop(job_id, None)
            self._db.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
            self._db.commit()

    def _load(self):
        for (data,) in self._db.execute("SELECT data FROM jobs ORDER BY created"):
            job = json.loads(data)
            self.jobs[job["id"]] = job

    # ---------- aria2 ----------
    def _start_aria2(self):
        cfg = config.get()
        self.aria2 = Aria2(cfg["aria2_rpc_port"], cfg["aria2_secret"])
        if self.aria2.alive():
            return
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
        limit = int(float(cfg.get("max_speed_mbps") or 0) * 1024 * 1024)
        args = [
            self.aria2_bin, "--enable-rpc", "--rpc-listen-all=false",
            "--rpc-listen-port=%d" % int(cfg["aria2_rpc_port"]),
            "--rpc-secret=%s" % cfg["aria2_secret"],
            "--max-concurrent-downloads=%d" % int(cfg.get("max_concurrent", 2)),
            "--max-overall-download-limit=%d" % limit,
            "--continue=true", "--auto-file-renaming=false", "--allow-overwrite=true",
            "--file-allocation=none", "--disk-cache=32M",
            "--max-tries=10", "--retry-wait=5", "--timeout=60", "--connect-timeout=30",
            "--min-split-size=1M", "--user-agent=" + UA,
            "--console-log-level=warn", "--summary-interval=0", "--quiet=true",
        ]
        log.info("Uruchamiam aria2c (%s)", self.aria2_bin)
        self.proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                     stdin=subprocess.DEVNULL)
        for _ in range(50):
            if self.aria2.alive():
                return
            if self.proc.poll() is not None:
                break
            time.sleep(0.1)
        raise RuntimeError(_("Could not start aria2c – is it installed?"))

    def apply_settings(self):
        cfg = config.get()
        if not self.engine_ok:
            return
        limit = int(float(cfg.get("max_speed_mbps") or 0) * 1024 * 1024)
        try:
            self.aria2.call("changeGlobalOption", {
                "max-concurrent-downloads": str(int(cfg.get("max_concurrent", 2))),
                "max-overall-download-limit": str(limit)})
        except Exception as e:
            log.warning("Could not change aria2 options: %s", e)

    def _aria_add(self, job, paused=False):
        n = max(1, min(16, int(config.get().get("connections_per_file", 6))))
        os.makedirs(job["tmp_dir"], exist_ok=True)
        opts = {"dir": job["tmp_dir"], "out": job["filename"], "split": str(n),
                "max-connection-per-server": str(n), "min-split-size": "1M",
                "continue": "true", "pause": "true" if paused else "false"}
        job["gid"] = self.aria2.call("addUri", [job["url"]], opts)
        job["max_connections"] = n

    # ---------- start / stop ----------
    def start(self):
        self._load()
        try:
            self._start_aria2()
            self.engine_ok = True
        except Exception as e:
            self.engine_ok = False
            self.engine_error = str(e)
            log.error("%s", e)
        self._restore()
        threading.Thread(target=self._poll_loop, name="plexdl-poll", daemon=True).start()

    def stop(self):
        self._stop.set()
        if self.proc and self.proc.poll() is None:
            try:
                self.aria2.call("saveSession")
            except Exception:
                pass
            self.proc.terminate()

    def _restore(self):
        """Po restarcie wznawia przerwane pobierania (aria2 kontynuuje z pliku .aria2)."""
        with self.lock:
            for job in list(self.jobs.values()):
                st = job["status"]
                if st == "cancelling":
                    self._cleanup_tmp(job)
                    self._delete(job["id"])
                elif st == "finalizing":
                    src = os.path.join(job["tmp_dir"], job["filename"])
                    if os.path.exists(src) and not os.path.exists(src + ".aria2"):
                        threading.Thread(target=self._finalize, args=(job,), daemon=True).start()
                    else:
                        self._readd(job, paused=False)
                elif st in ACTIVE:
                    self._readd(job, paused=(st == "paused"))

    def _readd(self, job, paused):
        if not self.engine_ok:
            return
        if job.get("gid"):
            try:  # aria2 nadal prowadzi to zadanie (np. przeżyło restart aplikacji) – nie dublujemy
                self.aria2.call("tellStatus", job["gid"], ["status"])
                return
            except Exception:
                job["gid"] = None
        try:
            self._aria_add(job, paused=paused)
            job["status"] = "paused" if paused else "queued"
        except Exception as e:
            job.update(status="error", error=_("Could not resume: %s") % e)
        self._save(job)

    # ---------- API zadań ----------
    def add(self, url, disk_id, category_id, folder, filename, kind, display, size=None):
        if not self.engine_ok:
            raise ValueError(_("The download engine (aria2c) is not running: %s") % self.engine_error)
        d = config.disk(disk_id)
        if not d:
            raise ValueError(_("Unknown target disk."))
        st = disk_status(d)
        if not st["ok"]:
            raise ValueError("%s: %s" % (d.get("label"), st["problem"]))
        cat = config.category(category_id) or {}
        base = (d.get("paths") or {}).get(category_id)
        if not base:
            raise ValueError(_("Disk %s has no folder for the category “%s”.") % (d["label"], cat.get("label", category_id)))
        if not os.path.isdir(base):
            raise ValueError(_("Library folder does not exist: %s") % base)
        target = os.path.join(folder, filename)
        if os.path.exists(target):
            raise ValueError(_("This file already exists: %s") % target)
        with self.lock:
            for j in self.jobs.values():
                if j["status"] not in ("done", "error") and os.path.join(j["folder"], j["filename"]) == target:
                    raise ValueError(_("This file is already in the queue."))
            reserved = sum(max(0, (j.get("total") or 0) - (j.get("completed") or 0))
                           for j in self.jobs.values()
                           if j["disk_id"] == disk_id and j["status"] in ACTIVE)
        if size and st["free"] is not None and size + reserved + 200 * 1024 * 1024 > st["free"]:
            raise ValueError(_("Not enough space on %s (needed %.1f GB, free %.1f GB).")
                             % (d["label"], (size + reserved) / 1e9, st["free"] / 1e9))
        job_id = uuid.uuid4().hex[:12]
        tmp_root = os.path.join(os.path.dirname(base.rstrip("/")), TMP_DIRNAME)
        job = {
            "id": job_id, "url": url, "kind": kind, "disk_id": disk_id, "disk_label": d["label"],
            "category": category_id, "category_label": cat.get("label", ""),
            "folder": folder, "filename": filename, "display": display,
            "tmp_dir": os.path.join(tmp_root, job_id), "gid": None,
            "status": "queued", "total": size or 0, "completed": 0, "speed": 0,
            "connections": 0, "max_connections": 0, "error": "",
            "created": time.time(), "finished": None,
        }
        try:
            self._aria_add(job)
        except Exception as e:
            self._cleanup_tmp(job)
            raise ValueError(_("aria2 rejected the task: %s") % e)
        with self.lock:
            self.jobs[job_id] = job
            self._save(job)
        actlog.write("DOWNLOAD", "%s → %s / %s (%s)" % (filename, d["label"], cat.get("label", ""), urlparse(url).netloc))
        return job

    def busy_paths(self):
        """Foldery, do których trwa pobieranie – menedżer plików ich nie rusza."""
        with self.lock:
            return [j["folder"] for j in self.jobs.values()
                    if j["status"] not in ("done", "error")]

    def list(self):
        with self.lock:
            jobs = [dict(j) for j in self.jobs.values()]
        order = {"downloading": 0, "finalizing": 0, "queued": 1, "paused": 2, "cancelling": 3,
                 "error": 4, "done": 5}
        jobs.sort(key=lambda j: (order.get(j["status"], 9),
                                 -(j.get("finished") or j["created"]) if j["status"] in ("done", "error")
                                 else j["created"]))
        for j in jobs:
            remaining = max(0, (j["total"] or 0) - (j["completed"] or 0))
            j["eta"] = int(remaining / j["speed"]) if j.get("speed") else None
            j["percent"] = round(100.0 * j["completed"] / j["total"], 1) if j.get("total") else 0
        return jobs

    def _get(self, job_id):
        job = self.jobs.get(job_id)
        if not job:
            raise ValueError(_("No such task."))
        return job

    def pause(self, job_id):
        with self.lock:
            job = self._get(job_id)
            if job["status"] in ("queued", "downloading") and job["gid"]:
                self.aria2.call("pause", job["gid"])
                job["status"] = "paused"
                job["speed"] = 0
                self._save(job)

    def resume(self, job_id):
        with self.lock:
            job = self._get(job_id)
            if job["status"] == "paused" and job["gid"]:
                try:
                    self.aria2.call("unpause", job["gid"])
                except Aria2Error:
                    self._aria_add(job)
                job["status"] = "queued"
                self._save(job)

    def cancel(self, job_id):
        with self.lock:
            job = self._get(job_id)
            if job["status"] in ("done", "finalizing"):
                raise ValueError(_("This task can no longer be cancelled."))
            if job["status"] == "error" or not job["gid"]:
                self._cleanup_tmp(job)
                self._delete(job_id)
                return
            job["status"] = "cancelling"
            self._save(job)
            try:
                self.aria2.call("forceRemove", job["gid"])
            except Aria2Error:
                pass  # zadanie mogło się właśnie zakończyć błędem – poll i tak posprząta

    def retry(self, job_id):
        with self.lock:
            job = self._get(job_id)
            if job["status"] != "error":
                raise ValueError(_("Only a failed task can be retried."))
            if os.path.exists(os.path.join(job["folder"], job["filename"])):
                raise ValueError(_("The target file already exists."))
            job.update(error="", completed=0, speed=0, finished=None)
            self._aria_add(job)
            job["status"] = "queued"
            self._save(job)

    def remove(self, job_id):
        with self.lock:
            job = self._get(job_id)
            if job["status"] not in ("done", "error"):
                raise ValueError("Najpierw anuluj pobieranie.")
            self._cleanup_tmp(job)
            self._delete(job_id)

    def clear_finished(self):
        with self.lock:
            for job in list(self.jobs.values()):
                if job["status"] == "done":
                    self._delete(job["id"])

    # ---------- pętla monitorująca ----------
    def _poll_loop(self):
        while not self._stop.is_set():
            try:
                self._poll()
            except Exception:
                log.exception("Monitor loop error")
            self._stop.wait(1.0)

    def _poll(self):
        if not self.engine_ok or not self.aria2.alive():
            # aria2 padło lub nie wystartowało – próbujemy podnieść i wznowić zadania
            try:
                self._start_aria2()
                self.engine_ok = True
                self.engine_error = ""
                with self.lock:
                    for job in self.jobs.values():
                        if job["status"] in ACTIVE + ("cancelling",):
                            job["gid"] = None
                self._restore()
            except Exception as e:
                self.engine_ok = False
                self.engine_error = str(e)
                return
        keys = ["status", "totalLength", "completedLength", "downloadSpeed", "connections",
                "errorCode", "errorMessage"]
        with self.lock:
            jobs = [j for j in self.jobs.values()
                    if j["status"] in ACTIVE + ("cancelling",) and j.get("gid")]
        for job in jobs:
            try:
                st = self.aria2.call("tellStatus", job["gid"], keys)
            except Aria2Error as e:
                if "not found" in str(e).lower():
                    if job["status"] == "cancelling":
                        self._finish_cancel(job)
                    else:
                        with self.lock:
                            self._readd(job, paused=(job["status"] == "paused"))
                continue
            self._apply_status(job, st)

    def _apply_status(self, job, st):
        a = st.get("status")
        with self.lock:
            job["total"] = int(st.get("totalLength") or 0) or job["total"]
            job["completed"] = int(st.get("completedLength") or 0)
            job["speed"] = int(st.get("downloadSpeed") or 0)
            job["connections"] = int(st.get("connections") or 0)
            if job["status"] == "cancelling":
                if a in ("removed", "error", "complete"):
                    self._finish_cancel(job)
                return
            prev = job["status"]
            if a == "active":
                job["status"] = "downloading"
            elif a == "waiting":
                job["status"] = "queued"
            elif a == "paused":
                job["status"] = "paused"
                job["speed"] = 0
            elif a == "complete":
                job["status"] = "finalizing"
                job["speed"] = 0
                job["completed"] = job["total"]
                self._save(job)
                threading.Thread(target=self._finalize, args=(job,), daemon=True).start()
                return
            elif a == "error":
                self._fail(job, _human_error(st.get("errorMessage")))
                return
            elif a == "removed":  # usunięte spoza aplikacji
                self._finish_cancel(job)
                return
            if job["status"] != prev:
                self._save(job)

    def _fail(self, job, message):
        log.warning("Download error %s: %s", job["filename"], message)
        self._aria_forget(job)
        self._cleanup_tmp(job)
        job.update(status="error", error=message, speed=0, finished=time.time())
        self._save(job)
        actlog.write("FAILED", "%s: %s" % (job["filename"], message))

    def _finish_cancel(self, job):
        actlog.write("CANCEL", job["filename"])
        self._aria_forget(job)
        self._cleanup_tmp(job)
        self._delete(job["id"])

    def _aria_forget(self, job):
        if job.get("gid"):
            try:
                self.aria2.call("removeDownloadResult", job["gid"])
            except Exception:
                pass
        job["gid"] = None

    @staticmethod
    def _cleanup_tmp(job):
        tmp = job.get("tmp_dir")
        if tmp and os.path.basename(os.path.dirname(tmp)) == TMP_DIRNAME:
            shutil.rmtree(tmp, ignore_errors=True)
            try:
                os.rmdir(os.path.dirname(tmp))  # tylko jeśli pusty
            except OSError:
                pass

    def _finalize(self, job):
        """Przenosi gotowy plik z folderu tymczasowego do biblioteki (atomowo, ten sam dysk)."""
        src = os.path.join(job["tmp_dir"], job["filename"])
        dst_dir = job["folder"]
        dst = os.path.join(dst_dir, job["filename"])
        created = []
        try:
            if not os.path.exists(src):
                raise RuntimeError(_("Downloaded file not found."))
            if os.path.exists(dst):
                raise RuntimeError(_("The target file already exists."))
            path = dst_dir
            while path and not os.path.isdir(path):
                created.append(path)
                path = os.path.dirname(path)
            os.makedirs(dst_dir, exist_ok=True)
            try:
                os.rename(src, dst)
            except OSError as e:
                if e.errno != errno.EXDEV:
                    raise
                part = dst + ".part"  # inny system plików: kopia + atomowa zmiana nazwy
                try:
                    shutil.copyfile(src, part)
                    os.rename(part, dst)
                except Exception:
                    if os.path.exists(part):
                        os.remove(part)
                    raise
        except Exception as e:
            log.exception("Finalization failed")
            for p in created:  # usuwamy tylko foldery utworzone przez nas i tylko puste
                try:
                    os.rmdir(p)
                except OSError:
                    pass
            with self.lock:
                self._fail(job, _("Could not move the file: %s") % e)
            return
        for p in created + [dst]:
            try:
                os.chmod(p, 0o775 if p != dst else 0o664)
            except OSError:
                pass
        with self.lock:
            self._aria_forget(job)
            self._cleanup_tmp(job)
            job.update(status="done", finished=time.time(), speed=0, error="")
            self._save(job)
        actlog.write("DONE", "%s → %s (%.2f GB)" % (job["filename"], dst_dir, (job.get("total") or 0) / 1e9))
        log.info("Finished: %s", dst)
