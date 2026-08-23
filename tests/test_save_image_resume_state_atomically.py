"""Prove atomic image resume-state stream lifecycle and error precedence."""

from __future__ import annotations

import traceback
from pathlib import Path

import pytest

from ocrllm import OutputError
from ocrllm.output import save_image_resume_state_atomically as saver
from install_close_failing_stream import install_close_failing_stream


def _install_state_stream_close_failure(
    monkeypatch,
    *,
    state_dir: Path,
    close_error: BaseException,
    write_error: BaseException | None = None,
) -> None:
    install_close_failing_stream(
        monkeypatch,
        matches=lambda path, mode: (
            path.parent == state_dir
            and path.name.startswith(".ocrllm-")
            and path.suffix == ".tmp"
            and mode == "xb"
        ),
        close_error=close_error,
        write_error=write_error,
    )


def _save_test_state(monkeypatch, state_path: Path) -> None:
    monkeypatch.setattr(saver, "serialize_image_resume_state", lambda _state: b"state")
    saver.save_image_resume_state_atomically(state_path, object())


def _assert_old_state_and_no_temporary(state_path: Path) -> None:
    assert state_path.read_bytes() == b"durable old state"
    assert list(state_path.parent.glob(".ocrllm-*.tmp")) == []


def test_state_close_only_failure_is_typed_and_redacted(
    tmp_path,
    monkeypatch,
) -> None:
    state_path = tmp_path / "result.ocrllm-state.json"
    state_path.write_bytes(b"durable old state")
    secret = "state-close-secret-4827"
    _install_state_stream_close_failure(
        monkeypatch,
        state_dir=tmp_path,
        close_error=OSError(secret),
    )

    with pytest.raises(OutputError) as caught:
        _save_test_state(monkeypatch, state_path)

    assert caught.value.code == "OUTPUT_WRITE_FAILED"
    rendered = "".join(
        traceback.format_exception(
            type(caught.value),
            caught.value,
            caught.value.__traceback__,
        )
    )
    assert secret not in rendered
    assert secret not in str(caught.value)
    assert secret not in repr(caught.value.details)
    _assert_old_state_and_no_temporary(state_path)


@pytest.mark.parametrize("primary_kind", ["typed", "ordinary", "keyboard_interrupt"])
def test_state_close_failure_does_not_replace_write_primary(
    tmp_path,
    monkeypatch,
    primary_kind,
) -> None:
    state_path = tmp_path / "result.ocrllm-state.json"
    state_path.write_bytes(b"durable old state")
    if primary_kind == "typed":
        primary = OutputError("primary state failure", code="OUTPUT_PATH_INVALID")
    elif primary_kind == "ordinary":
        primary = RuntimeError("primary ordinary state failure")
    else:
        primary = KeyboardInterrupt("primary state process control")
    _install_state_stream_close_failure(
        monkeypatch,
        state_dir=tmp_path,
        write_error=primary,
        close_error=OSError("secondary-state-close-secret-6351"),
    )

    with pytest.raises(type(primary)) as caught:
        _save_test_state(monkeypatch, state_path)

    assert caught.value is primary
    if isinstance(primary, OutputError):
        assert primary.details["state_stream_cleanup_failed"] is True
    _assert_old_state_and_no_temporary(state_path)


def test_state_close_process_control_propagates(tmp_path, monkeypatch) -> None:
    state_path = tmp_path / "result.ocrllm-state.json"
    state_path.write_bytes(b"durable old state")
    control = SystemExit("state close process control")
    _install_state_stream_close_failure(
        monkeypatch,
        state_dir=tmp_path,
        close_error=control,
    )

    with pytest.raises(SystemExit) as caught:
        _save_test_state(monkeypatch, state_path)

    assert caught.value is control
    _assert_old_state_and_no_temporary(state_path)
