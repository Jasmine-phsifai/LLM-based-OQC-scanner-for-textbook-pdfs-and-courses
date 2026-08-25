"""Atomically publish one settled video result as Markdown."""

from __future__ import annotations

import os
from pathlib import Path

from .result import RecognitionResult
from .video_recognition_outcome import VideoRecognitionOutcome


def publish_video_result(
    outcome: VideoRecognitionOutcome,
    output_path: str | Path,
    *,
    overwrite: bool = False,
) -> RecognitionResult:
    """Compose and atomically publish one complete or partial video outcome."""
    from .build_recognition_result import build_recognition_result
    from .compose_video_result import compose_video_result
    from .output.claim_output_target import claim_output_target
    from .output.write_markdown_atomically import write_markdown_atomically
    from .processor_output import ProcessorOutput

    if type(overwrite) is not bool:
        raise TypeError(
            "publish_video_result() overwrite must be a boolean"
        ) from None

    composed = compose_video_result(outcome)
    try:
        target = Path(output_path)
    except TypeError:
        raise TypeError(
            "publish_video_result() output_path must be a path"
        ) from None
    _reject_reserved_video_media_target(
        target,
        reserved_paths=(
            *composed.assets,
            outcome.output_root / "audio.mp3",
        ),
    )

    with claim_output_target(target):
        _prepare_video_markdown_target(target, overwrite=overwrite)
        write_markdown_atomically(target, composed.markdown, overwrite=overwrite)
        return build_recognition_result(
            ProcessorOutput(
                media_type="video",
                markdown=composed.markdown,
                profile=composed.profile,
                status=composed.status,
                assets=composed.assets,
                hotwords=composed.hotwords,
                warnings=composed.warnings,
                metadata=composed.metadata,
            ),
            output_path=target,
        )


def _reject_reserved_video_media_target(
    target: Path,
    *,
    reserved_paths: tuple[Path, ...],
) -> None:
    from .errors import OutputError

    if target in reserved_paths:
        raise OutputError(
            "The video Markdown output cannot use a reserved media path.",
            code="OUTPUT_PATH_INVALID",
        ) from None
    try:
        if not os.path.lexists(target):
            return
        aliases_reserved_media = any(
            os.path.lexists(asset) and os.path.samefile(target, asset)
            for asset in reserved_paths
        )
    except (OSError, ValueError) as error:
        raise OutputError(
            "The video Markdown output could not be compared with reserved media.",
            code="OUTPUT_PATH_INVALID",
        ) from error
    if aliases_reserved_media:
        raise OutputError(
            "The video Markdown output cannot use a reserved media path.",
            code="OUTPUT_PATH_INVALID",
        ) from None


def _prepare_video_markdown_target(target: Path, *, overwrite: bool) -> None:
    from .errors import OutputError, OutputExists

    try:
        parent = target.parent
        if parent.exists() and not parent.is_dir():
            raise OutputError(
                "The video Markdown output parent must be a directory.",
                code="OUTPUT_PATH_INVALID",
            ) from None
        parent.mkdir(parents=True, exist_ok=True)
        if not parent.is_dir():
            raise OutputError(
                "The video Markdown output parent must be a directory.",
                code="OUTPUT_PATH_INVALID",
            ) from None

        target_exists = os.path.lexists(target)
        if target_exists and not target.is_file():
            raise OutputError(
                "The video Markdown output path must be a regular file.",
                code="OUTPUT_PATH_INVALID",
            ) from None
        if target_exists and not overwrite:
            raise OutputExists("The video Markdown output already exists.") from None
    except (OutputError, OutputExists):
        raise
    except (OSError, ValueError) as error:
        raise OutputError(
            "The video Markdown output path could not be prepared.",
            code="OUTPUT_PATH_INVALID",
        ) from error
