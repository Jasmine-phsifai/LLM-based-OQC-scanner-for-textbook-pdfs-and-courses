"""Atomic publication of one validated long-audio partial state."""

from __future__ import annotations

import importlib
import os
import traceback
from pathlib import Path

import pytest

from install_close_failing_stream import install_close_failing_stream
from ocrllm.audio.fingerprint_long_audio_request import (
    LONG_AUDIO_REQUEST_IDENTITY_VERSION,
)
from ocrllm.audio.long_audio_partial_state import (
    LONG_AUDIO_PARTIAL_STATE_VERSION,
    LongAudioPartialState,
)
from ocrllm.audio.serialize_long_audio_partial_state import (
    serialize_long_audio_partial_state,
)
from ocrllm.errors import OutputError


saver = importlib.import_module("ocrllm.audio.save_long_audio_partial_state_atomically")


def _state() -> LongAudioPartialState:
    return LongAudioPartialState(
        state_version=LONG_AUDIO_PARTIAL_STATE_VERSION,
        identity_version=LONG_AUDIO_REQUEST_IDENTITY_VERSION,
        mode="whole",
        interval_minutes=None,
        request_fingerprints=("1" * 64,),
    )


def test_save_replaces_old_state_only_after_complete_sibling_write(
    tmp_path: Path,
    monkeypatch,
) -> None:
    state_path = tmp_path / "audio.ocrllm-state.json"
    state_path.write_bytes(b"durable old state")
    expected = serialize_long_audio_partial_state(_state())
    real_replace = saver.os.replace
    inspected = False

    def inspect_then_replace(temporary_path: Path, target_path: Path) -> None:
        nonlocal inspected
        inspected = True
        assert target_path == state_path
        assert temporary_path.parent == state_path.parent
        assert temporary_path.name.startswith(".ocrllm-")
        assert temporary_path.suffix == ".tmp"
        assert state_path.read_bytes() == b"durable old state"
        assert temporary_path.read_bytes() == expected
        real_replace(temporary_path, target_path)

    monkeypatch.setattr(saver.os, "replace", inspect_then_replace)

    saver.save_long_audio_partial_state_atomically(state_path, _state())

    assert inspected is True
    assert state_path.read_bytes() == expected
    assert list(tmp_path.glob(".ocrllm-*.tmp")) == []


def test_short_write_preserves_old_state_and_cleans_temporary_file(
    tmp_path: Path,
    monkeypatch,
) -> None:
    state_path = tmp_path / "audio.ocrllm-state.json"
    state_path.write_bytes(b"durable old state")
    real_open = Path.open

    class ShortWriter:
        def __init__(self, wrapped) -> None:
            self.wrapped = wrapped

        def __getattr__(self, name):
            return getattr(self.wrapped, name)

        def write(self, data: bytes) -> int:
            self.wrapped.write(data[:-1])
            return len(data) - 1

    def short_write_temporary(path: Path, *args, **kwargs):
        opened = real_open(path, *args, **kwargs)
        mode = args[0] if args else kwargs.get("mode", "r")
        if path.parent == tmp_path and path.name.startswith(".ocrllm-") and mode == "xb":
            return ShortWriter(opened)
        return opened

    monkeypatch.setattr(Path, "open", short_write_temporary)

    with pytest.raises(OutputError) as caught:
        saver.save_long_audio_partial_state_atomically(state_path, _state())

    assert caught.value.code == "OUTPUT_WRITE_FAILED"
    assert state_path.read_bytes() == b"durable old state"
    assert list(tmp_path.glob(".ocrllm-*.tmp")) == []


def test_replace_failure_is_redacted_and_preserves_old_state(
    tmp_path: Path,
    monkeypatch,
) -> None:
    state_path = tmp_path / "audio.ocrllm-state.json"
    state_path.write_bytes(b"durable old state")
    secret = "audio-state-replace-secret-319"

    def fail_replace(_temporary_path: Path, _state_path: Path) -> None:
        raise OSError(secret)

    monkeypatch.setattr(saver.os, "replace", fail_replace)

    with pytest.raises(OutputError) as caught:
        saver.save_long_audio_partial_state_atomically(state_path, _state())

    rendered = "".join(
        traceback.format_exception(type(caught.value), caught.value, caught.value.__traceback__)
    )
    assert caught.value.code == "OUTPUT_WRITE_FAILED"
    assert secret not in rendered
    assert state_path.read_bytes() == b"durable old state"
    assert list(tmp_path.glob(".ocrllm-*.tmp")) == []


def test_temporary_cleanup_failure_marks_the_primary_typed_error(
    tmp_path: Path,
    monkeypatch,
) -> None:
    state_path = tmp_path / "audio.ocrllm-state.json"
    state_path.write_bytes(b"durable old state")
    registered: list[Path] = []
    real_unlink = Path.unlink

    def fail_replace(_temporary_path: Path, _state_path: Path) -> None:
        raise OSError("primary replace failure")

    def deny_temporary_cleanup(path: Path, *args, **kwargs) -> None:
        if path.parent == tmp_path and path.name.startswith(".ocrllm-"):
            raise PermissionError("secondary cleanup failure")
        real_unlink(path, *args, **kwargs)

    def record_exit_cleanup(_callback, path: Path) -> None:
        registered.append(path)

    monkeypatch.setattr(saver.os, "replace", fail_replace)
    monkeypatch.setattr(Path, "unlink", deny_temporary_cleanup)
    monkeypatch.setattr(saver.atexit, "register", record_exit_cleanup)

    with pytest.raises(OutputError) as caught:
        saver.save_long_audio_partial_state_atomically(state_path, _state())

    assert caught.value.code == "OUTPUT_WRITE_FAILED"
    assert caught.value.details["state_file_cleanup_failed"] is True
    assert state_path.read_bytes() == b"durable old state"
    assert len(registered) == 1
    assert registered[0].parent == tmp_path


def test_fsync_failure_is_redacted_and_preserves_old_state(
    tmp_path: Path,
    monkeypatch,
) -> None:
    state_path = tmp_path / "audio.ocrllm-state.json"
    state_path.write_bytes(b"durable old state")
    secret = "audio-state-fsync-secret-319"

    def fail_fsync(_descriptor: int) -> None:
        raise OSError(secret)

    monkeypatch.setattr(saver.os, "fsync", fail_fsync)

    with pytest.raises(OutputError) as caught:
        saver.save_long_audio_partial_state_atomically(state_path, _state())

    assert caught.value.code == "OUTPUT_WRITE_FAILED"
    assert secret not in str(caught.value)
    assert state_path.read_bytes() == b"durable old state"
    assert list(tmp_path.glob(".ocrllm-*.tmp")) == []


def test_close_only_failure_is_typed_redacted_and_preserves_old_state(
    tmp_path: Path,
    monkeypatch,
) -> None:
    state_path = tmp_path / "audio.ocrllm-state.json"
    state_path.write_bytes(b"durable old state")
    secret = "audio-state-close-secret-319"
    install_close_failing_stream(
        monkeypatch,
        matches=lambda path, mode: path.parent == tmp_path and mode == "xb",
        close_error=OSError(secret),
    )

    with pytest.raises(OutputError) as caught:
        saver.save_long_audio_partial_state_atomically(state_path, _state())

    assert caught.value.code == "OUTPUT_WRITE_FAILED"
    assert secret not in str(caught.value)
    assert state_path.read_bytes() == b"durable old state"
    assert list(tmp_path.glob(".ocrllm-*.tmp")) == []


def test_oversized_serialized_state_is_rejected_before_open(
    tmp_path: Path,
    monkeypatch,
) -> None:
    state_path = tmp_path / "audio.ocrllm-state.json"
    state_path.write_bytes(b"durable old state")
    monkeypatch.setattr(saver, "_MAX_STATE_BYTES", 8)
    monkeypatch.setattr(saver, "serialize_long_audio_partial_state", lambda _state: b"123456789")

    with pytest.raises(OutputError) as caught:
        saver.save_long_audio_partial_state_atomically(state_path, _state())

    assert caught.value.code == "OUTPUT_WRITE_FAILED"
    assert state_path.read_bytes() == b"durable old state"
    assert list(tmp_path.glob(".ocrllm-*.tmp")) == []


def test_write_process_control_remains_primary_when_close_also_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    state_path = tmp_path / "audio.ocrllm-state.json"
    control = KeyboardInterrupt("primary audio state process control")
    install_close_failing_stream(
        monkeypatch,
        matches=lambda path, mode: path.parent == tmp_path and mode == "xb",
        write_error=control,
        close_error=OSError("secondary close secret"),
    )

    with pytest.raises(KeyboardInterrupt) as caught:
        saver.save_long_audio_partial_state_atomically(state_path, _state())

    assert caught.value is control
    assert not state_path.exists()
    assert list(tmp_path.glob(".ocrllm-*.tmp")) == []


def test_write_primary_is_not_replaced_by_cleanup_process_control(
    tmp_path: Path,
    monkeypatch,
) -> None:
    state_path = tmp_path / "audio.ocrllm-state.json"
    primary = RuntimeError("primary audio state write failure")
    install_close_failing_stream(
        monkeypatch,
        matches=lambda path, mode: path.parent == tmp_path and mode == "xb",
        write_error=primary,
        close_error=KeyboardInterrupt("secondary close process control"),
    )

    with pytest.raises(RuntimeError) as caught:
        saver.save_long_audio_partial_state_atomically(state_path, _state())

    assert caught.value is primary
    assert not state_path.exists()
    assert list(tmp_path.glob(".ocrllm-*.tmp")) == []


def test_close_only_process_control_propagates(
    tmp_path: Path,
    monkeypatch,
) -> None:
    state_path = tmp_path / "audio.ocrllm-state.json"
    control = SystemExit("audio state close process control")
    install_close_failing_stream(
        monkeypatch,
        matches=lambda path, mode: path.parent == tmp_path and mode == "xb",
        close_error=control,
    )

    with pytest.raises(SystemExit) as caught:
        saver.save_long_audio_partial_state_atomically(state_path, _state())

    assert caught.value is control
    assert not state_path.exists()
    assert list(tmp_path.glob(".ocrllm-*.tmp")) == []


@pytest.mark.skipif(os.name != "nt", reason="Windows legacy path-limit regression")
def test_sibling_temporary_does_not_amplify_near_limit_explicit_path(
    tmp_path: Path,
    monkeypatch,
) -> None:
    if _windows_path_units(tmp_path) >= 214:
        pytest.skip("pytest temporary root is already beyond the controlled path range")
    state_dir = _make_directory_with_windows_path_units(tmp_path, 214)
    state_path = state_dir / "audio.ocrllm-state.json"
    _enforce_legacy_windows_open_limit(monkeypatch)

    saver.save_long_audio_partial_state_atomically(state_path, _state())

    assert state_path.is_file()
    assert list(state_dir.glob(".ocrllm-*.tmp")) == []


def _windows_path_units(path: Path) -> int:
    return len(str(path).encode("utf-16-le")) // 2


def _make_directory_with_windows_path_units(base: Path, target_units: int) -> Path:
    current = base
    while _windows_path_units(current) < target_units:
        remaining = target_units - _windows_path_units(current) - 1
        if remaining < 1:
            raise AssertionError("target path length cannot be reached")
        current /= "d" * min(40, remaining)
    assert _windows_path_units(current) == target_units
    current.mkdir(parents=True)
    return current


def _enforce_legacy_windows_open_limit(monkeypatch) -> None:
    original_open = Path.open

    def open_with_legacy_limit(path: Path, *args, **kwargs):
        if _windows_path_units(path) > 259:
            raise OSError(206, "test-only simulated legacy Windows path limit", str(path))
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", open_with_legacy_limit)
