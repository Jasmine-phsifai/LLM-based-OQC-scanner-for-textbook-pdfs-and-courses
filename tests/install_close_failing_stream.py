"""Install one deterministic file-stream close failure for tests."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path


def install_close_failing_stream(
    monkeypatch,
    *,
    matches: Callable[[Path, str], bool],
    close_error: BaseException,
    read_error: BaseException | None = None,
    write_error: BaseException | None = None,
) -> None:
    """Wrap the matching stream with requested read, write, and close failures."""

    original_open = Path.open

    class CloseFailingStream:
        def __init__(self, wrapped) -> None:
            self.wrapped = wrapped

        def __getattr__(self, name):
            return getattr(self.wrapped, name)

        def read(self, size=-1):
            if read_error is not None:
                raise read_error
            return self.wrapped.read(size)

        def write(self, data):
            if write_error is not None:
                raise write_error
            return self.wrapped.write(data)

        def close(self) -> None:
            self.wrapped.close()
            raise close_error

    def wrap_opened_stream(path, *args, **kwargs):
        opened = original_open(path, *args, **kwargs)
        mode = args[0] if args else kwargs.get("mode", "r")
        return CloseFailingStream(opened) if matches(path, mode) else opened

    monkeypatch.setattr(Path, "open", wrap_opened_stream)
