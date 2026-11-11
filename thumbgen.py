"""Posters from video frames (ffmpeg) – for home videos and titles without a TMDB match.

Only a few short reads of the file are needed (seek → one frame), so it also works over SMB.
The frame (usually 16:9) is placed on a blurred copy of itself in a 2:3 poster, so nothing is cut off.
"""
import os
import random
import shutil
import subprocess
import threading

from i18n import _

W, H = 400, 600                  # poster size (2:3)
SAMPLE_W, SAMPLE_H = 64, 36       # tiny grayscale frame used to score a candidate
POSITIONS = (0.15, 0.3, 0.45, 0.6, 0.75, 0.88)
_sem = threading.Semaphore(1)     # one ffmpeg at a time (Pi Zero)


class FrameError(Exception):
    pass


def available():
    return bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def version():
    if not available():
        return ""
    try:
        out = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True, timeout=10).stdout
        return (out.splitlines() or [""])[0].replace("ffmpeg version ", "").split(" ")[0]
    except (OSError, subprocess.SubprocessError):
        return ""


def duration(path):
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                             capture_output=True, text=True, timeout=60).stdout.strip()
        return float(out.split()[0])
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        raise FrameError(_("The video length cannot be read (is the file complete?)."))


def _run(args, timeout=120):
    try:
        p = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin"] + args,
                           capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise FrameError(_("Reading the frame took too long."))
    except OSError:
        raise FrameError(_("ffmpeg is not installed – add it with fix.sh → Additional modules."))
    return p.stdout


def score(path, t):
    """Contrast of a tiny grayscale frame: black screens, fades and flat titles score low."""
    raw = _run(["-ss", "%.2f" % t, "-i", path, "-frames:v", "1", "-vf",
                "scale=%d:%d,format=gray" % (SAMPLE_W, SAMPLE_H), "-f", "rawvideo", "-"], 90)
    if len(raw) < SAMPLE_W * SAMPLE_H:
        return -1.0
    px = raw[:SAMPLE_W * SAMPLE_H]
    mean = sum(px) / len(px)
    var = sum((p - mean) ** 2 for p in px) / len(px)
    penalty = 0.2 if mean < 25 or mean > 235 else 1.0     # almost black / almost white
    return (var ** 0.5) * penalty


def poster(path, t):
    """JPEG 400×600: the frame on a blurred, darker copy of itself."""
    vf = ("split[a][b];[a]scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d,boxblur=18:2,"
          "eq=brightness=-0.12[bg];[b]scale=%d:-2[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2") % (W, H, W, H, W)
    data = _run(["-ss", "%.2f" % t, "-i", path, "-frames:v", "1", "-filter_complex", vf,
                 "-q:v", "4", "-f", "image2", "-c:v", "mjpeg", "-"], 120)
    if data[:3] != b"\xff\xd8\xff":
        raise FrameError(_("No frame could be read from this file."))
    return data


def _times(path, n, shuffle):
    d = duration(path)
    if d <= 1:
        return [0.0]
    pos = list(POSITIONS)
    if shuffle:
        pos = sorted(random.uniform(0.08, 0.92) for _ in range(max(n, 1)))
    return [round(d * p, 2) for p in pos[:n]]


def best(path):
    """Automatic poster: the most detailed of several frames."""
    if not available():
        raise FrameError(_("ffmpeg is not installed – add it with fix.sh → Additional modules."))
    with _sem:
        times = _times(path, 4, False)
        scored = sorted(((score(path, t), t) for t in times), reverse=True)
        return poster(path, scored[0][1])


def candidates(path, n=6, shuffle=False):
    """Several posters to choose from in the Edit window: [(time, jpeg), …], best first."""
    if not available():
        raise FrameError(_("ffmpeg is not installed – add it with fix.sh → Additional modules."))
    n = max(1, min(8, int(n)))
    with _sem:
        times = _times(path, n, shuffle)
        out = []
        for t in times:
            try:
                out.append((score(path, t), t, poster(path, t)))
            except FrameError:
                continue
    if not out:
        raise FrameError(_("No frame could be read from this file."))
    out.sort(key=lambda x: -x[0])
    return [(t, data) for _s, t, data in out]


def first_video(path, is_video):
    """The video to take frames from: the file itself or the first (largest) video in the folder."""
    if os.path.isfile(path):
        return path
    best_f, best_size = None, -1
    for root, dirs, files in os.walk(path):
        dirs[:] = sorted(x for x in dirs if not x.startswith("."))
        for f in files:
            if f.startswith(".") or not is_video(f):
                continue
            rel = os.path.relpath(root, path).lower()
            if any(p in ("trailers", "featurettes", "extras", "behind the scenes", "deleted scenes")
                   for p in rel.split(os.sep)):
                continue
            try:
                size = os.path.getsize(os.path.join(root, f))
            except OSError:
                continue
            if size > best_size:
                best_f, best_size = os.path.join(root, f), size
    if not best_f:
        raise FrameError(_("There is no video file in this folder."))
    return best_f
