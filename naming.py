"""Parsowanie nazw plików z URL i budowanie ścieżek zgodnych z konwencją Plexa."""
import os
import re
from urllib.parse import unquote, urlparse

VIDEO_EXTS = {
    ".mkv", ".mp4", ".avi", ".m4v", ".mov", ".wmv", ".ts", ".m2ts",
    ".mpg", ".mpeg", ".webm", ".flv", ".divx", ".ogm", ".vob",
}

# Tokeny, od których w nazwie zaczynają się "śmieci" (jakość, kodek, wersja językowa).
_JUNK = re.compile(
    r"(?i)\b(480p|576p|720p|1080p|1080i|2160p|4k|uhd|hdr|hdr10|dv|bluray|blu-ray|brrip|bdrip|"
    r"bdremux|remux|web[ -]?dl|webrip|web|hdtv|hdrip|dvdrip|dvdscr|dvd|cam|ts|x264|x265|h264|"
    r"h265|hevc|avc|xvid|divx|ac3|eac3|dts|dd5|ddp5|aac|mp3|atmos|truehd|pl|plsub|dubbing|dub|"
    r"lektor|napisy|subbed|multi|proper|repack|extended|unrated|limited|internal|remastered|imax)\b"
)
_YEAR = re.compile(r"\b(19\d{2}|20\d{2})\b")
_TV = re.compile(r"(?i)\bS(\d{1,2})[ ._-]?E(\d{1,3})(?:[ ._-]?E\d{1,3})?\b|\b(\d{1,2})x(\d{2,3})\b")
_FORBIDDEN = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


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
    return m.group(1).strip() if m else ""


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


def guess(filename):
    """Zgaduje typ (film/serial) i nazwę z nazwy pliku.

    Zwraca dict: kind, title, year, name (film: "Tytuł (YYYY)"), show, season, episode.
    """
    stem, ext = split_ext(filename)
    plain = re.sub(r"[._]+", " ", stem)
    result = {"kind": "movie", "title": "", "year": None, "name": "", "show": "",
              "season": None, "episode": None, "ext": ext}

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


def movie_target(base, name, ext):
    """base/Tytuł (YYYY)/Tytuł (YYYY).ext"""
    name = sanitize(name)
    if not name:
        raise ValueError("Podaj nazwę filmu.")
    return os.path.join(base, name), name + ext


def tv_target(base, show, season, episode, episode_title, ext):
    """base/Serial/Season 01/Serial - S01E02[ - Tytuł odcinka].ext"""
    show = sanitize(show)
    if not show:
        raise ValueError("Podaj nazwę serialu.")
    try:
        season = int(season)
        episode = int(episode)
    except (TypeError, ValueError):
        raise ValueError("Sezon i odcinek muszą być liczbami.")
    if not (0 <= season <= 99 and 0 <= episode <= 999):
        raise ValueError("Nieprawidłowy numer sezonu lub odcinka.")
    fname = "%s - S%02dE%02d" % (show, season, episode)
    et = sanitize(episode_title or "")
    if et:
        fname += " - " + et
    return os.path.join(base, show, "Season %02d" % season), fname + ext
