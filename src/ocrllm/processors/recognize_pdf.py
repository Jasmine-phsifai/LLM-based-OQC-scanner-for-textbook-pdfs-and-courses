"""Recognize one PDF through ordered image groups."""

from __future__ import annotations

import errno
import os
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING

from ..config import Config
from ..errors import InvalidSource, OCRLLMError
from ..output.build_output_path import build_output_path
from ..output.prepare_pdf_state_directory import prepare_pdf_state_directory
from ..pdf.attach_pdf_settled_work import attach_pdf_settled_work
from ..pdf.combine_pdf_group_results import combine_pdf_group_results
from ..pdf.inspect_pdf import inspect_pdf
from ..pdf.render_pdf_page_group import render_pdf_page_group
from ..pdf.snapshot_pdf import snapshot_pdf
from ..profiles.resolve_image_profile import resolve_image_profile
from ..raise_if_cancelled import raise_if_cancelled

if TYPE_CHECKING:
    from ..output.output_target_claims import OutputTargetClaims
    from ..processor_output import ProcessorOutput
    from ..result import RecognitionResult


PDF_IMAGE_GROUP_SIZE = 8


def recognize_pdf(
    source_paths: Sequence[Path],
    *,
    config: Config,
    output_claims: OutputTargetClaims,
) -> tuple[ProcessorOutput, Path | None]:
    """Return one complete range-marked PDF result and optional final path."""
    if len(source_paths) != 1:
        raise InvalidSource(
            "PDF recognition accepts exactly one PDF source.",
            code="SOURCE_INVALID",
        ) from None
    source_path = Path(source_paths[0])
    profile = resolve_image_profile(config.profile)
    settled_results: list[RecognitionResult] = []
    page_ranges: list[tuple[int, int]] = []
    output_path: Path | None = None
    state_directory: Path | None = None
    state_directory_created = False

    try:
        raise_if_cancelled(config.cancellation)
        with snapshot_pdf(source_path, temp_dir=config.temp_dir) as snapshot:
            page_sizes = inspect_pdf(snapshot.path)
            output_path = build_output_path(
                (source_path,),
                profile=profile,
                config=config,
            )
            if output_path is not None:
                output_claims.claim(output_path)
                output_path = build_output_path(
                    (source_path,),
                    profile=profile,
                    config=config,
                )
                state_directory = output_path.with_suffix("")
                state_directory_created = not os.path.lexists(state_directory)
                render_directory = prepare_pdf_state_directory(
                    output_path,
                    config=config,
                )
                child_config = replace(config, output_dir=render_directory)
            else:
                render_directory = snapshot.root / "rendered-pages"
                child_config = config

            from ..recognize import _recognize

            for first_index in range(0, len(page_sizes), PDF_IMAGE_GROUP_SIZE):
                raise_if_cancelled(config.cancellation)
                indexes = tuple(
                    range(
                        first_index,
                        min(first_index + PDF_IMAGE_GROUP_SIZE, len(page_sizes)),
                    )
                )
                with render_pdf_page_group(
                    snapshot.path,
                    indexes,
                    page_sizes,
                    output_directory=render_directory,
                    cancellation=config.cancellation,
                ) as rendered_paths:
                    settled_results.append(
                        _recognize(
                            rendered_paths,
                            config=child_config,
                            output_claims=output_claims,
                        )
                    )
                page_ranges.append((indexes[0] + 1, indexes[-1] + 1))
    except OCRLLMError as error:
        if (
            state_directory_created
            and state_directory is not None
            and not settled_results
        ):
            try:
                state_directory.rmdir()
            except OSError as cleanup_error:
                if cleanup_error.errno not in {errno.ENOTEMPTY, errno.EEXIST}:
                    error._add_safe_detail("pdf_state_cleanup_failed", True)
            except ValueError:
                error._add_safe_detail("pdf_state_cleanup_failed", True)
        attach_pdf_settled_work(error, settled_results)
        raise

    return (
        combine_pdf_group_results(
            settled_results,
            page_ranges,
            profile=profile,
        ),
        output_path,
    )
