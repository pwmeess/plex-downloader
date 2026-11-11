"""First-run wizard helpers: mounted disks, folder checks, folder creation."""
import os

from i18n import _

# file systems that are never a media library
_SKIP_FS = {"proc", "sysfs", "tmpfs", "devtmpfs", "devpts", "cgroup", "cgroup2", "securityfs", "pstore",
            "debugfs", "tracefs", "configfs", "fusectl", "mqueue", "hugetlbfs", "bpf", "autofs", "rpc_pipefs",
            "binfmt_misc", "ramfs", "squashfs", "overlay", "nsfs", "efivarfs", "fuse.gvfsd-fuse", "fuse.portal"}
_SKIP_PREFIX = ("/proc", "/sys", "/dev", "/run", "/boot", "/snap", "/var/lib/docker", "/tmp")
NETWORK_FS = {"cifs", "smb3", "smbfs", "nfs", "nfs4", "fuse.sshfs"}
# folders that may never be created or used as a library
_FORBIDDEN = ("/bin", "/boot", "/dev", "/etc", "/lib", "/proc", "/root", "/run", "/sbin", "/sys", "/usr", "/var")


def _unescape(path):
    # /proc/mounts encodes spaces etc. as octal: "Plex\0401T" → "Plex 1T"
    return path.replace("\\040", " ").replace("\\011", "\t").replace("\\012", "\n").replace("\\134", "\\")


def _space(path):
    try:
        st = os.statvfs(path)
        return st.f_blocks * st.f_frsize, st.f_bavail * st.f_frsize
    except OSError:
        return None, None


def home_dir():
    return os.path.expanduser("~")


def mounts(proc=None):
    """Mounted file systems that can hold a library.
    Returns [{mount, device, fs, network, root, total, free}] – the SD card (/) first."""
    proc = proc or os.environ.get("PLEXDL_MOUNTS") or "/proc/mounts"   # PLEXDL_MOUNTS: tests only
    out, seen = [], set()
    try:
        with open(proc, encoding="utf-8") as f:
            lines = f.read().splitlines()
    except OSError:
        lines = []
    for line in lines:
        parts = line.split()
        if len(parts) < 3:
            continue
        dev, mnt, fs = _unescape(parts[0]), _unescape(parts[1]), parts[2]
        if fs in _SKIP_FS or mnt in seen:
            continue
        if mnt != "/" and mnt.startswith(_SKIP_PREFIX):
            continue
        total, free = _space(mnt)
        if not total:
            continue
        seen.add(mnt)
        out.append({"mount": mnt, "device": dev, "fs": fs, "network": fs in NETWORK_FS,
                    "root": mnt == "/", "total": total, "free": free})
    out.sort(key=lambda m: (not m["root"], m["network"], m["mount"]))
    return out


def allowed(path, mount_points=None):
    """A library folder must be absolute, outside system folders, and on a mounted disk
    or in the user's home folder (SD-card setup)."""
    path = os.path.normpath(path or "")
    if not path.startswith("/") or path == "/" or ".." in path.split("/"):
        return False
    home = home_dir()
    if path == home or path.startswith(home.rstrip("/") + "/"):
        return True
    if any(path == p or path.startswith(p + "/") for p in _FORBIDDEN):
        return False
    points = mount_points if mount_points is not None else [m["mount"] for m in mounts() if not m["root"]]
    return any(path == m or path.startswith(m.rstrip("/") + "/") for m in points)


def check(paths):
    """[{path, exists, writable, free, problem}] for each folder."""
    res = []
    for p in paths:
        p = (p or "").strip()
        info = {"path": p, "exists": False, "writable": False, "free": None, "problem": ""}
        if not p:
            res.append(info)
            continue
        if not allowed(p):
            info["problem"] = _("This folder cannot be used for the library.")
        elif os.path.isdir(p):
            info["exists"] = True
            info["writable"] = os.access(p, os.W_OK | os.X_OK)
            info["free"] = _space(p)[1]
            if not info["writable"]:
                info["problem"] = _("no write permission:")
        else:
            info["problem"] = _("Folder does not exist")
        res.append(info)
    return res


def create(paths):
    """Creates missing folders (also parents). Returns (created, problems)."""
    created, problems = [], []
    for p in paths:
        p = (p or "").strip()
        if not p or os.path.isdir(p):
            continue
        if not allowed(p):
            problems.append("%s: %s" % (p, _("This folder cannot be used for the library.")))
            continue
        try:
            os.makedirs(p, mode=0o775, exist_ok=True)
            created.append(p)
        except OSError as e:
            problems.append("%s: %s" % (p, e.strerror or e))
    return created, problems
