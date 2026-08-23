"""Prove atomic Markdown stream lifecycle and error precedence."""

from __future__ import annotations

import traceback
from pathlib import Path

import pytest

from ocrllm import OutputError
from ocrllm.output.write_markdown_atomically import write_markdown_atomically
from install_close_failing_stream import install_close_failing_stream


def _install_temporary_stream_close_failure(
    monkeypatch,
    *,
    output_dir: Path,
    close_error: BaseException,
    write_error: BaseException | None = None,
) -> None:
    install_close_failing_stream(
        monkeypatch,
        matches=lambda path, mode: (
            path.parent == output_dir
            and path.name.startswith(".ocrllm-")
            and path.suffix == ".tmp"
            and mode == "x"
        ),
        close_error=close_error,
        write_error=write_error,
    )


def _assert_old_target_and_no_temporary(target: Path) -> None:
    assert target.read_text(encoding="utf-8") == "durable old content"
    assert list(target.parent.glob(".ocrllm-*.tmp")) == []


def test_markdown_close_only_failure_is_typed_and_redacted(
    tmp_path,
    monkeypatch,
) -> None:
    target = tmp_path / "result.md"
    target.write_text("durable old content", encoding="utf-8")
    secret = "markdown-close-secret-9164"
    _install_temporary_stream_close_failure(
        monkeypatch,
        output_dir=tmp_path,
        close_error=OSError(secret),
    )

    with pytest.raises(OutputError) as caught:
        write_markdown_atomically(target, "# Replacement\n", overwrite=True)

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
    _assert_old_target_and_no_temporary(target)


@pytest.mark.parametrize("primary_kind", ["typed", "ordinary", "keyboard_interrupt"])
def test_markdown_close_failure_does_not_replace_write_primary(
    tmp_path,
    monkeypatch,
    primary_kind,
) -> None:
    target = tmp_path / "result.md"
    target.write_text("durable old content", encoding="utf-8")
    if primary_kind == "typed":
        primary = OutputError("primary output failure", code="OUTPUT_PATH_INVALID")
    elif primary_kind == "ordinary":
        primary = RuntimeError("primary ordinary failure")
    else:
        primary = KeyboardInterrupt("primary output process control")
    _install_temporary_stream_close_failure(
        monkeypatch,
        output_dir=tmp_path,
        write_error=primary,
        close_error=OSError("secondary-markdown-close-secret-8243"),
    )

    with pytest.raises(type(primary)) as caught:
        write_markdown_atomically(target, "# Replacement\n", overwrite=True)

    assert caught.value is primary
    if isinstance(primary, OutputError):
        assert primary.details["markdown_stream_cleanup_failed"] is True
    _assert_old_target_and_no_temporary(target)


def test_markdown_close_process_control_propagates(
    tmp_path,
    monkeypatch,
) -> None:
    target = tmp_path / "result.md"
    target.write_text("durable old content", encoding="utf-8")
    control = SystemExit("Markdown close process control")
    _install_temporary_stream_close_failure(
        monkeypatch,
        output_dir=tmp_path,
        close_error=control,
    )

    with pytest.raises(SystemExit) as caught:
        write_markdown_atomically(target, "# Replacement\n", overwrite=True)

    assert caught.value is control
    _assert_old_target_and_no_temporary(target)
