"""Run one fixed-result resumable video recognition job."""

from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path

from .config import Config
from .result import RecognitionResult


def recognize_video_to_markdown(
    source: str | Path,
    *,
    output_dir: str | Path,
    image_config: Config,
    audio_config: Config,
    audio_interval_minutes: int | None = None,
    resume: bool = False,
) -> RecognitionResult:
    """Recognize full video frames and audio into one resumable result."""
    from .clear_public_error import clear_public_error
    from .errors import OCRLLMError

    try:
        return _recognize_video_to_markdown(
            source,
            output_dir=output_dir,
            image_config=image_config,
            audio_config=audio_config,
            audio_interval_minutes=audio_interval_minutes,
            resume=resume,
        )
    except OCRLLMError as error:
        clear_public_error(error)
        raise error from None


def _recognize_video_to_markdown(
    source: str | Path,
    *,
    output_dir: str | Path,
    image_config: Config,
    audio_config: Config,
    audio_interval_minutes: int | None,
    resume: bool,
) -> RecognitionResult:
    from .errors import ConfigError, OutputError, OutputExists
    from .output.claim_output_target import claim_output_target
    from .output.normalize_output_stem import normalize_output_stem
    from .providers.validate_vision_provider_config import (
        validate_vision_provider_config,
    )
    from .validate_cancellation_signal import validate_cancellation_signal
    from .validate_config import validate_config
    from .validate_google_mp3_options import validate_google_mp3_options
    from .validate_long_audio_interval_minutes import (
        validate_long_audio_interval_minutes,
    )
    from .video.coerce_video_output_directory import (
        coerce_video_output_directory,
    )

    if type(resume) is not bool:
        raise TypeError("recognize_video_to_markdown() resume must be a boolean")
    validated_image = validate_config(image_config)
    validated_audio = validate_config(audio_config)
    _reject_branch_persistence(validated_image, branch="image")
    _reject_branch_persistence(validated_audio, branch="audio")
    validate_vision_provider_config(validated_image, require_injected_callable=True)
    validate_google_mp3_options(
        (Path("video-audio.mp3"),),
        config=validated_audio,
    )
    interval_minutes = validate_long_audio_interval_minutes(
        audio_interval_minutes
    )
    validate_cancellation_signal(validated_image.cancellation)
    validate_cancellation_signal(validated_audio.cancellation)
    image_cancelled = _read_cancellation(validated_image)
    audio_cancelled = _read_cancellation(validated_audio)
    if image_cancelled is not None and audio_cancelled is not None:
        raise image_cancelled from None
    if not resume and audio_cancelled is None:
        from .providers.google_genai.resolve_google_genai_credential import (
            resolve_google_genai_credential,
        )

        try:
            resolve_google_genai_credential(validated_audio.provider)
        except ConfigError as error:
            error._add_safe_detail("provider_calls_attempted", 0)
            raise

    try:
        source_path = Path(source)
    except TypeError:
        raise TypeError(
            "recognize_video_to_markdown() source must be a string or Path"
        ) from None
    output_parent = coerce_video_output_directory(output_dir)
    try:
        output_parent = output_parent.resolve(strict=False)
    except (OSError, RuntimeError, ValueError) as error:
        raise OutputError(
            "The video output directory could not be resolved.",
            code="OUTPUT_PATH_INVALID",
        ) from error
    output_root = output_parent / normalize_output_stem(source_path.stem)

    if resume:
        _preflight_resume_root(output_root)
        with claim_output_target(output_root):
            _preflight_resume_root(output_root)
            return _resume_video_job(
                source_path,
                output_root=output_root,
                image_config=validated_image,
                audio_config=validated_audio,
                interval_minutes=interval_minutes,
                image_cancelled=image_cancelled,
                audio_cancelled=audio_cancelled,
            )

    if os.path.lexists(output_root):
        raise OutputExists("The requested video output directory already exists.")
    return _start_video_job(
        source_path,
        output_parent=output_parent,
        output_root=output_root,
        image_config=validated_image,
        audio_config=validated_audio,
        interval_minutes=interval_minutes,
        image_cancelled=image_cancelled,
        audio_cancelled=audio_cancelled,
    )


def _start_video_job(
    source_path: Path,
    *,
    output_parent: Path,
    output_root: Path,
    image_config: Config,
    audio_config: Config,
    interval_minutes: int | None,
    image_cancelled,
    audio_cancelled,
) -> RecognitionResult:
    from .build_owned_media_fingerprint import build_owned_media_fingerprint
    from .errors import OutputError
    from .hash_video_snapshot import hash_video_snapshot
    from .plan_video_frame_groups import plan_video_frame_groups
    from .video.prepare_video_media import prepare_video_media
    from .video_job_journal import VideoJobJournal
    from .video_job_state import (
        VIDEO_JOB_RESULT_NAME,
        VIDEO_JOB_STATE_NAME,
        VIDEO_JOB_STATE_VERSION,
        VideoAudioState,
        VideoJobState,
    )

    outcome = None
    journal = None
    result = None
    try:
        with prepare_video_media(
            source_path,
            output_dir=output_parent,
        ) as (snapshot_path, frames):
            byte_size, sha256 = hash_video_snapshot(snapshot_path)
            source_identity = build_owned_media_fingerprint(
                source_path,
                byte_size=byte_size,
                sha256=sha256,
            )
            model = audio_config.audio_model.name
            assert type(model) is str
            state = VideoJobState(
                state_version=VIDEO_JOB_STATE_VERSION,
                source=source_identity,
                frame_groups=plan_video_frame_groups(
                    frames,
                    config=image_config,
                ),
                audio=VideoAudioState(
                    state="pending",
                    mode=None,
                    interval_minutes=interval_minutes,
                    model=model,
                ),
            )
            journal = VideoJobJournal(output_root / VIDEO_JOB_STATE_NAME, state)
            journal.save_initial()
            if audio_cancelled is None:
                audio_cancelled = _read_cancellation(audio_config)
            if audio_cancelled is None:
                _prepare_pending_audio(
                    snapshot_path,
                    output_root=output_root,
                    config=audio_config,
                    interval_minutes=interval_minutes,
                    journal=journal,
                )
            outcome = _settle_video_job(
                frames,
                output_root=output_root,
                image_config=image_config,
                audio_config=audio_config,
                journal=journal,
                image_cancelled=image_cancelled,
                audio_cancelled=audio_cancelled,
            )
            from .finalize_video_job import finalize_video_job

            result = finalize_video_job(
                outcome,
                journal=journal,
                result_path=output_root / VIDEO_JOB_RESULT_NAME,
            )
    except BaseException as error:
        state_path = output_root / VIDEO_JOB_STATE_NAME
        if result is None and not os.path.lexists(state_path):
            _remove_unstarted_video_root(output_root, primary_error=error)
        if (
            isinstance(error, OutputError)
            and result is not None
            and error.details.get("stage") == "video_snapshot_cleanup"
        ):
            metadata = dict(result.metadata)
            metadata["video_cleanup_error_code"] = error.code
            result = replace(
                result,
                status="partial",
                warnings=(
                    *result.warnings,
                    f"Video source-snapshot cleanup failed with {error.code}.",
                ),
                metadata=metadata,
            )
        else:
            raise

    assert result is not None
    return result


def _resume_video_job(
    source_path: Path,
    *,
    output_root: Path,
    image_config: Config,
    audio_config: Config,
    interval_minutes: int | None,
    image_cancelled,
    audio_cancelled,
) -> RecognitionResult:
    from .errors import ConfigError, OutputError
    from .load_video_job_state import load_video_job_state
    from .validate_video_job_resume import (
        validate_video_job_finalization_state,
        validate_video_job_resume,
    )
    from .video.snapshot_video_source import snapshot_video_source
    from .video_job_journal import VideoJobJournal
    from .video_job_state import VIDEO_JOB_RESULT_NAME, VIDEO_JOB_STATE_NAME

    journal_path = output_root / VIDEO_JOB_STATE_NAME
    journal = VideoJobJournal(journal_path, load_video_job_state(journal_path))
    if interval_minutes is None:
        interval_minutes = journal.state.audio.interval_minutes

    validate_video_job_finalization_state(
        journal.state,
        result_path=output_root / VIDEO_JOB_RESULT_NAME,
    )
    if journal.state.audio.state == "pending":
        if audio_cancelled is None:
            audio_cancelled = _read_cancellation(audio_config)
        if audio_cancelled is None:
            from .providers.google_genai.resolve_google_genai_credential import (
                resolve_google_genai_credential,
            )

            try:
                resolve_google_genai_credential(audio_config.provider)
            except ConfigError as error:
                error._add_safe_detail("provider_calls_attempted", 0)
                raise
    outcome = None
    try:
        with snapshot_video_source(
            source_path,
            snapshot_parent=output_root.parent,
        ) as snapshot_path:
            frames = validate_video_job_resume(
                journal.state,
                source_path=source_path,
                snapshot_path=snapshot_path,
                output_root=output_root,
                image_config=image_config,
                audio_config=audio_config,
                audio_interval_minutes=interval_minutes,
            )
            if journal.state.audio.state == "pending":
                if audio_cancelled is None:
                    audio_cancelled = _read_cancellation(audio_config)
                if audio_cancelled is None:
                    _prepare_pending_audio(
                        snapshot_path,
                        output_root=output_root,
                        config=audio_config,
                        interval_minutes=interval_minutes,
                        journal=journal,
                    )
            outcome = _settle_video_job(
                frames,
                output_root=output_root,
                image_config=image_config,
                audio_config=audio_config,
                journal=journal,
                image_cancelled=image_cancelled,
                audio_cancelled=audio_cancelled,
            )
    except OutputError as error:
        if outcome is None or error.details.get("stage") != "video_snapshot_cleanup":
            raise
        outcome = replace(outcome, snapshot_cleanup_error=error)

    assert outcome is not None
    from .finalize_video_job import finalize_video_job

    return finalize_video_job(
        outcome,
        journal=journal,
        result_path=output_root / VIDEO_JOB_RESULT_NAME,
    )


def _prepare_pending_audio(
    snapshot_path: Path,
    *,
    output_root: Path,
    config: Config,
    interval_minutes: int | None,
    journal,
) -> None:
    from .errors import OCRLLMError, VideoError
    from .prepare_video_job_audio_state import prepare_video_job_audio_state
    from .video.extract_video_audio import (
        _extract_video_audio_from_stable_source,
    )
    from .video_job_state import VideoAudioState

    artifact = output_root / "audio.mp3"
    if os.path.lexists(artifact):
        try:
            artifact.unlink()
        except (OSError, ValueError) as error:
            from .errors import OutputError

            raise OutputError(
                "An unjournaled video audio artifact could not be removed.",
                code="OUTPUT_WRITE_FAILED",
            ) from error
    try:
        artifact = _extract_video_audio_from_stable_source(
            snapshot_path,
            output_path=artifact,
        )
    except VideoError as error:
        if error.code != "VIDEO_NO_AUDIO_STREAM":
            raise
        current = journal.state.audio
        journal.persist_audio(
            VideoAudioState(
                state="absent",
                mode=None,
                interval_minutes=interval_minutes,
                model=current.model,
            )
        )
        return

    try:
        ready = prepare_video_job_audio_state(
            artifact,
            config=config,
            interval_minutes=interval_minutes,
        )
        journal.persist_audio(ready)
    except BaseException as error:
        try:
            artifact.unlink(missing_ok=True)
        except (OSError, ValueError):
            if isinstance(error, OCRLLMError):
                error._add_safe_detail("audio_cleanup_failed", True)
        raise


def _settle_video_job(
    frames,
    *,
    output_root: Path,
    image_config: Config,
    audio_config: Config,
    journal,
    image_cancelled,
    audio_cancelled,
):
    from .attach_current_video_evidence_to_error import (
        attach_current_video_evidence_to_error,
    )
    from .errors import NoSpeechDetected, OCRLLMError, VideoError
    from .recognize_video_job_audio import recognize_video_job_audio
    from .recognize_video_job_frames import recognize_video_job_frames
    from .video_recognition_outcome import VideoRecognitionOutcome

    frame_error = image_cancelled
    frame_outcomes = ()
    if frame_error is None:
        try:
            frame_outcomes = recognize_video_job_frames(
                frames,
                config=image_config,
                journal=journal,
            )
        except OCRLLMError as error:
            frame_error = error
    audio = journal.state.audio
    audio_result = None
    audio_error = audio_cancelled
    if audio_error is None:
        if audio.state == "absent":
            audio_error = VideoError(
                "The video has no audio stream.",
                code="VIDEO_NO_AUDIO_STREAM",
                details={"provider_calls_attempted": 0},
            )
        else:
            audio_result, audio_error = recognize_video_job_audio(
                audio,
                config=audio_config,
                journal=journal,
            )
    if frame_error is not None:
        secondary_audio = audio_result if audio_result is not None else audio_error
        attach_current_video_evidence_to_error(
            frame_error,
            after=(() if secondary_audio is None else (secondary_audio,)),
        )
        raise frame_error from None
    if (
        audio_error is not None
        and not isinstance(audio_error, NoSpeechDetected)
        and audio_error.code != "VIDEO_NO_AUDIO_STREAM"
    ):
        attach_current_video_evidence_to_error(
            audio_error,
            before=tuple(
                item.result
                for item in frame_outcomes
                if item.result is not None
            ),
        )
        raise audio_error from None
    assert (audio_result is None) != (audio_error is None)
    outcome = VideoRecognitionOutcome(
        output_root=output_root,
        retained_frames=frames,
        frame_outcomes=frame_outcomes,
        audio_artifact=(
            output_root / "audio.mp3"
            if journal.state.audio.state == "ready"
            else None
        ),
        audio_result=audio_result,
        audio_error=audio_error,
    )
    late_cancellation = _read_cancellation(image_config)
    if late_cancellation is None:
        late_cancellation = _read_cancellation(audio_config)
    if late_cancellation is not None:
        branch_evidence = tuple(
            item.result if item.result is not None else item.error
            for item in frame_outcomes
        )
        audio_evidence = (
            outcome.audio_result
            if outcome.audio_result is not None
            else outcome.audio_error
        )
        assert all(item is not None for item in branch_evidence)
        assert audio_evidence is not None
        attach_current_video_evidence_to_error(
            late_cancellation,
            before=(*branch_evidence, audio_evidence),
            primary_provider_calls_attempted=0,
        )
        raise late_cancellation from None
    return outcome


def _preflight_resume_root(output_root: Path) -> None:
    from .errors import OutputError, ResumeStateError
    from .video_job_state import VIDEO_JOB_STATE_NAME

    try:
        if not os.path.lexists(output_root) or not output_root.is_dir():
            raise ResumeStateError(
                "The video job output directory is missing.",
                code="RESUME_STATE_INVALID",
            ) from None
        journal = output_root / VIDEO_JOB_STATE_NAME
        if not os.path.lexists(journal) or not journal.is_file():
            raise ResumeStateError(
                "The video resume journal is missing.",
                code="RESUME_STATE_INVALID",
            ) from None
    except ResumeStateError:
        raise
    except (OSError, ValueError) as error:
        raise OutputError(
            "The video job output directory could not be inspected.",
            code="OUTPUT_PATH_INVALID",
        ) from error


def _reject_branch_persistence(config: Config, *, branch: str) -> None:
    from .errors import ConfigError

    if config.output_dir is not None or config.resume or config.overwrite:
        raise ConfigError(
            f"recognize_video_to_markdown() owns {branch} persistence; "
            "branch output_dir, resume, and overwrite are not accepted.",
            code="CONFIG_INVALID",
        ) from None


def _read_cancellation(config: Config):
    from .errors import Cancelled
    from .raise_if_cancelled import raise_if_cancelled

    try:
        raise_if_cancelled(config.cancellation)
    except Cancelled as error:
        return error
    return None


def _remove_unstarted_video_root(
    output_root: Path,
    *,
    primary_error: BaseException,
) -> None:
    import shutil

    from .errors import OCRLLMError

    try:
        if os.path.lexists(output_root):
            shutil.rmtree(output_root)
    except (OSError, ValueError):
        if isinstance(primary_error, OCRLLMError):
            primary_error._add_safe_detail("video_output_cleanup_failed", True)
