"""Prove bounded final-output validation and close-error precedence."""

from __future__ import annotations

import hashlib
import traceback
from pathlib import Path

import pytest

from ocrllm import ResumeStateError
from ocrllm.contracts.source_fingerprint import SourceFingerprint
from ocrllm.fingerprint_image_request import IMAGE_REQUEST_IDENTITY_VERSION
from ocrllm.image_resume_state import IMAGE_RESUME_STATE_VERSION, ImageResumeState
from ocrllm.output.validate_image_resume_output import validate_image_resume_output
from install_close_failing_stream import install_close_failing_stream


_MARKDOWN = "# 已保存\n"


def _completed_state() -> ImageResumeState:
    return ImageResumeState(
        state_version=IMAGE_RESUME_STATE_VERSION,
        identity_version=IMAGE_REQUEST_IDENTITY_VERSION,
        request_fingerprint="0" * 64,
        processor_name="test.image",
        processor_version="test.image.v1",
        sources=(
            SourceFingerprint(
                uri="file:///test.png",
                byte_size=1,
                sha256="1" * 64,
            ),
        ),
        markdown=_MARKDOWN,
        media_type="image",
        profile="board",
        status="complete",
        hotwords=(),
        warnings=(),
        final_markdown_sha256=hashlib.sha256(
            _MARKDOWN.encode("utf-8")
        ).hexdigest(),
    )


def _install_output_stream_close_failure(
    monkeypatch,
    *,
    output_path: Path,
    close_error: BaseException,
    read_error: BaseException | None = None,
) -> None:
    install_close_failing_stream(
        monkeypatch,
        matches=lambda path, mode: Path(path) == output_path and mode == "rb",
        close_error=close_error,
        read_error=read_error,
    )


def test_resume_output_close_only_failure_is_typed_and_redacted(
    tmp_path,
    monkeypatch,
) -> None:
    output_path = tmp_path / "result.md"
    output_path.write_text(_MARKDOWN, encoding="utf-8")
    secret = "resume-output-close-secret-3762"
    _install_output_stream_close_failure(
        monkeypatch,
        output_path=output_path,
        close_error=OSError(secret),
    )

    with pytest.raises(ResumeStateError) as caught:
        validate_image_resume_output(output_path, _completed_state())

    assert caught.value.code == "RESUME_STATE_MISMATCH"
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
def test_resume_output_close_failure_does_not_replace_read_primary(
    tmp_path,
    monkeypatch,
    primary_kind,
) -> None:
    output_path = tmp_path / "result.md"
    output_path.write_text(_MARKDOWN, encoding="utf-8")
    if primary_kind == "typed":
        primary = ResumeStateError(
            "primary resume output failure",
            code="RESUME_STATE_MISMATCH",
        )
    elif primary_kind == "ordinary":
        primary = RuntimeError("primary ordinary resume output failure")
    elif primary_kind == "memory_error":
        primary = MemoryError("primary resume output memory failure")
    else:
        primary = KeyboardInterrupt("primary resume output process control")
    _install_output_stream_close_failure(
        monkeypatch,
        output_path=output_path,
        read_error=primary,
        close_error=OSError("secondary-resume-output-close-secret-4918"),
    )

    expected_type = (
        ResumeStateError if isinstance(primary, MemoryError) else type(primary)
    )
    with pytest.raises(expected_type) as caught:
        validate_image_resume_output(output_path, _completed_state())

    if isinstance(primary, MemoryError):
        assert caught.value.code == "RESUME_STATE_MISMATCH"
        assert caught.value.details["resume_output_stream_cleanup_failed"] is True
    else:
        assert caught.value is primary
        if isinstance(primary, ResumeStateError):
            assert primary.details["resume_output_stream_cleanup_failed"] is True


def test_resume_output_close_process_control_propagates(tmp_path, monkeypatch) -> None:
    output_path = tmp_path / "result.md"
    output_path.write_text(_MARKDOWN, encoding="utf-8")
    control = SystemExit("resume output close process control")
    _install_output_stream_close_failure(
        monkeypatch,
        output_path=output_path,
        close_error=control,
    )

    with pytest.raises(SystemExit) as caught:
        validate_image_resume_output(output_path, _completed_state())

    assert caught.value is control
