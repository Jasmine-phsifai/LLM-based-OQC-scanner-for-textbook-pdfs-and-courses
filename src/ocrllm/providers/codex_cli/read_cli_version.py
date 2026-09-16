"""Read the selected CLI's actual version once per binary revision."""
from pathlib import Path
import re
import subprocess
from threading import Lock

_LOCK = Lock()
_CACHE = {}
_VERSION = re.compile(r"^(?:codex-cli|codex) ([A-Za-z0-9][A-Za-z0-9.+_-]{0,100})$")


def read_cli_version(binary):
    """Unknown stays None; --version is not a model attempt or private session."""
    try:
        path = Path(binary).resolve()
        info = path.stat()
    except OSError:
        return None
    key = (str(path), info.st_mtime_ns, info.st_size)
    with _LOCK:
        if key in _CACHE:
            return _CACHE[key]
        version = None
        try:
            result = subprocess.run([str(path), "--version"], capture_output=True, text=True,
                                    encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL,
                                    timeout=3.0, check=False,
                                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            matched = _VERSION.fullmatch(result.stdout.strip()) if result.returncode == 0 else None
            if matched:
                version = matched.group(1)
        except (OSError, subprocess.TimeoutExpired):
            pass
        _CACHE[key] = version
        return version
