"""Menedżer plików: przeglądanie bibliotek, przenoszenie między folderami/dyskami, usuwanie, miniatury.

Zasady bezpieczeństwa:
- operujemy wyłącznie na bezpośrednich elementach folderów kategorii skonfigurowanych w Ustawieniach,
- nazwy nie mogą zawierać ścieżek; ścieżka po rozwiązaniu musi leżeć w folderze kategorii,
- przenoszenie między dyskami: kopia do folderu tymczasowego → weryfikacja SHA-256 →
  zmiana nazwy na docelową → dopiero wtedy usunięcie oryginału,
- elementy, do których trwa pobieranie, są zablokowane.
"""
import errno
import hashlib
import io
import logging
import os
import shutil
import threading
import time
import uuid

import config
import movieinfo
import naming
from downloader import TMP_DIRNAME, disk_status

log = logging.getLogger("plexdl")
CHUNK = 4 * 1024 * 1024
THUMB_EXTS = (".thumb.png", ".thumb.jpg")
SKIP = {"@eaDir", "$RECYCLE.BIN", "System Volume Information", "lost+found", "#recycle", ".Trash-1000"}
SIZE_TTL = 120

try:  # Pillow jest opcjonalny – bez niego miniatury zapisują się jako .thumb.jpg
    from PIL import Image
except Exception:  # pragma: no cover
    Image = None


class FMError(Exception):
    pass


# ------------------------------------------------------------------ ścieżki
def location(disk_id, cat_id, need_ok=True):
    d = config.disk(disk_id)
    if not d:
        raise FMError("Nieznany dysk.")
    cat = config.category(cat_id)
    if not cat:
        raise FMError("Nieznana kategoria.")
    base = (d.get("paths") or {}).get(cat_id)
    if not base:
        raise FMError("Dysk %s nie ma folderu dla kategorii „%s”." % (d["label"], cat["label"]))
    if need_ok:
        st = disk_status(d)
        if not st["ok"]:
            raise FMError("%s: %s" % (d["label"], st["problem"]))
    if not os.path.isdir(base):
        raise FMError("Folder nie istnieje: %s" % base)
    return d, cat, base


def item_path(base, name):
    if (not name or name in (".", "..") or "/" in name or "\\" in name or "\0" in name
            or name.startswith(".")):
        raise FMError("Nieprawidłowa nazwa: %r" % name)
    path = os.path.join(base, name)
    if os.path.dirname(os.path.realpath(path)) != os.path.realpath(base):
        raise FMError("Element spoza folderu biblioteki: %s" % name)
    if not os.path.lexists(path):
        raise FMError("Nie znaleziono: %s" % name)
    return path


def tmp_root(base):
    return os.path.join(os.path.dirname(base.rstrip("/")), TMP_DIRNAME)


def is_busy(path, busy):
    rp = os.path.realpath(path)
    for b in busy:
        rb = os.path.realpath(b)
        if rb == rp or rb.startswith(rp + os.sep):
            return True
    return False


# ------------------------------------------------------------------ lista
_size_cache = {}


def tree_size(path):
    now = time.time()
    hit = _size_cache.get(path)
    try:
        mtime = os.stat(path).st_mtime
    except OSError:
        return 0, 0
    if hit and hit[0] == mtime and now - hit[1] < SIZE_TTL:
        return hit[2], hit[3]
    total = videos = 0
    if os.path.isfile(path):
        total, videos = os.path.getsize(path), 1
    else:
        for root, dirs, files in os.walk(path):
            dirs[:] = [x for x in dirs if not x.startswith(".") and x not in SKIP]
            for f in files:
                if f.startswith("."):
                    continue
                try:
                    total += os.path.getsize(os.path.join(root, f))
                except OSError:
                    pass
                if naming.split_ext(f)[1]:
                    videos += 1
    _size_cache[path] = (mtime, now, total, videos)
    return total, videos


def thumb_base(base, name, is_dir):
    if is_dir:
        return os.path.join(base, name, name)
    return os.path.join(base, naming.split_ext(name)[0] or name)


def find_thumb(base, name, is_dir):
    stem = thumb_base(base, name, is_dir)
    for ext in THUMB_EXTS:
        if os.path.isfile(stem + ext):
            return stem + ext
    return None


def list_items(disk_id, cat_id, busy=()):
    d, cat, base = location(disk_id, cat_id)
    items = []
    with os.scandir(base) as it:
        for e in it:
            if e.name.startswith(".") or e.name in SKIP:
                continue
            try:
                is_dir = e.is_dir()
            except OSError:
                continue
            if not is_dir and not naming.split_ext(e.name)[1]:
                continue  # luźne pliki inne niż wideo (np. .nfo) pomijamy
            label = e.name if is_dir else naming.split_ext(e.name)[0]
            p = naming.parse_name(label)
            size, videos = tree_size(e.path)
            th = find_thumb(base, e.name, is_dir)
            items.append({
                "name": e.name, "is_dir": is_dir, "title": p["title"] or label, "year": p["year"],
                "edition": p["edition"], "tmdb": p["tmdb"], "size": size, "videos": videos,
                "thumb": bool(th), "thumb_v": int(os.path.getmtime(th)) if th else 0,
                "busy": is_busy(e.path, busy),
            })
    items.sort(key=lambda i: (i["title"].lower(), i["year"] or 0))
    st = disk_status(d)
    return {"disk": d["id"], "disk_label": d["label"], "category": cat["id"], "kind": cat["kind"],
            "category_label": cat["label"], "path": base, "free": st["free"], "total": st["total"],
            "thumbs_mode": config.get().get("thumbs_mode", "online"), "tmdb": movieinfo.configured(),
            "items": items}


# ------------------------------------------------------------------ plan przenoszenia
def plan_move(src_disk, src_cat, names, dst_disk, dst_cat, busy=()):
    sd, sc, sbase = location(src_disk, src_cat)
    dd, dc, dbase = location(dst_disk, dst_cat)
    if os.path.realpath(sbase) == os.path.realpath(dbase):
        raise FMError("Folder źródłowy i docelowy są takie same.")
    if sc["kind"] != dc["kind"]:
        raise FMError("Nie można przenosić między kategoriami różnego typu (%s → %s): "
                      "filmy i seriale mają inne nazewnictwo w Plexie." % (sc["label"], dc["label"]))
    if not names:
        raise FMError("Nic nie zaznaczono.")
    same_fs = (os.stat(sbase).st_dev == os.stat(dbase).st_dev
               and not os.environ.get("PLEXDL_FORCE_COPY"))  # zmienna tylko do testów
    items, problems, total = [], [], 0
    for name in names:
        try:
            src = item_path(sbase, name)
        except FMError as e:
            problems.append(str(e))
            continue
        size, _ = tree_size(src)
        it = {"name": name, "size": size, "problem": ""}
        if os.path.lexists(os.path.join(dbase, name)):
            it["problem"] = "istnieje już w miejscu docelowym"
        elif is_busy(src, busy):
            it["problem"] = "trwa pobieranie do tego folderu"
        if it["problem"]:
            problems.append("%s: %s" % (name, it["problem"]))
        total += size
        items.append(it)
    free = disk_status(dd)["free"]
    space_ok = same_fs or free is None or total + 200 * 1024 * 1024 <= free
    if not space_ok:
        problems.append("Za mało miejsca na %s (potrzeba %.1f GB, wolne %.1f GB)."
                        % (dd["label"], total / 1e9, free / 1e9))
    return {"src": {"disk": sd["id"], "disk_label": sd["label"], "category": sc["id"],
                    "category_label": sc["label"], "path": sbase},
            "dst": {"disk": dd["id"], "disk_label": dd["label"], "category": dc["id"],
                    "category_label": dc["label"], "path": dbase, "free": free},
            "same_fs": same_fs, "items": items, "total": total, "problems": problems,
            "ok": not problems and bool(items)}


# ------------------------------------------------------------------ operacje w tle
class Ops:
    def __init__(self):
        self.lock = threading.RLock()
        self.ops = {}
        self.queue = []
        self.cv = threading.Condition(self.lock)
        threading.Thread(target=self._worker, name="plexdl-fm", daemon=True).start()

    def _new(self, kind, title, total=0, **extra):
        op = {"id": uuid.uuid4().hex[:10], "type": kind, "title": title, "status": "queued",
              "total": total, "done": 0, "current": "", "phase": "", "error": "", "log": [],
              "items_total": 0, "items_done": 0, "created": time.time(), "finished": None,
              "cancel": False}
        op.update(extra)
        with self.cv:
            self.ops[op["id"]] = op
            self.queue.append(op["id"])
            self.cv.notify()
        return op

    def public(self):
        with self.lock:
            now = time.time()
            for k in [k for k, o in self.ops.items() if o["finished"] and now - o["finished"] > 3600]:
                del self.ops[k]
            return sorted(({k: v for k, v in o.items() if k not in ("cancel", "plan")}
                           for o in self.ops.values()), key=lambda o: -o["created"])

    def active(self):
        with self.lock:
            return sum(1 for o in self.ops.values() if o["status"] in ("queued", "running"))

    def cancel(self, op_id):
        with self.lock:
            op = self.ops.get(op_id)
            if not op:
                raise FMError("Nie ma takiej operacji.")
            if op["status"] in ("queued", "running"):
                op["cancel"] = True
                if op["status"] == "queued":
                    op.update(status="cancelled", finished=time.time())

    def clear(self):
        with self.lock:
            for k in [k for k, o in self.ops.items() if o["finished"]]:
                del self.ops[k]

    def _worker(self):
        while True:
            with self.cv:
                while not self.queue:
                    self.cv.wait()
                op = self.ops.get(self.queue.pop(0))
            if not op or op["status"] != "queued":
                continue
            op["status"] = "running"
            try:
                {"move": self._run_move, "thumbs": self._run_thumbs}[op["type"]](op)
                if op["cancel"]:
                    op["status"] = "cancelled"
                elif op["status"] == "running":
                    op["status"] = "error" if op["error"] else "done"
            except Exception as e:  # pragma: no cover
                log.exception("Operacja menedżera plików")
                op.update(status="error", error=str(e))
            op["finished"] = time.time()
            op["current"] = ""

    # ---- przenoszenie
    def move(self, plan):
        if not plan["ok"]:
            raise FMError("; ".join(plan["problems"]) or "Nie można wykonać operacji.")
        title = "%d → %s / %s" % (len(plan["items"]), plan["dst"]["disk_label"], plan["dst"]["category_label"])
        total = plan["total"] * (1 if plan["same_fs"] else 2)  # kopia + weryfikacja
        return self._new("move", title, total, plan=plan, items_total=len(plan["items"]),
                         same_fs=plan["same_fs"], src_label="%s / %s" % (plan["src"]["disk_label"],
                                                                        plan["src"]["category_label"]),
                         dst_label="%s / %s" % (plan["dst"]["disk_label"], plan["dst"]["category_label"]))

    def _run_move(self, op):
        plan = op["plan"]
        sbase, dbase = plan["src"]["path"], plan["dst"]["path"]
        for it in plan["items"]:
            if op["cancel"]:
                break
            name = it["name"]
            op["current"] = name
            try:
                src = item_path(sbase, name)
                dst = os.path.join(dbase, name)
                if os.path.lexists(dst):
                    raise FMError("istnieje już w miejscu docelowym")
                if plan["same_fs"]:
                    op["phase"] = "move"
                    os.rename(src, dst)
                    op["done"] += it["size"]
                else:
                    self._copy_verify_swap(op, src, dst, dbase)
                op["items_done"] += 1
                op["log"].append({"name": name, "ok": True})
                _size_cache.pop(src, None)
            except Exception as e:
                msg = "Anulowano" if op["cancel"] else str(e)
                op["log"].append({"name": name, "ok": False, "error": msg})
                if not op["cancel"]:
                    op["error"] = "%s: %s" % (name, msg)
                log.warning("Przenoszenie %s: %s", name, msg)

    def _copy_verify_swap(self, op, src, dst, dbase):
        tmp = os.path.join(tmp_root(dbase), "move-" + op["id"], os.path.basename(dst))
        os.makedirs(os.path.dirname(tmp), exist_ok=True)
        files = []  # (ścieżka względna, rozmiar, sha256)
        try:
            op["phase"] = "copy"
            if os.path.isdir(src):
                for root, dirs, fnames in os.walk(src):
                    rel = os.path.relpath(root, src)
                    os.makedirs(os.path.join(tmp, rel), exist_ok=True)
                    for f in fnames:
                        r = os.path.normpath(os.path.join(rel, f))
                        files.append((r,) + self._copy_file(op, os.path.join(src, r), os.path.join(tmp, r)))
            else:
                files.append(("",) + self._copy_file(op, src, tmp))
            op["phase"] = "verify"
            for r, size, digest in files:
                p = os.path.join(tmp, r) if r else tmp
                if os.path.getsize(p) != size or self._hash(op, p) != digest:
                    raise FMError("weryfikacja kopii nie powiodła się (%s) – oryginał pozostał nietknięty" % (r or os.path.basename(src)))
            if op["cancel"]:
                raise FMError("Anulowano")
            op["phase"] = "finish"
            if os.path.lexists(dst):
                raise FMError("istnieje już w miejscu docelowym")
            os.rename(tmp, dst)
            _fix_perms(dst)
        except Exception:
            shutil.rmtree(os.path.dirname(tmp), ignore_errors=True)
            raise
        shutil.rmtree(os.path.dirname(tmp), ignore_errors=True)
        try:  # kopia jest kompletna i sprawdzona – usuwamy oryginał
            if os.path.isdir(src) and not os.path.islink(src):
                shutil.rmtree(src)
            else:
                os.remove(src)
        except OSError as e:
            raise FMError("skopiowano poprawnie, ale nie udało się usunąć oryginału: %s" % e)

    def _copy_file(self, op, src, dst):
        h = hashlib.sha256()
        size = 0
        with open(src, "rb") as fi, open(dst, "wb") as fo:
            while True:
                if op["cancel"]:
                    raise FMError("Anulowano")
                buf = fi.read(CHUNK)
                if not buf:
                    break
                h.update(buf)
                fo.write(buf)
                size += len(buf)
                op["done"] += len(buf)
            fo.flush()
            os.fsync(fo.fileno())
        try:
            shutil.copystat(src, dst)
        except OSError:
            pass
        return size, h.hexdigest()

    def _hash(self, op, path):
        h = hashlib.sha256()
        with open(path, "rb") as f:
            while True:
                if op["cancel"]:
                    raise FMError("Anulowano")
                buf = f.read(CHUNK)
                if not buf:
                    break
                h.update(buf)
                op["done"] += len(buf)
        return h.hexdigest()

    # ---- miniatury: odświeżenie dla całego dysku
    def refresh_thumbs(self, disk_id):
        d = config.disk(disk_id)
        if not d:
            raise FMError("Nieznany dysk.")
        if not movieinfo.configured():
            raise FMError("Dodaj klucz TMDB w zakładce Podgląd i okładki.")
        return self._new("thumbs", "Okładki: %s" % d["label"], 0, disk=disk_id)

    def _run_thumbs(self, op):
        d = config.disk(op["disk"])
        work = []
        for cat in config.get().get("categories", []):
            try:
                _, _, base = location(d["id"], cat["id"])
            except FMError:
                continue
            for e in os.scandir(base):
                if e.name.startswith(".") or e.name in SKIP:
                    continue
                if e.is_dir() or naming.split_ext(e.name)[1]:
                    work.append((cat, base, e.name, e.is_dir()))
        op["items_total"] = op["total"] = len(work)
        for cat, base, name, is_dir in work:
            if op["cancel"]:
                break
            op["current"] = name
            try:
                fetch_thumb(cat["kind"], base, name, is_dir, force=True)
                op["log"].append({"name": name, "ok": True})
            except Exception as e:
                op["log"].append({"name": name, "ok": False, "error": str(e)})
            op["items_done"] += 1
            op["done"] += 1


def _fix_perms(path):
    try:
        if os.path.isdir(path):
            for root, dirs, files in os.walk(path):
                os.chmod(root, 0o775)
                for f in files:
                    os.chmod(os.path.join(root, f), 0o664)
        else:
            os.chmod(path, 0o664)
    except OSError:
        pass  # NTFS/exFAT – uprawnienia ustala montowanie


# ------------------------------------------------------------------ usuwanie
def delete(disk_id, cat_id, names, busy=()):
    _, _, base = location(disk_id, cat_id)
    removed, problems = [], []
    for name in names:
        try:
            path = item_path(base, name)
            if is_busy(path, busy):
                raise FMError("trwa pobieranie do tego folderu")
            if os.path.isdir(path) and not os.path.islink(path):
                shutil.rmtree(path)
            else:
                th = find_thumb(base, name, False)
                os.remove(path)
                if th:
                    os.remove(th)
            _size_cache.pop(path, None)
            removed.append(name)
        except (FMError, OSError) as e:
            problems.append("%s: %s" % (name, e))
    return {"removed": removed, "problems": problems}


# ------------------------------------------------------------------ miniatury
_thumb_locks = {}
_thumb_sem = threading.Semaphore(3)
_thumb_fail = {}
FAIL_TTL = 1800


def fetch_thumb(kind, base, name, is_dir, force=False):
    """Pobiera plakat z TMDB i zapisuje jako „Tytuł (Rok).thumb.png” w folderze filmu."""
    key = os.path.join(base, name)
    lock = _thumb_locks.setdefault(key, threading.Lock())
    with lock:
        existing = find_thumb(base, name, is_dir)
        if existing and not force:
            return existing
        if not force and time.time() - _thumb_fail.get(key, 0) < FAIL_TTL:
            raise FMError("brak plakatu (ponowna próba później)")
        label = name if is_dir else naming.split_ext(name)[0]
        p = naming.parse_name(label)
        with _thumb_sem:
            try:
                url = movieinfo.poster_url(kind, p["title"], p["year"], p["tmdb"])
                if not url:
                    raise FMError("nie znaleziono plakatu w TMDB")
                data = movieinfo.download(url)
            except (movieinfo.InfoError, FMError) as e:
                _thumb_fail[key] = time.time()
                raise FMError(str(e))
        stem = thumb_base(base, name, is_dir)
        for ext in THUMB_EXTS:
            if os.path.exists(stem + ext):
                os.remove(stem + ext)
        if Image is not None:
            out = stem + ".thumb.png"
            with Image.open(io.BytesIO(data)) as im:
                im = im.convert("RGB")
                im.thumbnail((342, 513))
                im.save(out + ".part", "PNG", optimize=True)
        else:
            out = stem + ".thumb.jpg"
            with open(out + ".part", "wb") as f:
                f.write(data)
        os.replace(out + ".part", out)
        _thumb_fail.pop(key, None)
        try:
            os.chmod(out, 0o664)
        except OSError:
            pass
        return out


def get_thumb(disk_id, cat_id, name):
    _, cat, base = location(disk_id, cat_id, need_ok=False)
    path = item_path(base, name)
    is_dir = os.path.isdir(path)
    existing = find_thumb(base, name, is_dir)
    if existing:
        return existing
    mode = config.get().get("thumbs_mode", "online")
    if mode != "online" or not movieinfo.configured():
        raise FMError("brak miniatury")
    return fetch_thumb(cat["kind"], base, name, is_dir)


def delete_thumbs(disk_id):
    d = config.disk(disk_id)
    if not d:
        raise FMError("Nieznany dysk.")
    count = 0
    for cat in config.get().get("categories", []):
        try:
            _, _, base = location(d["id"], cat["id"], need_ok=False)
        except FMError:
            continue
        for e in os.scandir(base):
            if e.name.startswith(".") or e.name in SKIP:
                continue
            stem = thumb_base(base, e.name, e.is_dir())
            for ext in THUMB_EXTS:
                if os.path.isfile(stem + ext):
                    os.remove(stem + ext)
                    count += 1
    _thumb_fail.clear()
    return count


def cleanup_tmp():
    """Po restarcie: usuwa niedokończone kopie (oryginały nie były jeszcze ruszane)."""
    for d in config.get().get("disks", []):
        for base in (d.get("paths") or {}).values():
            root = tmp_root(base)
            if not os.path.isdir(root):
                continue
            for e in os.scandir(root):
                if e.name.startswith("move-"):
                    shutil.rmtree(e.path, ignore_errors=True)


ops = Ops()
