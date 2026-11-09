"""Parsowanie nazw plików z URL i budowanie ścieżek zgodnych z konwencją Plexa."""
import os
import re
from urllib.parse import unquote, urlparse

from i18n import _

VIDEO_EXTS = {
    ".mkv", ".mp4", ".avi", ".m4v", ".mov", ".wmv", ".ts", ".m2ts",
    ".mpg", ".mpeg", ".webm", ".flv", ".divx", ".ogm", ".vob",
}

# Tokeny, od których w nazwie zaczynają się "śmieci" (jakość, kodek, wersja językowa).
_JUNK = re.compile(
    r"(?i)\b(480p|576p|720p|1080p|1080i|2160p|4k|uhd|hdr|hdr10|dv|bluray|blu-ray|brrip|bdrip|"
    r"bdremux|remux|web[ -]?dl|webrip|web|hdtv|hdrip|dvdrip|dvdscr|dvd|cam|ts|x264|x265|h264|"
    r"h265|hevc|avc|xvid|divx|ac3|eac3|dts|dd5|ddp5|aac|mp3|atmos|truehd|pl|plsub|dubbing|dub|"
    r"lektor|napisy|subbed|subtitles?|softsub|hardsub|engsub|vostfr|multi|proper|repack|extended|"
    r"unrated|limited|internal|remastered|imax)\b"
)
# „(720)”, „[1080]” – rozdzielczość bez litery p, traktowana jak znacznik jakości
_RES_BRACKET = re.compile(r"(?i)[(\[]\s*(480|576|720|1080|2160)\s*[pi]?\s*[)\]]")
# Adres strony doklejony na początku nazwy: „SITE.COM - Tytuł…”, „www.site.net_Tytuł…”
_SITE_PREFIX = re.compile(
    r"(?i)^\s*(?:www\.)?[a-z0-9][a-z0-9-]*(?:\.[a-z0-9-]+)*\.(?:com|net|org|to|tv|cc|io|me|info|biz|ws|xyz|"
    r"pl|eu|se|ru|co|site|online|top|club|link|lol|li|is|nu|ag|sx|vip)\s*[-_\u2013]\s*")
# „Episode 2”, „Ep 02”, „Odcinek 2”, opcjonalnie „Season 1” / „Sezon 1”
_EPISODE = re.compile(r"(?i)\b(?:episode|ep|odcinek|odc)[ ._-]*(\d{1,3})\b")
_SEASON = re.compile(r"(?i)\b(?:season|sezon|series)[ ._-]*(\d{1,2})\b")
_YEAR = re.compile(r"\b(19\d{2}|20\d{2})\b")
_TV = re.compile(r"(?i)\bS(\d{1,2})[ ._-]?E(\d{1,3})(?:[ ._-]?E\d{1,3})?\b|\b(\d{1,2})x(\d{2,3})\b")
_FORBIDDEN = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_TAG = re.compile(r"\s*\{(edition|imdb|tmdb|tvdb)-([^}]*)\}", re.I)

# Popularne edycje (Plex: {edition-Nazwa}, maks. 32 znaki) – podpowiedzi w formularzu
EDITIONS = ["Director's Cut", "Extended Edition", "Theatrical Cut", "Final Cut", "Unrated",
            "Special Edition", "Ultimate Edition", "Collector's Edition", "Anniversary Edition",
            "Remastered", "IMAX", "Criterion", "Despecialized", "VHS", "Blu-ray", "Open Matte"]
# Popularne oznaczenia wersji (Plex: „Tytuł (Rok) - 1080p.mkv” – kilka wersji w jednym folderze)
VERSIONS = ["4K", "2160p", "1080p", "720p", "SD", "HDR", "Dolby Vision", "Blu-ray", "Remux",
            "Lektor PL", "Napisy PL", "Dubbing PL", "Wersja oryginalna"]
_EDITION_HINTS = [
    (re.compile(r"(?i)\bdirector'?s[ ._-]?cut\b|\bDC\b"), "Director's Cut"),
    (re.compile(r"(?i)\bextended([ ._-]?(edition|cut))?\b"), "Extended Edition"),
    (re.compile(r"(?i)\btheatrical([ ._-]?cut)?\b"), "Theatrical Cut"),
    (re.compile(r"(?i)\bfinal[ ._-]?cut\b"), "Final Cut"),
    (re.compile(r"(?i)\bunrated\b"), "Unrated"),
    (re.compile(r"(?i)\bspecial[ ._-]?edition\b"), "Special Edition"),
    (re.compile(r"(?i)\bultimate([ ._-]?(edition|cut))?\b"), "Ultimate Edition"),
    (re.compile(r"(?i)\bremaster(ed)?\b"), "Remastered"),
    (re.compile(r"(?i)\bimax\b"), "IMAX"),
    (re.compile(r"(?i)\bcriterion\b"), "Criterion"),
]


def sanitize(name):
    """Usuwa znaki niedozwolone w nazwach plików (także dla Samby/Windows)."""
    name = _FORBIDDEN.sub(" ", name or "")
    name = re.sub(r"\s+", " ", name).strip(" .")
    if name in ("", ".", ".."):
        return ""
    return name[:180]


def filename_from_url(url):
    try:
        path = urlparse(url).path
    except ValueError:
        return ""
    return unquote(os.path.basename(path.rstrip("/")))


def filename_from_content_disposition(value):
    if not value:
        return ""
    m = re.search(r"filename\*\s*=\s*([^']*)''([^;]+)", value, re.I)
    if m:
        try:
            return unquote(m.group(2).strip().strip('"'), encoding=m.group(1) or "utf-8")
        except LookupError:
            return unquote(m.group(2).strip().strip('"'))
    m = re.search(r'filename\s*=\s*"([^"]+)"', value, re.I) or re.search(r"filename\s*=\s*([^;]+)", value, re.I)
    if not m:
        return ""
    name = m.group(1).strip()
    # część serwerów koduje nazwę procentowo także w zwykłym filename= („Tytul%20Filmu.mp4”)
    if re.search(r"%[0-9A-Fa-f]{2}", name):
        name = unquote(name)
    return name


def split_ext(filename):
    stem, ext = os.path.splitext(filename or "")
    if ext.lower() in VIDEO_EXTS:
        return stem, ext.lower()
    return filename or "", ""


def _clean(text):
    text = re.sub(r"[._]+", " ", text)
    text = re.sub(r"\[[^\]]*\]", " ", text)          # [grupa]
    text = re.sub(r"\s+-\s*$", "", text.strip())
    text = re.sub(r"[\s\-(]+$", "", text)
    return re.sub(r"\s+", " ", text).strip()


def clean_tag(text, limit=32):
    """Tekst do znacznika {edition-…} / sufiksu wersji: bez klamer i znaków zakazanych."""
    text = sanitize(re.sub(r"[{}]", " ", text or ""))
    return text[:limit].strip()


def strip_tags(name):
    """„Blade Runner (1982) {edition-Final Cut} {tmdb-78}” → „Blade Runner (1982)”."""
    return _TAG.sub("", name or "").strip()


def parse_name(name):
    """Rozbija nazwę folderu/pliku Plex: tytuł, rok, edycja, ID."""
    out = {"title": "", "year": None, "edition": "", "tmdb": None, "imdb": None, "tvdb": None}
    for key, val in _TAG.findall(name or ""):
        key = key.lower()
        if key == "edition":
            out["edition"] = val.strip()
        elif key == "imdb":
            out["imdb"] = val.strip()
        elif val.strip().isdigit():
            out[key] = int(val)
    base = strip_tags(name)
    base = re.sub(r"\s+-\s+(?:pt|part|cd|disc|disk|dvd)\d+$", "", base, flags=re.I)
    m = re.match(r"^(.*?)\s*\((\d{4})\)(?:\s+-\s+.*)?$", base)
    if m:
        out["title"], out["year"] = m.group(1).strip(), int(m.group(2))
    else:
        out["title"] = re.sub(r"\s+-\s+[^-]+$", "", base).strip() or base
    return out


def detect_edition(filename):
    for rx, label in _EDITION_HINTS:
        if rx.search(filename or ""):
            return label
    return ""


def guess(filename):
    """Zgaduje typ (film/serial) i nazwę z nazwy pliku.

    Zwraca dict: kind, title, year, name (film: "Tytuł (YYYY)"), show, season, episode.
    """
    stem, ext = split_ext(filename)
    stem = _SITE_PREFIX.sub("", stem) or stem
    stem = _RES_BRACKET.sub(r" \1p ", stem)
    plain = re.sub(r"[._]+", " ", stem)
    result = {"kind": "movie", "title": "", "year": None, "name": "", "show": "",
              "season": None, "episode": None, "ext": ext, "edition": detect_edition(stem)}

    tv = _TV.search(plain)
    if tv:
        season = int(tv.group(1) or tv.group(3))
        episode = int(tv.group(2) or tv.group(4))
        show = _clean(plain[: tv.start()])
        y = _YEAR.search(show)
        if y and y.start() > 0:
            show = "%s (%s)" % (_clean(show[: y.start()]), y.group(1))
        if show:
            result.update(kind="tv", show=sanitize(show), season=season, episode=episode)
            return result

    ep = _EPISODE.search(plain)
    # „Star Wars Episode 1 The Phantom Menace 1999” to film: rok po słowie Episode → nie serial
    if ep and not _YEAR.search(plain[ep.end():]):
        se = _SEASON.search(plain)
        cut = min(ep.start(), se.start()) if se else ep.start()
        show = _clean(plain[:cut])
        y = _YEAR.search(show)
        if y and y.start() > 0:
            show = "%s (%s)" % (_clean(show[: y.start()]), y.group(1))
        if show:
            result.update(kind="tv", show=sanitize(show), season=int(se.group(1)) if se else 1,
                          episode=int(ep.group(1)))
            return result

    junk = _JUNK.search(plain)
    head = plain[: junk.start()] if junk and junk.start() > 0 else plain
    years = [m for m in _YEAR.finditer(head) if m.start() > 0]
    if years:
        y = years[-1]
        title = _clean(head[: y.start()])
        result["year"] = int(y.group(1))
    else:
        title = _clean(head)
    title = sanitize(title)
    result["title"] = title
    result["name"] = "%s (%d)" % (title, result["year"]) if result["year"] else title
    return result


def _tags(edition=None, ids=None):
    parts = []
    for key in ("tmdb", "imdb", "tvdb"):
        val = (ids or {}).get(key)
        if val:
            val = str(val).strip()
            if key == "imdb" and not re.match(r"^tt\d{5,10}$", val):
                raise ValueError(_("Invalid IMDb ID (expected tt1234567)."))
            if key != "imdb" and not val.isdigit():
                raise ValueError(_("Invalid %s ID.") % key.upper())
            parts.append("{%s-%s}" % (key, val))
    ed = clean_tag(edition)
    if ed:
        parts.append("{edition-%s}" % ed)
    return (" " + " ".join(parts)) if parts else ""


def movie_target(base, name, ext, edition=None, version=None, ids=None):
    """base/Tytuł (YYYY) {tmdb-…} {edition-…}/Tytuł (YYYY) {…} - wersja.ext

    Edycja (Plex Pass) trafia do folderu i pliku – zgodnie z zaleceniem Plex.
    Wersja (np. „1080p”) tylko do nazwy pliku – kilka wersji w jednym folderze.
    """
    name = sanitize(strip_tags(name))
    if not name:
        raise ValueError(_("Enter the movie name."))
    folder = name + _tags(edition, ids)
    fname = folder
    ver = clean_tag(version, 40)
    if ver:
        fname += " - " + ver
    return os.path.join(base, folder), fname + ext


def tv_target(base, show, season, episode, episode_title, ext, ids=None):
    """base/Serial {tmdb-…}/Season 01/Serial - S01E02[ - Tytuł odcinka].ext"""
    show = sanitize(strip_tags(show))
    if not show:
        raise ValueError(_("Enter the TV show name."))
    try:
        season = int(season)
        episode = int(episode)
    except (TypeError, ValueError):
        raise ValueError(_("Season and episode must be numbers."))
    if not (0 <= season <= 99 and 0 <= episode <= 999):
        raise ValueError(_("Invalid season or episode number."))
    folder = show + _tags(None, ids)
    fname = "%s - S%02dE%02d" % (show, season, episode)
    et = sanitize(episode_title or "")
    if et:
        fname += " - " + et
    return os.path.join(base, folder, "Season %02d" % season), fname + ext
