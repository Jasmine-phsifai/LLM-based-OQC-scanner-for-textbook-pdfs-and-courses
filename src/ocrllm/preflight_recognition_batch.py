"""Validate one complete recognition batch before execution side effects."""

from __future__ import annotations

import os
from pathlib import Path

from .audio.probe_short_mp3 import probe_short_mp3
from .coerce_source_paths import coerce_source_paths
from .config import Config
from .errors import ConfigError, InvalidSource, OutputError, OutputExists
from .output.load_image_resume_state import load_image_resume_state
from .output.resolve_resume_state_path import resolve_resume_state_path
from .output.resolve_output_path import resolve_output_path
from .output.validate_image_resume_state_output_pair import (
    validate_image_resume_state_output_pair,
)
from .profiles.resolve_image_profile import resolve_image_profile
from .providers.validate_vision_provider_config import (
    validate_vision_provider_config,
)
from .validate_execution_image_count import validate_execution_image_count
from .validate_image_group import validate_image_group
from .validate_same_type_group import validate_same_type_group
from .validate_source import validate_source
from .validate_google_mp3_options import validate_google_mp3_options


def preflight_recognition_batch(
    sources: object,
    *,
    config: Config,
) -> tuple[tuple[Path, ...], ...]:
    """Return normalized groups after complete read-only batch validation."""
    groups = _normalize_batch_shape(sources)
    media_types: list[str] = []
    image_provider_validated = False

    for source_paths in groups:
        media_type = validate_same_type_group(source_paths)
        media_types.append(media_type)
        if media_type == "image":
            if not image_provider_validated:
                validate_vision_provider_config(
                    config,
                    require_injected_callable=True,
                )
                image_provider_validated = True
        elif media_type == "pdf":
            raise InvalidSource(
                "recognize_batch() does not accept PDF sources in this release.",
                code="SOURCE_INVALID",
            ) from None
        else:
            validate_google_mp3_options(source_paths, config=config)

    if groups:
        from .raise_if_cancelled import raise_if_cancelled

        raise_if_cancelled(config.cancellation)

    resolved_targets: list[Path] = []
    audio_credential_validated = False
    for source_paths, media_type in zip(groups, media_types):
        if media_type == "image":
            validate_execution_image_count(source_paths, config=config)
            output_path = resolve_output_path(
                source_paths,
                profile=resolve_image_profile(config.profile),
                config=config,
            )
            if output_path is not None:
                _validate_output_target_without_writing(output_path, config=config)
                if config.resume:
                    resume_state = load_image_resume_state(
                        resolve_resume_state_path(output_path)
                    )
                    validate_image_resume_state_output_pair(
                        resume_state,
                        output_path,
                    )
                resolved_targets.append(output_path)
        else:
            if not audio_credential_validated:
                from .providers.google_genai.resolve_google_genai_credential import (
                    resolve_google_genai_credential,
                )

                try:
                    resolve_google_genai_credential(config.provider)
                except ConfigError as error:
                    error._add_safe_detail("provider_calls_attempted", 0)
                    raise
                audio_credential_validated = True

    if len(set(resolved_targets)) != len(resolved_targets):
        raise OutputExists(
            "Two batch items resolve to the same Markdown output target."
        ) from None

    for source_paths, media_type in zip(groups, media_types):
        if media_type == "image":
            validate_image_group(source_paths)
        else:
            validate_source(source_paths[0])
            probe_short_mp3(source_paths[0])
    return groups


def _normalize_batch_shape(sources: object) -> tuple[tuple[Path, ...], ...]:
    if type(sources) is not tuple:
        raise InvalidSource(
            "recognize_batch() requires a concrete tuple of sources.",
            code="SOURCE_INVALID",
        ) from None
    groups: list[tuple[Path, ...]] = []
    for item in sources:
        groups.append(coerce_source_paths(item))
    return tuple(groups)


def _validate_output_target_without_writing(
    output_path: Path,
    *,
    config: Config,
) -> None:
    output_dir = output_path.parent
    try:
        if output_dir.exists() and not output_dir.is_dir():
            raise OutputError(
                "Config.output_dir must identify a directory.",
                code="OUTPUT_PATH_INVALID",
            )
        target_exists = os.path.lexists(output_path)
        if target_exists and not output_path.is_file():
            raise OutputError(
                "The requested Markdown output path is not a regular file.",
                code="OUTPUT_PATH_INVALID",
            )
    except OutputError:
        raise
    except (OSError, ValueError) as error:
        raise OutputError(
            "Config.output_dir could not be opened.",
            code="OUTPUT_PATH_INVALID",
        ) from error
    if target_exists and not config.overwrite and not config.resume:
        raise OutputExists("The requested Markdown output already exists.")
