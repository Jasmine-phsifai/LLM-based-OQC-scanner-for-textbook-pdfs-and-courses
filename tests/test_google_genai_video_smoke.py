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
from ocrllm.errors import ProviderError, VideoError
from tools import run_google_genai_video_smoke as smoke


MODEL = "gemini-video-live-model"


def _frame_result(
    *,
    markdown: str,
    output_path: Path | None = None,
) -> RecognitionResult:
    return RecognitionResult(
        markdown=markdown,
        source_type="image",
        output_path=output_path,
        metadata={
            "provider": "google",
            "model": MODEL,
            "provider_call_count": 1,
            "video_frame_indices": (0,),
            "video_frame_timestamps_seconds": (0.0,),
        },
    )


def _audio_result(
    *,
    markdown: str,
    output_path: Path | None = None,
) -> RecognitionResult:
    return RecognitionResult(
        markdown=markdown,
        source_type="audio",
        output_path=output_path,
        metadata={
            "provider": "google",
            "model": MODEL,
            "provider_call_count": 1,
        },
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
) -> VideoRecognitionOutcome:
    output_root = output_dir / "video"
    frames_dir = output_root / "frames"
    frames_dir.mkdir(parents=True)
    frame_path = frames_dir / "frame-00000000.jpg"
    frame_path.write_bytes(b"jpeg")
    retained_frames = (
        RetainedVideoFrame(
            frame_index=0,
            timestamp_seconds=0.0,
            path=frame_path,
        ),
    )
    if frame_error is None:
        frame_outcomes = (
            BatchItemOutcome(
                index=0,
                result=_frame_result(
                    markdown=private_markdown,
                    output_path=frame_output_path,
                ),
            ),
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
            )
            if audio_error is None
            else None
        ),
        audio_error=audio_error,
    )


def _arguments() -> argparse.Namespace:
    return argparse.Namespace(
        model=MODEL,
        video=Path("private-video-name.mp4"),
        timeout=9.0,
    )


def _install_catalog(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        smoke,
        "list_google_genai_models",
        lambda settings, timeout_seconds: (MODEL,),
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
        assert image_config.vision_model.name == MODEL
        assert audio_config.audio_model.name == MODEL
        assert image_config.timeout_seconds == audio_config.timeout_seconds == 9.0
        return _build_outcome(
            Path(output_dir),
            private_markdown=private_markdown,
        )

    monkeypatch.setattr(smoke, "recognize_video", fake_recognize_video)

    summary = smoke.run_google_genai_video_smoke(_arguments())

    assert summary == {
        "status": "passed",
        "catalog_count": 1,
        "model": MODEL,
        "outcome_status": "complete",
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
        },
    }
    assert summary["composition"]["status"] == "partial"
    raw = json.dumps(summary, sort_keys=True)
    assert private_text not in raw
    assert observed_roots and all(not root.exists() for root in observed_roots)


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

    assert smoke.main(["--model", MODEL, "--video", "private-name.mp4"]) == 1
    raw = capsys.readouterr().out
    assert json.loads(raw) == {
        "status": "failed",
        "error": {
            "code": "UNEXPECTED_SAFE_FAILURE",
            "stage": None,
            "provider_calls_attempted": None,
        },
    }
    assert secret not in raw
    assert "private-name.mp4" not in raw
