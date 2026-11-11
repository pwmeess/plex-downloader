"""Poglądowe informacje o filmie/serialu z TMDB (The Movie Database) – tylko do wyświetlenia.

Nic nie jest zapisywane do plików ani na dysk; Plex i tak pobiera własne metadane.
"""
import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

import config
from i18n import _, tmdb_language

API = os.environ.get("PLEXDL_TMDB_BASE", "https://api.themoviedb.org/3")
IMG = os.environ.get("PLEXDL_TMDB_IMG", "https://image.tmdb.org/t/p/")
TTL = 6 * 3600
UA = "PlexDownloader/1.1 (+github.com/pwmeess/plex-downloader)"

_cache = {}
_lock = threading.Lock()


class InfoError(Exception):
    pass


def configured():
    return bool((config.get().get("tmdb_api_key") or "").strip())


def _get(path, **params):
    key = (config.get().get("tmdb_api_key") or "").strip()
    if not key:
        raise InfoError(_("No TMDB API key."))
    headers = {"Accept": "application/json", "User-Agent": UA}
    if len(key) > 40:  # „API Read Access Token” (v4) – przekazywany jako Bearer
        headers["Authorization"] = "Bearer " + key
    else:              # klasyczny „API Key” (v3)
        params["api_key"] = key
    url = API + path + "?" + urllib.parse.urlencode({k: v for k, v in params.items() if v not in (None, "")})
    now = time.time()
    with _lock:
        hit = _cache.get(url)
        if hit and now - hit[0] < TTL:
            return hit[1]
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 401:
            raise InfoError(_("Invalid TMDB API key – check it in Settings."))
        if e.code == 404:
            raise InfoError(_("Not found in TMDB."))
        raise InfoError(_("TMDB returned error %d.") % e.code)
    except (urllib.error.URLError, OSError, ValueError):
        raise InfoError(_("No connection to TMDB."))
    with _lock:
        if len(_cache) > 500:
            _cache.clear()
        _cache[url] = (now, data)
    return data


def check_key(key):
    """Is this TMDB key valid? (ok, message) – asked without the cache, the key is not saved."""
    key = re.sub(r"\s+", "", key or "")
    if not key:
        return False, _("No TMDB API key.")
    headers = {"Accept": "application/json", "User-Agent": UA}
    params = {}
    if len(key) > 40:
        headers["Authorization"] = "Bearer " + key
    else:
        params["api_key"] = key
    url = API + "/configuration" + ("?" + urllib.parse.urlencode(params) if params else "")
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=8) as resp:
            resp.read(1)
        return True, _("Key OK")
    except urllib.error.HTTPError as e:
        if e.code == 401:
            return False, _("Invalid key")
        return False, _("TMDB returned error %d.") % e.code
    except (urllib.error.URLError, OSError, ValueError):
        return None, _("No connection to TMDB.")


def split_title(text):
    """„Milczenie owiec (1991)” → („Milczenie owiec”, 1991)."""
    text = (text or "").strip()
    m = re.match(r"^(.*?)\s*\((\d{4})\)\s*$", text)
    if m:
        return m.group(1).strip(), int(m.group(2))
    return text, None


def _year(date):
    return int(date[:4]) if date and len(date) >= 4 and date[:4].isdigit() else None


def _poster(path, size="w342"):
    return IMG + size + path if path else None


def search(kind, title, year=None):
    """Zwraca listę do 6 trafień: id, tytuł, rok, oryginalny tytuł."""
    if not title:
        return []
    if kind == "tv":
        res = _get("/search/tv", query=title, first_air_date_year=year, language=tmdb_language())
        if year and not res.get("results"):
            res = _get("/search/tv", query=title, language=tmdb_language())
        items = [{"id": r["id"], "title": r.get("name") or r.get("original_name"),
                  "original_title": r.get("original_name"), "year": _year(r.get("first_air_date")),
                  "poster": _poster(r.get("poster_path"), "w92")} for r in res.get("results", [])]
    else:
        res = _get("/search/movie", query=title, primary_release_year=year, language=tmdb_language())
        if year and not res.get("results"):  # rok z nazwy pliku bywa rokiem premiery DVD itp.
            res = _get("/search/movie", query=title, year=year, language=tmdb_language())
        if year and not res.get("results"):
            res = _get("/search/movie", query=title, language=tmdb_language())
        items = [{"id": r["id"], "title": r.get("title") or r.get("original_title"),
                  "original_title": r.get("original_title"), "year": _year(r.get("release_date")),
                  "poster": _poster(r.get("poster_path"), "w92")} for r in res.get("results", [])]
    return items[:6]


def details(kind, item_id, season=None, episode=None):
    kind = "tv" if kind == "tv" else "movie"
    d = _get("/%s/%d" % (kind, int(item_id)), language=tmdb_language(), append_to_response="credits,external_ids")
    overview = d.get("overview") or ""
    if not overview and tmdb_language() != "en-US":  # brak opisu w języku interfejsu → angielski
        try:
            overview = _get("/%s/%d" % (kind, int(item_id)), language="en-US").get("overview") or ""
        except InfoError:
            pass
    credits = d.get("credits") or {}
    cast = [c.get("name") for c in (credits.get("cast") or [])[:5] if c.get("name")]
    if kind == "tv":
        title, original = d.get("name"), d.get("original_name")
        year = _year(d.get("first_air_date"))
        runtime = (d.get("episode_run_time") or [None])[0]
        creators = [c.get("name") for c in d.get("created_by") or [] if c.get("name")]
    else:
        title, original = d.get("title"), d.get("original_title")
        year = _year(d.get("release_date"))
        runtime = d.get("runtime")
        creators = [c.get("name") for c in credits.get("crew") or []
                    if c.get("job") == "Director" and c.get("name")]
    imdb_id = (d.get("external_ids") or {}).get("imdb_id") or d.get("imdb_id")
    info = {
        "kind": kind, "id": d.get("id"), "title": title, "original_title": original, "year": year,
        "runtime": runtime, "genres": [g.get("name") for g in d.get("genres") or []],
        "overview": overview, "rating": round(d.get("vote_average") or 0, 1),
        "votes": d.get("vote_count") or 0, "poster": _poster(d.get("poster_path")),
        "people_label": "Created by" if kind == "tv" else "Directed by", "people": creators[:3],
        "cast": cast, "imdb_id": imdb_id, "seasons": d.get("number_of_seasons"),
        "tmdb_url": "https://www.themoviedb.org/%s/%s?language=pl" % (kind, d.get("id")),
        "imdb_url": "https://www.imdb.com/title/%s/" % imdb_id if imdb_id else None,
        "filmweb_url": "https://www.filmweb.pl/search#/?query=" + urllib.parse.quote(
            "%s %s" % (title or original or "", year or "")).strip(),
        "episode": None,
    }
    if kind == "tv" and season is not None and episode is not None:
        try:
            ep = _get("/tv/%d/season/%d/episode/%d" % (int(item_id), int(season), int(episode)), language=tmdb_language())
            info["episode"] = {"season": int(season), "episode": int(episode), "name": ep.get("name"),
                               "air_date": ep.get("air_date")}
        except (InfoError, ValueError):
            pass
    return info


def lookup(kind, title, year=None, item_id=None, season=None, episode=None):
    kind = "tv" if kind == "tv" else "movie"
    results = search(kind, title, year) if title else []
    if item_id is None:
        if not results:
            return {"results": [], "item": None}
        item_id = results[0]["id"]
    return {"results": results, "item": details(kind, item_id, season, episode)}


def poster_url(kind, title, year=None, tmdb_id=None, size="w342"):
    """Adres plakatu do miniatury w menedżerze plików (None, gdy brak)."""
    kind = "tv" if kind == "tv" else "movie"
    path = None
    if tmdb_id:
        path = _get("/%s/%d" % (kind, int(tmdb_id)), language=tmdb_language()).get("poster_path")
    elif title:
        if kind == "tv":
            res = _get("/search/tv", query=title, first_air_date_year=year, language=tmdb_language())
        else:
            res = _get("/search/movie", query=title, primary_release_year=year, language=tmdb_language())
            if year and not res.get("results"):
                res = _get("/search/movie", query=title, year=year, language=tmdb_language())
        if year and not res.get("results"):
            res = _get("/search/%s" % kind, query=title, language=tmdb_language())
        for r in res.get("results", []):
            if r.get("poster_path"):
                path = r["poster_path"]
                break
    return _poster(path, size) if path else None


def download(url, timeout=15, limit=8 * 1024 * 1024):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read(limit + 1)
    except (urllib.error.URLError, OSError) as e:
        raise InfoError(_("Could not download the poster: %s") % e)
    if len(data) > limit:
        raise InfoError(_("The poster is too large."))
    return data
