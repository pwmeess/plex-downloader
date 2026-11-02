"""Tłumaczenia interfejsu.

Teksty w kodzie są po angielsku. Plik locales/<kod>.json zawiera:
  {"_meta": {"name": "Polski", "code": "pl"}, "English text": "Tłumaczenie", ...}
Nowy język = nowy plik w locales/ (np. de.json) – pojawi się automatycznie w Ustawieniach.
"""
import json
import os
import threading

import config

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOCALES_DIR = os.path.join(BASE_DIR, "locales")
DEFAULT = "en"
_lock = threading.Lock()
_catalogs = {}
_mtimes = {}


def _load(code):
    path = os.path.join(LOCALES_DIR, code + ".json")
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return {}
    with _lock:
        if _mtimes.get(code) != mtime:
            with open(path, encoding="utf-8") as f:
                _catalogs[code] = json.load(f)
            _mtimes[code] = mtime
        return _catalogs[code]


def available():
    out = []
    if os.path.isdir(LOCALES_DIR):
        for name in sorted(os.listdir(LOCALES_DIR)):
            if name.endswith(".json"):
                code = name[:-5]
                meta = _load(code).get("_meta", {})
                out.append({"code": code, "name": meta.get("name", code)})
    return out


def current():
    lang = (config.get().get("language") or "").strip()
    return lang if lang and os.path.isfile(os.path.join(LOCALES_DIR, lang + ".json")) else DEFAULT


def catalog(lang=None):
    cat = dict(_load(lang or current()))
    cat.pop("_meta", None)
    return cat


def gettext(text, lang=None, **kw):
    lang = lang or current()
    out = _load(lang).get(text, text) if lang != DEFAULT else _load(DEFAULT).get(text, text)
    if kw:
        try:
            out = out.format(**kw)
        except (KeyError, IndexError, ValueError):
            pass
    return out


_ = gettext


def tmdb_language():
    meta = _load(current()).get("_meta", {})
    return meta.get("tmdb", "en-US")
