"""Menedżer plików: przeglądanie bibliotek, przenoszenie między folderami/dyskami, usuwanie, okładki.

Zasady bezpieczeństwa:
- operujemy wyłącznie na elementach folderów kategorii skonfigurowanych w Ustawieniach,
- nazwy nie mogą zawierać ścieżek; ścieżka po rozwiązaniu musi leżeć w folderze kategorii,
- przenoszenie między dyskami: kopia do folderu tymczasowego → weryfikacja SHA-256 →
  zmiana nazwy na docelową → dopiero wtedy usunięcie oryginału,
- elementy, do których trwa pobieranie, są zablokowane.
"""
import hashlib
import logging
import os
import re
import shutil
import threading
import time
import uuid

import actlog
import config
import movieinfo
import naming
from downloader import TMP_DIRNAME, disk_status
from i18n import _

log = logging.getLogger("plexdl")
CHUNK = 4 * 1024 * 1024
THUMB = ".thumb.jpg"
THUMB_EXTS = (".thumb.jpg", ".thumb.png")  # .png – okładki z wersji 1.2.0
SKIP = {"@eaDir", "$RECYCLE.BIN", "System Volume Information", "lost+found", "#recycle", ".Trash-1000"}
# foldery dodatków Plexa (zwiastuny itp.) – nie liczą się jako osobne filmy
EXTRA_DIRS = {"trailers", "featurettes", "behind the scenes", "deleted scenes", "interviews",
              "scenes", "shorts", "other", "extras", "specials", "subs", "subtitles"}
SUB_EXTS = {".srt", ".ass", ".ssa", ".sub", ".idx", ".vtt", ".smi"}
EXTRA_SUFFIX = re.compile(r"-(trailer|sample|featurette|behindthescenes|deleted|interview|scene|short|other)$", re.I)
EPISODE = re.compile(r"(?i)\bS(\d{1,2})E(\d{1,3})")
SIZE_TTL = 120


class FMError(Exception):
    pass


# ------------------------------------------------------------------ ścieżki
def location(disk_id, cat_id, need_ok=True):
    d = config.disk(disk_id)
    if not d:
        raise FMError(_("Unknown disk."))
    cat = config.category(cat_id)
    if not cat:
        raise FMError(_("Unknown category."))
    base = (d.get("paths") or {}).get(cat_id)
    if not base:
        raise FMError(_("Disk %s has no folder for the category “%s”.") % (d["label"], cat["label"]))
    if need_ok:
        st = disk_status(d)
        if not st["ok"]:
            raise FMError("%s: %s" % (d["label"], st["problem"]))
    if not os.path.isdir(base):
        raise FMError(_("Folder does not exist: %s") % base)
    return d, cat, base


def _safe_name(name):
    if (not name or name in (".", "..") or "/" in name or "\\" in name or "\0" in name
            or name.startswith(".")):
        raise FMError(_("Invalid name: %r") % name)


def item_path(base, name):
    _safe_name(name)
    path = os.path.join(base, name)
    if os.path.dirname(os.path.realpath(path)) != os.path.realpath(base):
        raise FMError(_("Invalid name: %r") % name)
    if not os.path.lexists(path):
        raise FMError(_("Not found: %s") % name)
    return path


def sub_path(root, rel):
    """Ścieżka pliku wewnątrz folderu serialu (np. „Season 01/Show - S01E02.mkv”)."""
    parts = [p for p in (rel or "").split("/") if p]
    if not parts or len(parts) > 3:
        raise FMError(_("Invalid name: %r") % rel)
    for p in parts:
        _safe_name(p)
    path = os.path.join(root, *parts)
    if not os.path.realpath(path).startswith(os.path.realpath(root) + os.sep):
        raise FMError(_("Invalid name: %r") % rel)
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


def _is_video(name):
    stem, ext = naming.split_ext(name)
    return bool(ext) and not EXTRA_SUFFIX.search(stem)


# ------------------------------------------------------------------ lista
_size_cache = {}


def scan_item(path, kind):
    """Rozmiar, liczba głównych plików wideo (lub odcinków) i czy folder zawiera dodatki."""
    now = time.time()
    try:
        mtime = os.stat(path).st_mtime
    except OSError:
        return {"size": 0, "videos": 0, "extras": False}
    hit = _size_cache.get(path)
    if hit and hit[0] == mtime and now - hit[1] < SIZE_TTL:
        return hit[2]
    total = videos = 0
    extras = False
    if os.path.isfile(path):
        total, videos = os.path.getsize(path), 1
    else:
        for root, dirs, files in os.walk(path):
            rel_depth = os.path.relpath(root, path).count(os.sep) + (0 if root == path else 1)
            keep = []
            for x in dirs:
                if x.startswith(".") or x in SKIP:
                    continue
                if x.lower() in EXTRA_DIRS or (kind != "tv" and rel_depth == 0):
                    extras = True  # podfolder w folderze filmu = dodatki (zwiastuny itp.)
                keep.append(x)
            dirs[:] = keep
            in_extra = any(p.lower() in EXTRA_DIRS for p in os.path.relpath(root, path).split(os.sep))
            for f in files:
                if f.startswith(".") or f.endswith(THUMB_EXTS):
                    continue
                try:
                    total += os.path.getsize(os.path.join(root, f))
                except OSError:
                    pass
                ext = os.path.splitext(f)[1].lower()
                if ext in SUB_EXTS:
                    extras = True
                elif naming.split_ext(f)[1]:
                    if in_extra or not _is_video(f):
                        extras = True
                    else:
                        videos += 1
        if kind != "tv" and videos > 1:
            extras = True  # kilka wersji filmu w jednym folderze
    res = {"size": total, "videos": videos, "extras": extras}
    _size_cache[path] = (mtime, now, res)
    return res


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
                continue
            label = e.name if is_dir else naming.split_ext(e.name)[0]
            p = naming.parse_name(label)
            info = scan_item(e.path, cat["kind"])
            th = find_thumb(base, e.name, is_dir)
            items.append({
                "name": e.name, "is_dir": is_dir, "title": p["title"] or label, "year": p["year"],
                "edition": p["edition"], "tmdb": p["tmdb"], "size": info["size"], "videos": info["videos"],
                "extras": info["extras"], "thumb": bool(th), "thumb_v": int(os.path.getmtime(th)) if th else 0,
                "busy": is_busy(e.path, busy),
            })
    items.sort(key=lambda i: (i["title"].lower(), i["year"] or 0))
    st = disk_status(d)
    return {"disk": d["id"], "disk_label": d["label"], "category": cat["id"], "kind": cat["kind"],
            "category_label": cat["label"], "path": base, "free": st["free"], "total": st["total"],
            "thumbs_mode": config.get().get("thumbs_mode", "online"),
            "tmdb": movieinfo.configured() and cat.get("tmdb", True), "items": items}


def list_episodes(disk_id, cat_id, show):
    """Odcinki serialu pogrupowane według sezonów (do przenoszenia wybranych odcinków)."""
    _, cat, base = location(disk_id, cat_id)
    if cat["kind"] != "tv":
        raise FMError(_("Episodes can only be selected in TV show categories."))
    root = item_path(base, show)
    seasons = {}
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = [x for x in dirs if not x.startswith(".") and x not in SKIP]
        for f in files:
            if f.startswith(".") or not _is_video(f):
                continue
            rel = os.path.relpath(os.path.join(dirpath, f), root).replace(os.sep, "/")
            if any(p.lower() in EXTRA_DIRS for p in rel.split("/")[:-1]):
                continue
            m = EPISODE.search(f)
            season_name = rel.split("/")[0] if "/" in rel else _("(no season folder)")
            seasons.setdefault(season_name, []).append({
                "rel": rel, "name": f, "size": os.path.getsize(os.path.join(dirpath, f)),
                "code": "S%02dE%02d" % (int(m.group(1)), int(m.group(2))) if m else "",
            })
    out = []
    for name in sorted(seasons):
        eps = sorted(seasons[name], key=lambda e: (e["code"] or "~", e["name"]))
        out.append({"season": name, "episodes": eps, "size": sum(e["size"] for e in eps)})
    return {"show": show, "seasons": out}


def _sidecars(path):
    """Pliki towarzyszące odcinkowi (napisy itp.) o tym samym początku nazwy."""
    d, f = os.path.split(path)
    stem = os.path.splitext(f)[0]
    out = []
    for x in os.listdir(d):
        if x != f and x.startswith(stem + ".") and os.path.splitext(x)[1].lower() in SUB_EXTS | {".nfo", ".jpg", ".png"}:
            out.append(os.path.join(d, x))
    return out


# ------------------------------------------------------------------ plan przenoszenia
def _check_kinds(sc, dc):
    if sc["kind"] != dc["kind"]:
        raise FMError(_("Cannot move between categories of different types (%s → %s): movies, TV shows and other videos use different naming in Plex.") % (sc["label"], dc["label"]))


def _route(sd, sc, sbase, dd, dc, dbase):
    return {"src": {"disk": sd["id"], "disk_label": sd["label"], "category": sc["id"],
                    "category_label": sc["label"], "path": sbase},
            "dst": {"disk": dd["id"], "disk_label": dd["label"], "category": dc["id"],
                    "category_label": dc["label"], "path": dbase, "free": disk_status(dd)["free"]}}


def _same_fs(a, b):
    return os.stat(a).st_dev == os.stat(b).st_dev and not os.environ.get("PLEXDL_FORCE_COPY")


def plan_move(src_disk, src_cat, names, dst_disk, dst_cat, busy=()):
    sd, sc, sbase = location(src_disk, src_cat)
    dd, dc, dbase = location(dst_disk, dst_cat)
    if os.path.realpath(sbase) == os.path.realpath(dbase):
        raise FMError(_("Source and target folders are the same."))
    _check_kinds(sc, dc)
    if not names:
        raise FMError(_("Nothing selected."))
    same_fs = _same_fs(sbase, dbase)
    items, problems, total = [], [], 0
    for name in names:
        try:
            src = item_path(sbase, name)
        except FMError as e:
            problems.append(str(e))
            continue
        size = scan_item(src, sc["kind"])["size"]
        it = {"name": name, "size": size, "problem": ""}
        if os.path.lexists(os.path.join(dbase, name)):
            it["problem"] = _("already exists at the destination")
        elif is_busy(src, busy):
            it["problem"] = _("a download into this folder is in progress")
        if it["problem"]:
            problems.append("%s: %s" % (name, it["problem"]))
        total += size
        items.append(it)
    plan = _route(sd, sc, sbase, dd, dc, dbase)
    plan.update(mode="items", same_fs=same_fs, items=items, total=total, problems=problems)
    _space(plan)
    return plan


def plan_episodes(src_disk, src_cat, show, rels, dst_disk, dst_cat, busy=()):
    """Przeniesienie wybranych odcinków serialu – na dysku docelowym powstaje ten sam układ folderów."""
    sd, sc, sbase = location(src_disk, src_cat)
    dd, dc, dbase = location(dst_disk, dst_cat)
    _check_kinds(sc, dc)
    if sc["kind"] != "tv":
        raise FMError(_("Episodes can only be selected in TV show categories."))
    if os.path.realpath(sbase) == os.path.realpath(dbase):
        raise FMError(_("Source and target folders are the same."))
    if not rels:
        raise FMError(_("Nothing selected."))
    root = item_path(sbase, show)
    same_fs = _same_fs(sbase, dbase)
    items, problems, total, seen = [], [], 0, set()
    for rel in rels:
        try:
            src = sub_path(root, rel)
        except FMError as e:
            problems.append(str(e))
            continue
        if not os.path.isfile(src):
            problems.append(_("Not found: %s") % rel)
            continue
        for p in [src] + _sidecars(src):
            r = os.path.relpath(p, root).replace(os.sep, "/")
            if r in seen:
                continue
            seen.add(r)
            size = os.path.getsize(p)
            it = {"name": r, "size": size, "problem": ""}
            if os.path.lexists(os.path.join(dbase, show, *r.split("/"))):
                it["problem"] = _("already exists at the destination")
            elif is_busy(p, busy) or is_busy(os.path.dirname(p), busy):
                it["problem"] = _("a download into this folder is in progress")
            if it["problem"]:
                problems.append("%s: %s" % (r, it["problem"]))
            total += size
            items.append(it)
    plan = _route(sd, sc, sbase, dd, dc, dbase)
    plan.update(mode="episodes", show=show, same_fs=same_fs, items=items, total=total, problems=problems)
    _space(plan)
    return plan


def _space(plan):
    free = plan["dst"]["free"]
    if not plan["same_fs"] and free is not None and plan["total"] + 200 * 1024 * 1024 > free:
        plan["problems"].append(_("Not enough space on %s (needed %.1f GB, free %.1f GB).")
                                % (plan["dst"]["disk_label"], plan["total"] / 1e9, free / 1e9))
    plan["ok"] = not plan["problems"] and bool(plan["items"])


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
              "cancel": False, "speed": 0, "eta": None, "_samples": []}
        op.update(extra)
        with self.cv:
            self.ops[op["id"]] = op
            self.queue.append(op["id"])
            self.cv.notify()
        return op

    @staticmethod
    def _rate(op):
        """Prędkość z ostatnich ~5 s (lekko: liczona tylko przy odpytaniu przez przeglądarkę)."""
        now = time.time()
        s = op["_samples"]
        s.append((now, op["done"]))
        while len(s) > 2 and now - s[0][0] > 5:
            s.pop(0)
        if op["status"] != "running" or len(s) < 2 or s[-1][0] - s[0][0] < 0.5:
            op["speed"], op["eta"] = (0, None) if op["status"] != "running" else (op["speed"], op["eta"])
            return
        dt = s[-1][0] - s[0][0]
        op["speed"] = max(0, int((s[-1][1] - s[0][1]) / dt))
        op["eta"] = int((op["total"] - op["done"]) / op["speed"]) if op["speed"] and op["total"] else None

    def public(self):
        with self.lock:
            now = time.time()
            for k in [k for k, o in self.ops.items() if o["finished"] and now - o["finished"] > 3600]:
                del self.ops[k]
            out = []
            for o in self.ops.values():
                self._rate(o)
                out.append({k: v for k, v in o.items() if k not in ("cancel", "plan", "_samples")})
            return sorted(out, key=lambda o: -o["created"])

    def active(self):
        with self.lock:
            return sum(1 for o in self.ops.values() if o["status"] in ("queued", "running"))

    def cancel(self, op_id):
        with self.lock:
            op = self.ops.get(op_id)
            if not op:
                raise FMError(_("No such operation."))
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
                log.exception("File manager operation")
                op.update(status="error", error=str(e))
            op["finished"] = time.time()
            op["current"] = ""

    # ---- przenoszenie
    def move(self, plan, verify=True):
        """verify=False: kopia bez drugiego odczytu (SHA-256); przed usunięciem oryginału
        porównywany jest tylko rozmiar plików."""
        if not plan["ok"]:
            raise FMError("; ".join(plan["problems"]) or _("The operation cannot be performed."))
        src_label = "%s / %s" % (plan["src"]["disk_label"], plan["src"]["category_label"])
        dst_label = "%s / %s" % (plan["dst"]["disk_label"], plan["dst"]["category_label"])
        verify = bool(verify) and not plan["same_fs"]
        # pasek postępu: kopia (+ weryfikacja); osobne liczniki copied / verified dla każdego etapu
        total = plan["total"] * (2 if verify else 1)
        return self._new("move", dst_label, total, plan=plan, items_total=len(plan["items"]),
                         same_fs=plan["same_fs"], src_label=src_label, dst_label=dst_label,
                         src_disk=plan["src"]["disk_label"], dst_disk=plan["dst"]["disk_label"],
                         show=plan.get("show"), verify=verify, size=plan["total"], copied=0, verified=0)

    def _run_move(self, op):
        plan = op["plan"]
        sbase, dbase = plan["src"]["path"], plan["dst"]["path"]
        episodes = plan.get("mode") == "episodes"
        sroot = os.path.join(sbase, plan["show"]) if episodes else sbase
        droot = os.path.join(dbase, plan["show"]) if episodes else dbase
        for it in plan["items"]:
            if op["cancel"]:
                break
            name = it["name"]
            op["current"] = name
            try:
                if episodes:
                    src = sub_path(sroot, name)
                    dst = os.path.join(droot, *name.split("/"))
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                else:
                    src = item_path(sbase, name)
                    dst = os.path.join(dbase, name)
                if os.path.lexists(dst):
                    raise FMError(_("already exists at the destination"))
                if plan["same_fs"]:
                    op["phase"] = "move"
                    os.rename(src, dst)
                    op["done"] += it["size"]
                    op["copied"] = op.get("copied", 0) + it["size"]
                else:
                    self._copy_verify_swap(op, src, dst, dbase)
                op["items_done"] += 1
                op["log"].append({"name": name, "ok": True})
                actlog.write("MOVE", "%s%s: %s → %s%s" % (plan["show"] + "/" if episodes else "", name,
                                                         op["src_label"], op["dst_label"],
                                                         "" if op.get("verify", True) or plan["same_fs"] else " (no SHA-256 verification)"))
                _size_cache.pop(src, None)
            except Exception as e:
                msg = _("Cancelled") if op["cancel"] else str(e)
                op["log"].append({"name": name, "ok": False, "error": msg})
                if not op["cancel"]:
                    op["error"] = "%s: %s" % (name, msg)
                    actlog.write("ERROR", "%s: %s (%s → %s)" % (name, msg, op["src_label"], op["dst_label"]))
                log.warning("Move %s: %s", name, msg)
        if episodes:
            self._finish_episodes(sroot, droot)

    @staticmethod
    def _finish_episodes(sroot, droot):
        # okładka serialu także na dysku docelowym
        name = os.path.basename(sroot)
        for ext in THUMB_EXTS:
            s, d = os.path.join(sroot, name + ext), os.path.join(droot, name + ext)
            if os.path.isfile(s) and os.path.isdir(droot) and not os.path.exists(d):
                try:
                    shutil.copy2(s, d)
                except OSError:
                    pass
        # puste foldery sezonów po stronie źródłowej
        for root, dirs, files in os.walk(sroot, topdown=False):
            if root != sroot and not os.listdir(root):
                try:
                    os.rmdir(root)
                except OSError:
                    pass
        # serial bez żadnego pliku poza okładką i plikami systemowymi → usuwamy folder źródłowy
        rest = [f for f in os.listdir(sroot) if not f.endswith(THUMB_EXTS) and f != ".DS_Store"]
        if not rest:
            shutil.rmtree(sroot, ignore_errors=True)

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
                # daty folderów jak w oryginale (od najgłębszych)
                for root, dirs, _f in os.walk(src, topdown=False):
                    rel = os.path.relpath(root, src)
                    try:
                        shutil.copystat(root, os.path.join(tmp, rel))
                    except OSError:
                        pass
            else:
                files.append(("",) + self._copy_file(op, src, tmp))
            verify = op.get("verify", True)
            if verify:
                op["phase"] = "verify"
            for r, size, digest in files:
                p = os.path.join(tmp, r) if r else tmp
                if os.path.getsize(p) != size or (verify and self._hash(op, p) != digest):
                    raise FMError(_("copy verification failed (%s) – the original was left untouched") % (r or os.path.basename(src)))
            if op["cancel"]:
                raise FMError(_("Cancelled"))
            op["phase"] = "finish"
            if os.path.lexists(dst):
                raise FMError(_("already exists at the destination"))
            _fix_perms(tmp)
            os.rename(tmp, dst)
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
            raise FMError(_("copied correctly, but the original could not be removed: %s") % e)

    def _copy_file(self, op, src, dst):
        h = hashlib.sha256() if op.get("verify", True) else None
        size = 0
        with open(src, "rb") as fi, open(dst, "wb") as fo:
            while True:
                if op["cancel"]:
                    raise FMError(_("Cancelled"))
                buf = fi.read(CHUNK)
                if not buf:
                    break
                if h:
                    h.update(buf)
                fo.write(buf)
                size += len(buf)
                op["done"] += len(buf)
                op["copied"] = op.get("copied", 0) + len(buf)
            fo.flush()
            os.fsync(fo.fileno())
        try:
            shutil.copystat(src, dst)
        except OSError:
            pass
        return size, (h.hexdigest() if h else "")

    def _hash(self, op, path):
        h = hashlib.sha256()
        with open(path, "rb") as f:
            while True:
                if op["cancel"]:
                    raise FMError(_("Cancelled"))
                buf = f.read(CHUNK)
                if not buf:
                    break
                h.update(buf)
                op["done"] += len(buf)
                op["verified"] = op.get("verified", 0) + len(buf)
        return h.hexdigest()

    # ---- okładki: odświeżenie dla całego dysku
    def refresh_thumbs(self, disk_id):
        d = config.disk(disk_id)
        if not d:
            raise FMError(_("Unknown disk."))
        if not movieinfo.configured():
            raise FMError(_("Add a TMDB key in the Preview & posters tab."))
        actlog.write("POSTERS", _("Refreshing posters: %s") % d["label"])
        return self._new("thumbs", _("Posters: %s") % d["label"], 0, disk=disk_id)

    def _run_thumbs(self, op):
        d = config.disk(op["disk"])
        work = []
        for cat in config.get().get("categories", []):
            if not cat.get("tmdb", True):
                continue
            try:
                _d, _c, base = location(d["id"], cat["id"])
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
            except Exception:
                op["log"].append({"name": name, "ok": True, "note": "placeholder"})
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
    d, cat, base = location(disk_id, cat_id)
    removed, problems = [], []
    for name in names:
        try:
            path = item_path(base, name)
            if is_busy(path, busy):
                raise FMError(_("a download into this folder is in progress"))
            size = scan_item(path, cat["kind"])["size"]
            if os.path.isdir(path) and not os.path.islink(path):
                shutil.rmtree(path)
            else:
                th = find_thumb(base, name, False)
                os.remove(path)
                if th:
                    os.remove(th)
            _size_cache.pop(path, None)
            removed.append(name)
            actlog.write("DELETE", "%s (%s / %s, %.2f GB)" % (name, d["label"], cat["label"], size / 1e9))
        except (FMError, OSError) as e:
            problems.append("%s: %s" % (name, e))
    return {"removed": removed, "problems": problems}


# ------------------------------------------------------------------ okładki
_thumb_locks = {}
_thumb_sem = threading.Semaphore(3)
_thumb_fail = {}
FAIL_TTL = 24 * 3600  # brak wyniku w TMDB → nie pytamy ponownie przez dobę


def fetch_thumb(kind, base, name, is_dir, force=False):
    """Pobiera plakat z TMDB i zapisuje jako „Tytuł (Rok).thumb.jpg” w folderze filmu.
    Gdy TMDB nic nie zwraca – plik nie powstaje (widok pokaże obrazek zastępczy)."""
    key = os.path.join(base, name)
    lock = _thumb_locks.setdefault(key, threading.Lock())
    with lock:
        existing = find_thumb(base, name, is_dir)
        if existing and not force:
            return existing
        if not force and time.time() - _thumb_fail.get(key, 0) < FAIL_TTL:
            raise FMError("no poster")
        label = name if is_dir else naming.split_ext(name)[0]
        p = naming.parse_name(label)
        with _thumb_sem:
            try:
                url = movieinfo.poster_url(kind, p["title"], p["year"], p["tmdb"])
                if not url:
                    raise FMError("no poster")
                data = movieinfo.download(url)
            except (movieinfo.InfoError, FMError) as e:
                _thumb_fail[key] = time.time()
                raise FMError(str(e))
        stem = thumb_base(base, name, is_dir)
        for ext in THUMB_EXTS:
            if os.path.exists(stem + ext):
                os.remove(stem + ext)
        out = stem + THUMB
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
    _d, cat, base = location(disk_id, cat_id, need_ok=False)
    path = item_path(base, name)
    is_dir = os.path.isdir(path)
    existing = find_thumb(base, name, is_dir)
    if existing:
        return existing
    mode = config.get().get("thumbs_mode", "online")
    if mode != "online" or not movieinfo.configured() or not cat.get("tmdb", True):
        raise FMError("no poster")
    return fetch_thumb(cat["kind"], base, name, is_dir)


def delete_thumbs(disk_id):
    d = config.disk(disk_id)
    if not d:
        raise FMError(_("Unknown disk."))
    count = 0
    for cat in config.get().get("categories", []):
        try:
            _d, _c, base = location(d["id"], cat["id"], need_ok=False)
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
    actlog.write("POSTERS", _("Posters deleted from %s: %d") % (d["label"], count))
    return count


# ------------------------------------------------------------------ „Aktualizuj ścieżki”
ALIASES = {
    "movies": ["movies", "movie", "filmy", "film", "films"],
    "tv": ["tv shows", "tv", "tvshows", "tv series", "series", "shows", "seriale", "serial"],
    "kids": ["kids", "children", "dla dzieci", "bajki", "kids movies", "family"],
}


def find_plex_dir(mount):
    """Folder „Plex” (dowolna wielkość liter) bezpośrednio na dysku – tam kreator proponuje foldery kategorii."""
    try:
        for e in sorted(os.scandir(mount), key=lambda e: e.name.lower()):
            if e.is_dir(follow_symlinks=False) and e.name.lower() in ("plex", "plex media", "plex_media", "plexmedia"):
                return e.path
    except OSError:
        pass
    return None


def _rebase(path, mount):
    """Ścieżka z innego urządzenia (np. /plex_media_1024/Plex 1T/Home Video z Pi z Plexem) przeniesiona
    na ten punkt montowania (/mnt/plex_1024/Plex 1T/Home Video) – jeśli taki folder tu istnieje."""
    parts = [x for x in (path or "").split("/") if x]
    for k in range(1, len(parts)):
        cand = os.path.join(mount, *parts[k:])
        if os.path.isdir(cand):
            return cand
    return None


def scan_paths(mount, categories, current=None, max_depth=3, max_dirs=4000):
    """Szuka na dysku folderów pasujących do kategorii. Zwraca {id: {path, status}}:
    status = ok (obecna ścieżka istnieje), found (znaleziono), missing (nie znaleziono)."""
    current = current or {}
    if not mount or not os.path.isdir(mount):
        raise FMError(_("Mount point not found"))
    wanted = {}
    for c in categories:
        names = {(c.get("folder") or "").strip().lower(), (c.get("label") or "").strip().lower()}
        names |= set(ALIASES.get(c.get("id"), []))
        names |= {n.strip().lower() for n in c.get("names") or [] if isinstance(n, str)}
        wanted[c["id"]] = {n for n in names if n}
    found, visited = {}, 0
    queue = [(mount, 0)]
    while queue and visited < max_dirs:
        path, depth = queue.pop(0)
        try:
            entries = sorted(os.scandir(path), key=lambda e: e.name.lower())
        except OSError:
            continue
        for e in entries:
            if e.name.startswith(".") or e.name in SKIP or not e.is_dir(follow_symlinks=False):
                continue
            visited += 1
            low = e.name.lower()
            for cid, names in wanted.items():
                if low in names and cid not in found:
                    found[cid] = e.path
            if depth + 1 < max_depth:
                queue.append((e.path, depth + 1))
    # preferujemy foldery leżące obok już znalezionych (np. wszystkie w „Plex 1T/”)
    roots = [os.path.dirname(p) for p in list(current.values()) + list(found.values()) if p and os.path.isdir(p)]
    out = {}
    for c in categories:
        cid = c["id"]
        cur = current.get(cid)
        if cur and os.path.isdir(cur):
            out[cid] = {"path": cur, "status": "ok"}
            continue
        hit = None
        for r in roots:
            for n in wanted[cid]:
                for entry in (os.listdir(r) if os.path.isdir(r) else []):
                    if entry.lower() == n and os.path.isdir(os.path.join(r, entry)):
                        hit = os.path.join(r, entry)
                        break
                if hit:
                    break
            if hit:
                break
        hit = hit or found.get(cid) or _rebase(cur, mount)
        out[cid] = {"path": hit or cur or "", "status": "found" if hit else "missing"}
    return out


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
