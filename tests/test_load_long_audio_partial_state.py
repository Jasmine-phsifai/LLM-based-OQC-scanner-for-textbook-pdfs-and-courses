"""Bounded loading of one optional long-audio partial state."""

from __future__ import annotations

import importlib
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
from ocrllm.errors import ResumeStateError


loader = importlib.import_module("ocrllm.audio.load_long_audio_partial_state")


def _state() -> LongAudioPartialState:
    return LongAudioPartialState(
        state_version=LONG_AUDIO_PARTIAL_STATE_VERSION,
        identity_version=LONG_AUDIO_REQUEST_IDENTITY_VERSION,
        request_fingerprints=("1" * 64,),
    )


def test_absent_state_returns_none_and_valid_state_round_trips(tmp_path: Path) -> None:
    state_path = tmp_path / "audio.ocrllm-state.json"

    assert loader.load_long_audio_partial_state(state_path) is None

    state_path.write_bytes(serialize_long_audio_partial_state(_state()))
    assert loader.load_long_audio_partial_state(state_path) == _state()


@pytest.mark.parametrize("kind", ["directory", "oversized", "corrupt"])
def test_invalid_state_file_is_a_typed_failure(
    tmp_path: Path,
    monkeypatch,
    kind: str,
) -> None:
    state_path = tmp_path / "audio.ocrllm-state.json"
    if kind == "directory":
        state_path.mkdir()
    elif kind == "oversized":
        monkeypatch.setattr(loader, "_MAX_STATE_BYTES", 8)
        state_path.write_bytes(b"123456789")
    else:
        state_path.write_bytes(b"{}")

    with pytest.raises(ResumeStateError) as caught:
        loader.load_long_audio_partial_state(state_path)

    assert caught.value.code == "RESUME_STATE_INVALID"


def test_actual_read_limit_rejects_growth_after_stat(
    tmp_path: Path,
    monkeypatch,
) -> None:
    state_path = tmp_path / "audio.ocrllm-state.json"
    state_path.write_bytes(b"12345678")
    real_open = Path.open
    monkeypatch.setattr(loader, "_MAX_STATE_BYTES", 8)

    class GrowingReader:
        def __init__(self, wrapped) -> None:
            self.wrapped = wrapped

        def __getattr__(self, name):
            return getattr(self.wrapped, name)

        def read(self, size: int = -1) -> bytes:
            assert size == 9
            return b"123456789"

    def grow_after_stat(path: Path, *args, **kwargs):
        opened = real_open(path, *args, **kwargs)
        mode = args[0] if args else kwargs.get("mode", "r")
        return GrowingReader(opened) if path == state_path and mode == "rb" else opened

    monkeypatch.setattr(Path, "open", grow_after_stat)

    with pytest.raises(ResumeStateError) as caught:
        loader.load_long_audio_partial_state(state_path)

    assert caught.value.code == "RESUME_STATE_INVALID"


def test_read_and_close_failures_are_redacted_without_losing_primary_fact(
    tmp_path: Path,
    monkeypatch,
) -> None:
    state_path = tmp_path / "audio.ocrllm-state.json"
    state_path.write_bytes(b"{}")
    read_secret = "audio-state-read-secret-319"
    close_secret = "audio-state-close-secret-319"
    install_close_failing_stream(
        monkeypatch,
        matches=lambda path, mode: path == state_path and mode == "rb",
        read_error=OSError(read_secret),
        close_error=OSError(close_secret),
    )

    with pytest.raises(ResumeStateError) as caught:
        loader.load_long_audio_partial_state(state_path)

    rendered = "".join(
        traceback.format_exception(type(caught.value), caught.value, caught.value.__traceback__)
    )
    assert caught.value.code == "RESUME_STATE_INVALID"
    assert caught.value.details["state_stream_cleanup_failed"] is True
    assert read_secret not in rendered
    assert close_secret not in rendered


def test_close_only_failure_is_typed_and_redacted(
    tmp_path: Path,
    monkeypatch,
) -> None:
    state_path = tmp_path / "audio.ocrllm-state.json"
    state_path.write_bytes(serialize_long_audio_partial_state(_state()))
    secret = "audio-state-close-only-secret-319"
    install_close_failing_stream(
        monkeypatch,
        matches=lambda path, mode: path == state_path and mode == "rb",
        close_error=OSError(secret),
    )

    with pytest.raises(ResumeStateError) as caught:
        loader.load_long_audio_partial_state(state_path)

    assert caught.value.code == "RESUME_STATE_INVALID"
    assert secret not in str(caught.value)


def test_read_process_control_remains_primary_when_close_also_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    state_path = tmp_path / "audio.ocrllm-state.json"
    state_path.write_bytes(b"{}")
    control = KeyboardInterrupt("primary audio state process control")
    install_close_failing_stream(
        monkeypatch,
        matches=lambda path, mode: path == state_path and mode == "rb",
        read_error=control,
        close_error=OSError("secondary close secret"),
    )

    with pytest.raises(KeyboardInterrupt) as caught:
        loader.load_long_audio_partial_state(state_path)

    assert caught.value is control


def test_read_primary_is_not_replaced_by_cleanup_process_control(
    tmp_path: Path,
    monkeypatch,
) -> None:
    state_path = tmp_path / "audio.ocrllm-state.json"
    state_path.write_bytes(b"{}")
    primary = RuntimeError("primary audio state read failure")
    install_close_failing_stream(
        monkeypatch,
        matches=lambda path, mode: path == state_path and mode == "rb",
        read_error=primary,
        close_error=KeyboardInterrupt("secondary close process control"),
    )

    with pytest.raises(RuntimeError) as caught:
        loader.load_long_audio_partial_state(state_path)

    assert caught.value is primary


def test_close_only_process_control_propagates(
    tmp_path: Path,
    monkeypatch,
) -> None:
    state_path = tmp_path / "audio.ocrllm-state.json"
    state_path.write_bytes(serialize_long_audio_partial_state(_state()))
    control = SystemExit("audio state close process control")
    install_close_failing_stream(
        monkeypatch,
        matches=lambda path, mode: path == state_path and mode == "rb",
        close_error=control,
    )

    with pytest.raises(SystemExit) as caught:
        loader.load_long_audio_partial_state(state_path)

    assert caught.value is control
