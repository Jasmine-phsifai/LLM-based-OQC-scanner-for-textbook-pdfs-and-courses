from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from ocrllm import (
    BatchItemOutcome,
    RecognitionResult,
    RetainedVideoFrame,
    VideoRecognitionOutcome,
)
from ocrllm.errors import ConfigError, ProviderError, VideoError
from tools import run_google_genai_video_smoke as smoke


IMAGE_MODEL = "gemini-video-image-model"
AUDIO_MODEL = "gemini-video-audio-model"


def _frame_result(
    *,
    markdown: str,
    output_path: Path | None = None,
    include_usage: bool = False,
    model: str = IMAGE_MODEL,
    frame_indices: tuple[int, ...] = (0,),
    frame_timestamps: tuple[float, ...] = (0.0,),
) -> RecognitionResult:
    metadata: dict[str, object] = {
        "provider": "google",
        "model": model,
        "provider_call_count": 1,
        "video_frame_indices": frame_indices,
        "video_frame_timestamps_seconds": frame_timestamps,
    }
    if include_usage:
        metadata["current_model_token_usage"] = (
            {"model": model, "input_tokens": 10, "output_tokens": 2},
        )
    return RecognitionResult(
        markdown=markdown,
        source_type="image",
        output_path=output_path,
        metadata=metadata,
    )


def _audio_result(
    *,
    markdown: str,
    output_path: Path | None = None,
    include_usage: bool = False,
    model: str = AUDIO_MODEL,
    transport: str = "google_inline",
) -> RecognitionResult:
    metadata: dict[str, object] = {
        "provider": "google",
        "model": model,
        "provider_call_count": 1,
        "duration_seconds": 1.0,
        "provider_client_closed": True,
    }
    if transport == "google_files":
        metadata.update(
            {
                "transport": "google_files",
                "duration_seconds": 301.0,
                "remote_file_deleted": True,
            }
        )
    if include_usage:
        metadata["current_model_token_usage"] = (
            {"model": model, "input_tokens": 20, "output_tokens": 4},
        )
    return RecognitionResult(
        markdown=markdown,
        source_type="audio",
        output_path=output_path,
        metadata=metadata,
    )


def _build_outcome(
    output_dir: Path,
    *,
    private_markdown: str,
    frame_error: ProviderError | None = None,
    audio_error: ProviderError | VideoError | None = None,
    keep_audio_artifact: bool = True,
    frame_output_path: Path | None = None,
    audio_output_path: Path | None = None,
    include_usage: bool = False,
    image_model: str = IMAGE_MODEL,
    audio_model: str = AUDIO_MODEL,
    retained_count: int = 1,
    frame_group_count: int = 1,
    audio_transport: str = "google_inline",
) -> VideoRecognitionOutcome:
    output_root = output_dir / "video"
    frames_dir = output_root / "frames"
    frames_dir.mkdir(parents=True)
    retained_frames = tuple(
        RetainedVideoFrame(
            frame_index=index,
            timestamp_seconds=float(index),
            path=frames_dir / f"frame-{index:08d}.jpg",
        )
        for index in range(retained_count)
    )
    for frame in retained_frames:
        frame.path.write_bytes(b"jpeg")
    if frame_error is None:
        frame_outcomes = tuple(
            BatchItemOutcome(
                index=group_index,
                result=_frame_result(
                    markdown=private_markdown,
                    output_path=frame_output_path,
                    include_usage=include_usage,
                    model=image_model,
                    frame_indices=tuple(
                        frame.frame_index
                        for frame in retained_frames[
                            group_index * 8 : (group_index + 1) * 8
                        ]
                    ),
                    frame_timestamps=tuple(
                        frame.timestamp_seconds
                        for frame in retained_frames[
                            group_index * 8 : (group_index + 1) * 8
                        ]
                    ),
                ),
            )
            for group_index in range(frame_group_count)
        )
    else:
        frame_outcomes = ()

    audio_artifact = output_root / "audio.mp3" if keep_audio_artifact else None
    if audio_artifact is not None:
        audio_artifact.write_bytes(b"mp3")
    return VideoRecognitionOutcome(
        output_root=output_root,
        retained_frames=retained_frames,
        frame_outcomes=frame_outcomes,
        frame_error=frame_error,
        audio_artifact=audio_artifact,
        audio_result=(
            _audio_result(
                markdown=private_markdown,
                output_path=audio_output_path,
                include_usage=include_usage,
                model=audio_model,
                transport=audio_transport,
            )
            if audio_error is None
            else None
        ),
        audio_error=audio_error,
    )


def _arguments(
    *,
    image_model: str = IMAGE_MODEL,
    audio_model: str = AUDIO_MODEL,
    expected_frame_group_count: int = 1,
    expected_audio_transport: str = "google_inline",
) -> argparse.Namespace:
    return argparse.Namespace(
        image_model=image_model,
        audio_model=audio_model,
        video=Path("private-video-name.mp4"),
        timeout=9.0,
        expected_frame_group_count=expected_frame_group_count,
        expected_audio_transport=expected_audio_transport,
    )


@pytest.fixture(autouse=True)
def real_video_preflight(monkeypatch: pytest.MonkeyPatch):
    real_preflight = smoke._preflight_video_frames
    monkeypatch.setattr(smoke, "_preflight_video_frames", lambda source: (1, 1))
    return real_preflight


def _install_catalog(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        smoke,
        "list_google_genai_models",
        lambda settings, timeout_seconds: (IMAGE_MODEL, AUDIO_MODEL),
    )


@pytest.mark.parametrize("expected_count", [1, 2])
def test_video_smoke_parses_only_bounded_expected_group_counts(
    expected_count: int,
) -> None:
    arguments = smoke.parse_arguments(
        [
            "--image-model",
            IMAGE_MODEL,
            "--audio-model",
            AUDIO_MODEL,
            "--expected-audio-transport",
            "google_inline",
            "--video",
            "controlled.mp4",
            "--expected-frame-groups",
            str(expected_count),
        ]
    )

    assert arguments.expected_frame_group_count == expected_count


@pytest.mark.parametrize("invalid_count", ["0", "3", "many"])
def test_video_smoke_rejects_unbounded_expected_group_counts(
    invalid_count: str,
) -> None:
    with pytest.raises(SystemExit):
        smoke.parse_arguments(
            [
                "--image-model",
                IMAGE_MODEL,
                "--audio-model",
                AUDIO_MODEL,
                "--expected-audio-transport",
                "google_inline",
                "--video",
                "controlled.mp4",
                "--expected-frame-groups",
                invalid_count,
            ]
        )


def test_video_smoke_reports_complete_branches_and_cleans_owned_artifacts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_markdown = "PRIVATE VIDEO RECOGNITION"
    private_key = "PRIVATE-GOOGLE-VIDEO-KEY"
    monkeypatch.setenv("GOOGLE_API_KEY", private_key)
    _install_catalog(monkeypatch)
    observed_roots: list[Path] = []

    def fake_recognize_video(source, *, output_dir, image_config, audio_config):
        observed_roots.append(Path(output_dir).parent)
        assert source == _arguments().video
        assert image_config is not audio_config
        assert image_config.vision_model.name == IMAGE_MODEL
        assert audio_config.audio_model.name == AUDIO_MODEL
        assert image_config.timeout_seconds == audio_config.timeout_seconds == 9.0
        return _build_outcome(
            Path(output_dir),
            private_markdown=private_markdown,
        )

    monkeypatch.setattr(smoke, "recognize_video", fake_recognize_video)

    summary = smoke.run_google_genai_video_smoke(_arguments())

    assert summary["report_type"] == "video_outcome"
    assert summary == {
        "report_type": "video_outcome",
        "status": "passed",
        "catalog_count": 2,
        "image_model": IMAGE_MODEL,
        "audio_model": AUDIO_MODEL,
        "outcome_status": "complete",
        "preflight": {
            "retained_count": 1,
            "expected_frame_group_count": 1,
        },
        "frames": {
            "status": "complete",
            "retained_count": 1,
            "group_count": 1,
            "successful_group_count": 1,
            "provider_calls_attempted": 1,
            "errors": [],
        },
        "audio": {
            "status": "recognized",
            "artifact_present": True,
            "provider_calls_attempted": 1,
            "transport": "google_inline",
            "duration_seconds": 1.0,
            "remote_file_deleted": None,
            "provider_client_closed": True,
            "error": None,
        },
        "composition": {
            "status": "complete",
            "asset_count": 2,
            "error": None,
        },
    }
    raw = json.dumps(summary, sort_keys=True)
    assert private_key not in raw
    assert private_markdown not in raw
    assert str(_arguments().video) not in raw
    assert observed_roots and all(not root.exists() for root in observed_roots)


def test_video_smoke_proves_files_transport_and_cleanup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_catalog(monkeypatch)
    monkeypatch.setattr(
        smoke,
        "recognize_video",
        lambda source, **kwargs: _build_outcome(
            Path(kwargs["output_dir"]),
            private_markdown="PRIVATE LONG AUDIO",
            audio_transport="google_files",
        ),
    )

    summary = smoke.run_google_genai_video_smoke(
        _arguments(expected_audio_transport="google_files")
    )

    assert summary["status"] == "passed"
    assert summary["audio"] == {
        "status": "recognized",
        "artifact_present": True,
        "provider_calls_attempted": 1,
        "transport": "google_files",
        "duration_seconds": 301.0,
        "remote_file_deleted": True,
        "provider_client_closed": True,
        "error": None,
    }


def test_video_smoke_rejects_inline_audio_when_files_is_expected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_catalog(monkeypatch)
    monkeypatch.setattr(
        smoke,
        "recognize_video",
        lambda source, **kwargs: _build_outcome(
            Path(kwargs["output_dir"]),
            private_markdown="PRIVATE INLINE AUDIO",
        ),
    )

    with pytest.raises(smoke._LiveSmokeFailure) as failure:
        smoke.run_google_genai_video_smoke(
            _arguments(expected_audio_transport="google_files")
        )

    assert failure.value.stage == "video_orchestration"
    assert failure.value.error is not None
    assert failure.value.error.code == "CONFIG_INVALID"


def test_video_smoke_preflight_counts_groups_and_cleans_frames(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    real_video_preflight,
) -> None:
    observed_roots: list[Path] = []

    def fake_extract_video_frames(source, *, output_dir):
        assert source == tmp_path / "controlled.mp4"
        observed_roots.append(Path(output_dir).parent)
        return tuple(object() for _ in range(10))

    monkeypatch.setattr(smoke, "extract_video_frames", fake_extract_video_frames)

    assert real_video_preflight(tmp_path / "controlled.mp4") == (10, 2)
    assert observed_roots and all(not root.exists() for root in observed_roots)


def test_video_smoke_rejects_excess_groups_before_catalog_or_recognition(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(smoke, "_preflight_video_frames", lambda source: (17, 3))
    monkeypatch.setattr(
        smoke,
        "list_google_genai_models",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("catalog must not start")
        ),
    )
    monkeypatch.setattr(
        smoke,
        "recognize_video",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("recognition must not start")
        ),
    )

    with pytest.raises(smoke._LiveSmokeFailure) as failure:
        smoke.run_google_genai_video_smoke(
            _arguments(expected_frame_group_count=2)
        )

    assert failure.value.stage == "video_preflight"
    assert failure.value.error is not None
    assert failure.value.error.code == "CONFIG_INVALID"
    assert failure.value.error.details["provider_calls_attempted"] == 0


def test_video_smoke_accepts_two_complete_frame_groups(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_catalog(monkeypatch)
    monkeypatch.setattr(smoke, "_preflight_video_frames", lambda source: (10, 2))
    monkeypatch.setattr(
        smoke,
        "recognize_video",
        lambda source, **kwargs: _build_outcome(
            Path(kwargs["output_dir"]),
            private_markdown="PRIVATE TWO-GROUP RESULT",
            retained_count=10,
            frame_group_count=2,
        ),
    )

    summary = smoke.run_google_genai_video_smoke(
        _arguments(expected_frame_group_count=2)
    )

    assert summary["status"] == "passed"
    assert summary["preflight"] == {
        "retained_count": 10,
        "expected_frame_group_count": 2,
    }
    assert summary["frames"]["retained_count"] == 10
    assert summary["frames"]["group_count"] == 2
    assert summary["frames"]["provider_calls_attempted"] == 2
    assert summary["composition"]["asset_count"] == 11


def test_video_smoke_reports_only_validated_model_token_usage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_catalog(monkeypatch)

    def fake_recognize_video(source, *, output_dir, image_config, audio_config):
        return _build_outcome(
            Path(output_dir),
            private_markdown="PRIVATE TOKEN USAGE TRANSCRIPT",
            include_usage=True,
        )

    monkeypatch.setattr(smoke, "recognize_video", fake_recognize_video)

    summary = smoke.run_google_genai_video_smoke(_arguments())

    assert summary["composition"]["model_token_usage"] == [
        {
            "model": IMAGE_MODEL,
            "input_tokens": 10,
            "output_tokens": 2,
        },
        {
            "model": AUDIO_MODEL,
            "input_tokens": 20,
            "output_tokens": 4,
        },
    ]
    assert "PRIVATE TOKEN USAGE TRANSCRIPT" not in json.dumps(summary)


def test_video_smoke_aggregates_usage_when_both_branches_use_same_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    shared_model = "gemini-video-shared-model"
    monkeypatch.setattr(
        smoke,
        "list_google_genai_models",
        lambda settings, timeout_seconds: (shared_model,),
    )
    monkeypatch.setattr(
        smoke,
        "recognize_video",
        lambda source, **kwargs: _build_outcome(
            Path(kwargs["output_dir"]),
            private_markdown="PRIVATE",
            include_usage=True,
            image_model=shared_model,
            audio_model=shared_model,
        ),
    )

    summary = smoke.run_google_genai_video_smoke(
        _arguments(image_model=shared_model, audio_model=shared_model)
    )

    assert summary["composition"]["model_token_usage"] == [
        {
            "model": shared_model,
            "input_tokens": 30,
            "output_tokens": 6,
        }
    ]


def test_video_smoke_rejects_usage_from_an_unconfigured_model() -> None:
    with pytest.raises(ConfigError, match="invalid model-usage evidence"):
        smoke._safe_model_token_usage(
            {
                "current_model_token_usage": (
                    {
                        "model": "unexpected-third-model",
                        "input_tokens": 1,
                        "output_tokens": 1,
                    },
                )
            },
            (IMAGE_MODEL, AUDIO_MODEL),
        )


@pytest.mark.parametrize("catalog_models", [(IMAGE_MODEL,), (AUDIO_MODEL,)])
def test_video_smoke_rejects_missing_branch_model_before_recognition(
    monkeypatch: pytest.MonkeyPatch,
    catalog_models: tuple[str, ...],
) -> None:
    monkeypatch.setattr(
        smoke,
        "list_google_genai_models",
        lambda settings, timeout_seconds: catalog_models,
    )
    recognition_called = False

    def fake_recognize_video(*args, **kwargs):
        nonlocal recognition_called
        recognition_called = True
        raise AssertionError("recognition must not start")

    monkeypatch.setattr(smoke, "recognize_video", fake_recognize_video)

    with pytest.raises(smoke._LiveSmokeFailure) as failure:
        smoke.run_google_genai_video_smoke(_arguments())

    assert failure.value.stage == "model_selection"
    assert failure.value.error is not None
    assert failure.value.error.code == "CONFIG_INVALID"
    assert recognition_called is False


def test_video_smoke_preserves_audio_provider_failure_call_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_catalog(monkeypatch)
    private_text = "PRIVATE AUDIO PROVIDER FAILURE"
    observed_roots: list[Path] = []

    def fake_recognize_video(source, *, output_dir, image_config, audio_config):
        observed_roots.append(Path(output_dir).parent)
        return _build_outcome(
            Path(output_dir),
            private_markdown=private_text,
            audio_error=ProviderError(
                private_text,
                code="PROVIDER_RATE_LIMITED",
                details={
                    "provider_calls_attempted": 1,
                    "failure_scope": "request",
                    "remote_file_deleted": True,
                    "provider_file_cleanup_failed": False,
                    "provider_client_closed": True,
                    "provider_client_cleanup_failed": False,
                    "raw_response": private_text,
                },
            ),
        )

    monkeypatch.setattr(smoke, "recognize_video", fake_recognize_video)

    summary = smoke.run_google_genai_video_smoke(_arguments())

    assert summary["status"] == "failed"
    assert summary["outcome_status"] == "partial"
    assert summary["audio"] == {
        "status": "failed",
        "artifact_present": True,
        "provider_calls_attempted": 1,
        "error": {
            "code": "PROVIDER_RATE_LIMITED",
            "stage": "audio_recognition",
            "provider_calls_attempted": 1,
            "failure_scope": "request",
            "remote_file_deleted": True,
            "provider_file_cleanup_failed": False,
            "provider_client_closed": True,
            "provider_client_cleanup_failed": False,
        },
    }
    assert summary["composition"]["status"] == "partial"
    raw = json.dumps(summary, sort_keys=True)
    assert private_text not in raw
    assert observed_roots and all(not root.exists() for root in observed_roots)


def test_video_smoke_reports_only_canonical_safe_provider_failure_reasons(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_catalog(monkeypatch)
    private_text = "PRIVATE PROVIDER RESPONSE DETAIL"
    monkeypatch.setattr(
        smoke,
        "recognize_video",
        lambda source, **kwargs: _build_outcome(
            Path(kwargs["output_dir"]),
            private_markdown=private_text,
            frame_error=ProviderError(
                private_text,
                code="PROVIDER_RESPONSE_INVALID",
                details={
                    "provider_calls_attempted": 1,
                    "reason": "missing_text",
                    "raw_response": private_text,
                },
            ),
            audio_error=ProviderError(
                private_text,
                code="PROVIDER_RESPONSE_INVALID",
                details={
                    "provider_calls_attempted": 1,
                    "reason": "invalid_no_speech_marker",
                    "raw_response": private_text,
                },
            ),
        ),
    )

    summary = smoke.run_google_genai_video_smoke(_arguments())

    assert summary["frames"]["errors"][0]["reason"] == "missing_text"
    assert summary["audio"]["error"]["reason"] == "invalid_no_speech_marker"
    assert private_text not in json.dumps(summary, sort_keys=True)

    unsafe = smoke._safe_error(
        ProviderError(
            private_text,
            details={"reason": private_text},
        ),
        "frame_recognition",
        1,
    )
    assert "reason" not in unsafe
    assert private_text not in json.dumps(unsafe, sort_keys=True)

    malformed_lifecycle = smoke._safe_error(
        ProviderError(
            private_text,
            details={
                "failure_scope": private_text,
                "remote_file_deleted": 1,
                "provider_client_closed": "yes",
            },
        ),
        "audio_recognition",
        0,
    )
    assert "failure_scope" not in malformed_lifecycle
    assert "remote_file_deleted" not in malformed_lifecycle
    assert "provider_client_closed" not in malformed_lifecycle
    assert private_text not in json.dumps(malformed_lifecycle, sort_keys=True)


def test_video_smoke_keeps_missing_audio_call_evidence_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_catalog(monkeypatch)

    monkeypatch.setattr(
        smoke,
        "recognize_video",
        lambda source, **kwargs: _build_outcome(
            Path(kwargs["output_dir"]),
            private_markdown="PRIVATE",
            audio_error=ProviderError(code="PROVIDER_UNAVAILABLE"),
        ),
    )

    summary = smoke.run_google_genai_video_smoke(_arguments())

    assert summary["audio"]["provider_calls_attempted"] is None
    assert summary["audio"]["error"]["provider_calls_attempted"] is None
    assert summary["status"] == "failed"


@pytest.mark.parametrize("attempted_calls", [1, None])
def test_video_smoke_preserves_frame_branch_call_evidence(
    monkeypatch: pytest.MonkeyPatch,
    attempted_calls: int | None,
) -> None:
    _install_catalog(monkeypatch)
    details = (
        {"provider_calls_attempted": attempted_calls}
        if attempted_calls is not None
        else None
    )
    monkeypatch.setattr(
        smoke,
        "recognize_video",
        lambda source, **kwargs: _build_outcome(
            Path(kwargs["output_dir"]),
            private_markdown="PRIVATE",
            frame_error=ProviderError(
                code="PROVIDER_UNAVAILABLE",
                details=details,
            ),
        ),
    )

    summary = smoke.run_google_genai_video_smoke(_arguments())

    assert summary["frames"]["provider_calls_attempted"] == attempted_calls
    assert summary["frames"]["errors"] == [
        {
            "code": "PROVIDER_UNAVAILABLE",
            "stage": "frame_recognition",
            "provider_calls_attempted": attempted_calls,
        }
    ]
    assert summary["status"] == "failed"


def test_video_smoke_reports_audio_extraction_failure_as_zero_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_catalog(monkeypatch)

    monkeypatch.setattr(
        smoke,
        "recognize_video",
        lambda source, **kwargs: _build_outcome(
            Path(kwargs["output_dir"]),
            private_markdown="PRIVATE",
            audio_error=VideoError(code="VIDEO_INVALID"),
            keep_audio_artifact=False,
        ),
    )

    summary = smoke.run_google_genai_video_smoke(_arguments())

    assert summary["audio"] == {
        "status": "failed",
        "artifact_present": False,
        "provider_calls_attempted": 0,
        "error": {
            "code": "VIDEO_INVALID",
            "stage": "video_extract_audio",
            "provider_calls_attempted": 0,
        },
    }


def test_video_smoke_does_not_compose_when_both_branches_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_catalog(monkeypatch)

    def fake_recognize_video(source, *, output_dir, image_config, audio_config):
        return _build_outcome(
            Path(output_dir),
            private_markdown="PRIVATE",
            frame_error=ProviderError(
                code="PROVIDER_UNAVAILABLE",
                details={"provider_calls_attempted": 1},
            ),
            audio_error=ProviderError(
                code="PROVIDER_RESPONSE_INVALID",
                details={"provider_calls_attempted": 1},
            ),
        )

    monkeypatch.setattr(smoke, "recognize_video", fake_recognize_video)

    summary = smoke.run_google_genai_video_smoke(_arguments())

    assert summary["report_type"] == "video_outcome"
    assert summary["outcome_status"] == "failed"
    assert summary["frames"]["provider_calls_attempted"] == 1
    assert summary["audio"]["provider_calls_attempted"] == 1
    assert summary["composition"] == {
        "status": "not_started",
        "asset_count": 0,
        "error": None,
    }


def test_video_smoke_reports_silent_video_without_audio_dispatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_catalog(monkeypatch)
    monkeypatch.setattr(
        smoke,
        "recognize_video",
        lambda source, **kwargs: _build_outcome(
            Path(kwargs["output_dir"]),
            private_markdown="PRIVATE",
            audio_error=VideoError(code="VIDEO_NO_AUDIO_STREAM"),
            keep_audio_artifact=False,
        ),
    )

    summary = smoke.run_google_genai_video_smoke(_arguments())

    assert summary["outcome_status"] == "complete"
    assert summary["audio"] == {
        "status": "absent",
        "artifact_present": False,
        "provider_calls_attempted": 0,
        "error": {
            "code": "VIDEO_NO_AUDIO_STREAM",
            "stage": "video_extract_audio",
            "provider_calls_attempted": 0,
        },
    }
    assert summary["composition"]["status"] == "complete"
    assert summary["status"] == "failed"


def test_video_smoke_preserves_branches_when_composition_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_catalog(monkeypatch)
    private_text = "PRIVATE COMPOSITION FAILURE"
    observed_roots: list[Path] = []

    def fake_recognize_video(source, **kwargs):
        observed_roots.append(Path(kwargs["output_dir"]).parent)
        return _build_outcome(
            Path(kwargs["output_dir"]),
            private_markdown="PRIVATE",
        )

    monkeypatch.setattr(
        smoke,
        "recognize_video",
        fake_recognize_video,
    )
    monkeypatch.setattr(
        smoke,
        "compose_video_result",
        lambda outcome: (_ for _ in ()).throw(RuntimeError(private_text)),
    )

    summary = smoke.run_google_genai_video_smoke(_arguments())

    assert summary["frames"]["provider_calls_attempted"] == 1
    assert summary["audio"]["provider_calls_attempted"] == 1
    assert summary["composition"] == {
        "status": "failed",
        "asset_count": 0,
        "error": {
            "code": "UNEXPECTED_SAFE_FAILURE",
            "stage": "composition",
            "provider_calls_attempted": 0,
        },
    }
    assert summary["status"] == "failed"
    assert private_text not in json.dumps(summary, sort_keys=True)
    assert observed_roots and all(not root.exists() for root in observed_roots)


def test_video_smoke_rejects_provider_failure_without_audio_artifact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_catalog(monkeypatch)
    monkeypatch.setattr(
        smoke,
        "recognize_video",
        lambda source, **kwargs: _build_outcome(
            Path(kwargs["output_dir"]),
            private_markdown="PRIVATE",
            audio_error=ProviderError(
                code="PROVIDER_UNAVAILABLE",
                details={"provider_calls_attempted": 1},
            ),
            keep_audio_artifact=False,
        ),
    )

    with pytest.raises(smoke._LiveSmokeFailure) as failure:
        smoke.run_google_genai_video_smoke(_arguments())

    assert failure.value.stage == "video_orchestration"
    assert failure.value.error is not None
    assert failure.value.error.code == "CONFIG_INVALID"


@pytest.mark.parametrize("branch", ["frame", "audio"])
def test_video_smoke_rejects_persisted_branch_results_and_cleans_artifacts(
    monkeypatch: pytest.MonkeyPatch,
    branch: str,
) -> None:
    _install_catalog(monkeypatch)
    observed_roots: list[Path] = []

    def fake_recognize_video(source, **kwargs):
        observed_roots.append(Path(kwargs["output_dir"]).parent)
        return _build_outcome(
            Path(kwargs["output_dir"]),
            private_markdown="PRIVATE",
            frame_output_path=(Path("private-frame.md") if branch == "frame" else None),
            audio_output_path=(Path("private-audio.md") if branch == "audio" else None),
        )

    monkeypatch.setattr(smoke, "recognize_video", fake_recognize_video)

    with pytest.raises(smoke._LiveSmokeFailure) as failure:
        smoke.run_google_genai_video_smoke(_arguments())

    assert failure.value.error is not None
    assert failure.value.error.code == "CONFIG_INVALID"
    assert observed_roots and all(not root.exists() for root in observed_roots)


def test_video_smoke_main_redacts_unexpected_failure(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    secret = "PRIVATE UNEXPECTED VIDEO FAILURE"
    monkeypatch.setattr(
        smoke,
        "run_google_genai_video_smoke",
        lambda arguments: (_ for _ in ()).throw(RuntimeError(secret)),
    )

    assert (
        smoke.main(
            [
                "--image-model",
                IMAGE_MODEL,
                "--audio-model",
                AUDIO_MODEL,
                "--expected-audio-transport",
                "google_inline",
                "--video",
                "private-name.mp4",
                "--expected-frame-groups",
                "1",
            ]
        )
        == 1
    )
    raw = capsys.readouterr().out
    assert json.loads(raw) == {
        "report_type": "runner_failure",
        "status": "failed",
        "error": {
            "code": "UNEXPECTED_SAFE_FAILURE",
            "stage": None,
            "provider_calls_attempted": None,
        },
    }
    assert secret not in raw
    assert "private-name.mp4" not in raw
