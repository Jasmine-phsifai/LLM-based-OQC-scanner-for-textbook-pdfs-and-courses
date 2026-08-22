import runpy
import subprocess
import sys
from pathlib import Path
from types import ModuleType


def test_importing_bilibili_diagnostic_does_not_start_network_work(monkeypatch):
    class ForbiddenSession:
        def __init__(self, *args, **kwargs):
            raise AssertionError("import constructed a Bilibili HTTP session")

    fake_requests = ModuleType("curl_cffi.requests")
    fake_requests.Session = ForbiddenSession  # type: ignore[attr-defined]
    fake_package = ModuleType("curl_cffi")
    fake_package.requests = fake_requests  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "curl_cffi", fake_package)
    monkeypatch.setitem(sys.modules, "curl_cffi.requests", fake_requests)

    def forbid_subprocess(*args, **kwargs):
        raise AssertionError("import started a Bilibili curl subprocess")

    monkeypatch.setattr(subprocess, "run", forbid_subprocess)

    diagnostic = Path(__file__).with_name("diagnose_bilibili_api.py")
    runpy.run_path(str(diagnostic), run_name="bilibili_import_probe")
