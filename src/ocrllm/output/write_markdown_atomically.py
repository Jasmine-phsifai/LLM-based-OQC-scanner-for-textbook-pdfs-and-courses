"""Atomically write one final Markdown file."""

from __future__ import annotations

import atexit
import os
from pathlib import Path
from uuid import uuid4

from ..errors import OCRLLMError, OutputError, OutputExists


def write_markdown_atomically(
    output_path: Path,
    markdown: str,
    *,
    overwrite: bool,
) -> None:
    """Durably publish Markdown without silently replacing an existing file."""
    temporary_path = output_path.with_name(f".ocrllm-{uuid4().hex}.tmp")
    try:
        stream = temporary_path.open("x", encoding="utf-8", newline="\n")
        primary_error: BaseException | None = None
        try:
            try:
                written_characters = stream.write(markdown)
                if written_characters != len(markdown):
                    raise OutputError(
                        "The requested Markdown output was not written completely.",
                        code="OUTPUT_WRITE_FAILED",
                    ) from None
                stream.flush()
                os.fsync(stream.fileno())
            except (OSError, ValueError) as error:
                raise OutputError(
                    "The requested Markdown output could not be written atomically.",
                    code="OUTPUT_WRITE_FAILED",
                ) from error
        except BaseException as error:
            primary_error = error
            raise
        finally:
            _close_markdown_stream(stream, primary_error=primary_error)

        if overwrite:
            os.replace(temporary_path, output_path)
        else:
            _publish_without_overwrite(temporary_path, output_path)
            try:
                temporary_path.unlink(missing_ok=True)
            except (OSError, ValueError):
                pass
    except (OutputError, OutputExists):
        raise
    except (OSError, ValueError) as error:
        raise OutputError(
            "The requested Markdown output could not be written atomically.",
            code="OUTPUT_WRITE_FAILED",
        ) from error
    finally:
        try:
            temporary_path.unlink(missing_ok=True)
        except (OSError, ValueError):
            atexit.register(_delete_temporary_path_at_exit, temporary_path)


def _close_markdown_stream(
    stream,
    *,
    primary_error: BaseException | None,
) -> None:
    """Close the Markdown stream without replacing an active failure."""

    try:
        stream.close()
    except (OSError, ValueError):
        if primary_error is None:
            raise OutputError(
                "The temporary Markdown output could not be closed safely.",
                code="OUTPUT_WRITE_FAILED",
            ) from None
        if isinstance(primary_error, OCRLLMError):
            primary_error._add_safe_detail("markdown_stream_cleanup_failed", True)


def _publish_without_overwrite(temporary_path: Path, output_path: Path) -> None:
    try:
        os.link(temporary_path, output_path)
        return
    except FileExistsError as error:
        raise OutputExists("The requested Markdown output already exists.") from error
    except OSError as link_error:
        if os.path.lexists(output_path):
            raise OutputExists("The requested Markdown output already exists.") from link_error
        if os.name != "nt":
            raise

    try:
        os.rename(temporary_path, output_path)
    except OSError as rename_error:
        if os.path.lexists(output_path):
            raise OutputExists("The requested Markdown output already exists.") from rename_error
        raise


def _delete_temporary_path_at_exit(temporary_path: Path) -> None:
    try:
        temporary_path.unlink(missing_ok=True)
    except (OSError, ValueError):
        pass
