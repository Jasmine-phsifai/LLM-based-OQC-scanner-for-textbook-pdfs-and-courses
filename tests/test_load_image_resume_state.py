"""Prove bounded image resume-state reads and close-error precedence."""

from __future__ import annotations

import importlib
import traceback
from pathlib import Path

import pytest

from ocrllm import ResumeStateError
from install_close_failing_stream import install_close_failing_stream


loader = importlib.import_module("ocrllm.output.load_image_resume_state")


def _install_state_read_close_failure(
    monkeypatch,
    *,
    state_path: Path,
    close_error: BaseException,
    read_error: BaseException | None = None,
) -> None:
    install_close_failing_stream(
        monkeypatch,
        matches=lambda path, mode: Path(path) == state_path and mode == "rb",
        close_error=close_error,
        read_error=read_error,
    )


def test_state_read_close_only_failure_is_typed_and_redacted(
    tmp_path,
    monkeypatch,
) -> None:
    state_path = tmp_path / "result.ocrllm-state.json"
    state_path.write_bytes(b"{}")
    secret = "state-read-close-secret-5928"
    _install_state_read_close_failure(
        monkeypatch,
        state_path=state_path,
        close_error=OSError(secret),
    )

    with pytest.raises(ResumeStateError) as caught:
        loader.load_image_resume_state(state_path)

    assert caught.value.code == "RESUME_STATE_INVALID"
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


@pytest.mark.parametrize(
    "primary_kind",
    ["typed", "ordinary", "memory_error", "keyboard_interrupt"],
)
def test_state_read_close_failure_does_not_replace_read_primary(
    tmp_path,
    monkeypatch,
    primary_kind,
) -> None:
    state_path = tmp_path / "result.ocrllm-state.json"
    state_path.write_bytes(b"{}")
    if primary_kind == "typed":
        primary = ResumeStateError(
            "primary resume state failure",
            code="RESUME_STATE_MISMATCH",
        )
    elif primary_kind == "ordinary":
        primary = RuntimeError("primary ordinary state read failure")
    elif primary_kind == "memory_error":
        primary = MemoryError("primary state read memory failure")
    else:
        primary = KeyboardInterrupt("primary state read process control")
    _install_state_read_close_failure(
        monkeypatch,
        state_path=state_path,
        read_error=primary,
        close_error=OSError("secondary-state-read-close-secret-7349"),
    )

    expected_type = (
        ResumeStateError if isinstance(primary, MemoryError) else type(primary)
    )
    with pytest.raises(expected_type) as caught:
        loader.load_image_resume_state(state_path)

    if isinstance(primary, MemoryError):
        assert caught.value.code == "RESUME_STATE_INVALID"
        assert caught.value.details["state_stream_cleanup_failed"] is True
    else:
        assert caught.value is primary
        if isinstance(primary, ResumeStateError):
            assert primary.details["state_stream_cleanup_failed"] is True


def test_state_read_close_process_control_propagates(tmp_path, monkeypatch) -> None:
    state_path = tmp_path / "result.ocrllm-state.json"
    state_path.write_bytes(b"{}")
    control = SystemExit("state read close process control")
    _install_state_read_close_failure(
        monkeypatch,
        state_path=state_path,
        close_error=control,
    )

    with pytest.raises(SystemExit) as caught:
        loader.load_image_resume_state(state_path)

    assert caught.value is control
