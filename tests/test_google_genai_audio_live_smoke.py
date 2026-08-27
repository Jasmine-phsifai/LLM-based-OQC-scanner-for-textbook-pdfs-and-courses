from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from types import MappingProxyType, SimpleNamespace

import pytest

from ocrllm.errors import ConfigError, InvalidSource, ProviderError
from tools import run_google_genai_audio_smoke as smoke


MODEL = "gemini-audio-live-model"
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_audio_live_smoke_cli_reports_missing_credential_without_network(tmp_path):
    environment = os.environ.copy()
    environment.pop("GOOGLE_API_KEY", None)
    environment.pop("GEMINI_API_KEY", None)
    source_path = tmp_path / "never-opened-audio-source.mp3"
    source_pythonpath = str(PROJECT_ROOT / "src")
    inherited_pythonpath = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = (
        os.pathsep.join((source_pythonpath, inherited_pythonpath))
        if inherited_pythonpath
        else source_pythonpath
    )

    completed = subprocess.run(
        (
            sys.executable,
            str(PROJECT_ROOT / "tools" / "run_google_genai_audio_smoke.py"),
            "--model",
            "never-requested-model",
            "--audio",
            str(source_path),
        ),
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )

    assert completed.returncode == 1
    assert completed.stderr == ""
    assert json.loads(completed.stdout) == {
        "error": {
            "code": "CONFIG_MISSING",
            "scope": None,
            "stage": "catalog",
        },
        "status": "failed",
    }
    assert not source_path.exists()


def test_audio_live_smoke_outputs_no_transcript_path_or_secret(monkeypatch, capsys):
    secret = "unit-test-google-audio-secret"
    transcript = "PRIVATE AUDIO TRANSCRIPT"
    source = "private-audio-name.mp3"
    list_api_keys = []
    monkeypatch.setenv("GOOGLE_API_KEY", secret)

    def fake_list(settings, timeout_seconds):
        list_api_keys.append(settings.api_key)
        if settings.api_key is not None:
            raise ProviderError(
                code="PROVIDER_AUTHENTICATION",
                details={"failure_scope": "credential"},
            )
        assert timeout_seconds == 9.0
        return (MODEL,)

    def fake_recognize(actual_source, *, config):
        assert str(actual_source) == source
        assert config.audio_model.name == MODEL
        return SimpleNamespace(
            markdown=transcript,
            source_type="audio",
            output_path=None,
            metadata=MappingProxyType(
                {
                    "provider": "google",
                    "model": MODEL,
                    "provider_call_count": 1,
                    "duration_seconds": 1.25,
                    "byte_size": 2048,
                    "current_model_token_usage": (
                        {"model": MODEL, "input_tokens": 21, "output_tokens": 8},
                    ),
                }
            ),
        )

    monkeypatch.setattr(smoke, "list_google_genai_models", fake_list)
    monkeypatch.setattr(smoke, "recognize", fake_recognize)

    assert smoke.main(
        ["--model", MODEL, "--audio", source, "--timeout", "9"]
    ) == 0
    raw = capsys.readouterr().out.strip()
    assert json.loads(raw) == {
        "catalog_count": 1,
        "model": MODEL,
        "recognition": {
            "input_tokens": 21,
            "model": MODEL,
            "output_tokens": 8,
            "provider_call_count": 1,
        },
        "status": "passed",
    }
    assert list_api_keys == [None]
    assert secret not in raw
    assert transcript not in raw
    assert source not in raw


def test_audio_live_smoke_long_mode_requires_complete_deleted_files_lifecycle(
    monkeypatch,
    capsys,
) -> None:
    transcript = "PRIVATE LONG AUDIO TRANSCRIPT"
    source = "private-long-audio-name.mp3"
    monkeypatch.setattr(
        smoke,
        "list_google_genai_models",
        lambda settings, timeout_seconds: (MODEL,),
    )

    def fake_long_recognize(actual_source, *, config):
        assert str(actual_source) == source
        return SimpleNamespace(
            markdown=transcript,
            source_type="audio",
            status="complete",
            output_path=None,
            metadata=MappingProxyType(
                {
                    "provider": "google",
                    "model": MODEL,
                    "transport": "google_files",
                    "provider_call_count": 1,
                    "duration_seconds": 301.0,
                    "byte_size": 2048,
                    "remote_file_deleted": True,
                    "provider_client_closed": True,
                    "current_model_token_usage": (
                        {"model": MODEL, "input_tokens": 21, "output_tokens": 8},
                    ),
                }
            ),
        )

    monkeypatch.setattr(smoke, "recognize_long_mp3", fake_long_recognize)

    assert smoke.main(
        ["--model", MODEL, "--audio", source, "--timeout", "9", "--long"]
    ) == 0
    raw = capsys.readouterr().out.strip()
    assert json.loads(raw)["recognition"] == {
        "input_tokens": 21,
        "model": MODEL,
        "output_tokens": 8,
        "provider_call_count": 1,
        "remote_file_deleted": True,
        "transport": "google_files",
    }
    assert transcript not in raw
    assert source not in raw


def test_audio_live_smoke_interval_mode_requires_explicit_long_output_boundary(
    tmp_path: Path,
) -> None:
    with pytest.raises(SystemExit):
        smoke.parse_arguments(
            [
                "--model",
                MODEL,
                "--audio",
                "lecture.mp3",
                "--interval-minutes",
                "6",
                "--output-dir",
                str(tmp_path),
            ]
        )
    with pytest.raises(SystemExit):
        smoke.parse_arguments(
            ["--model", MODEL, "--audio", "lecture.mp3", "--resume"]
        )
    with pytest.raises(SystemExit):
        smoke.parse_arguments(
            [
                "--model",
                MODEL,
                "--audio",
                "lecture.mp3",
                "--long",
                "--interval-minutes",
                "6",
            ]
        )
    with pytest.raises(SystemExit):
        smoke.parse_arguments(
            [
                "--model",
                MODEL,
                "--audio",
                "lecture.mp3",
                "--long",
                "--interval-minutes",
                "0",
                "--output-dir",
                str(tmp_path),
            ]
        )


def test_audio_live_smoke_interval_mode_reports_only_safe_two_call_facts(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    secret = "unit-test-google-interval-secret"
    transcript = "PRIVATE INTERVAL TRANSCRIPT"
    source = "private-interval-audio-name.mp3"
    output_dir = tmp_path / "published"
    output_path = output_dir / "private-interval-audio-name" / "result.md"
    output_path.parent.mkdir(parents=True)
    output_path.write_text(transcript, encoding="utf-8")
    monkeypatch.setenv("GOOGLE_API_KEY", secret)
    monkeypatch.setattr(
        smoke,
        "list_google_genai_models",
        lambda settings, timeout_seconds: (MODEL,),
    )

    def fake_long_recognize(
        actual_source,
        *,
        config,
        interval_minutes,
    ):
        assert str(actual_source) == source
        assert config.output_directory() == output_dir
        assert interval_minutes == 6
        return SimpleNamespace(
            markdown=transcript,
            source_type="audio",
            status="complete",
            output_path=output_path,
            metadata=MappingProxyType(
                {
                    "provider": "google",
                    "model": MODEL,
                    "transport": "google_files",
                    "provider_call_count": 2,
                    "current_run_provider_call_count": 2,
                    "duration_seconds": 601.0,
                    "byte_size": 4096,
                    "remote_file_deleted": True,
                    "provider_client_closed": True,
                    "current_model_token_usage": (
                        {"model": MODEL, "input_tokens": 202, "output_tokens": 19},
                    ),
                }
            ),
        )

    monkeypatch.setattr(smoke, "recognize_long_mp3", fake_long_recognize)

    assert smoke.main(
        [
            "--model",
            MODEL,
            "--audio",
            source,
            "--timeout",
            "9",
            "--long",
            "--interval-minutes",
            "6",
            "--output-dir",
            str(output_dir),
        ]
    ) == 0
    raw = capsys.readouterr().out.strip()
    assert json.loads(raw)["recognition"] == {
        "current_run_provider_call_count": 2,
        "input_tokens": 202,
        "interval_minutes": 6,
        "model": MODEL,
        "output_tokens": 19,
        "provider_call_count": 2,
        "remote_file_deleted": True,
        "result_published": True,
        "resume": False,
        "transport": "google_files",
    }
    assert secret not in raw
    assert transcript not in raw
    assert source not in raw
    assert str(output_dir) not in raw


def test_audio_live_smoke_interval_resume_reports_reused_call_boundary(
    tmp_path: Path,
    monkeypatch,
) -> None:
    output_dir = tmp_path / "published"
    output_path = output_dir / "lecture" / "result.md"
    output_path.parent.mkdir(parents=True)
    output_path.write_text("synthetic transcript", encoding="utf-8")
    monkeypatch.setattr(
        smoke,
        "list_google_genai_models",
        lambda settings, timeout_seconds: (MODEL,),
    )

    def fake_resume(actual_source, *, config, interval_minutes):
        assert config.resume is True
        return SimpleNamespace(
            source_type="audio",
            status="complete",
            output_path=output_path,
            metadata=MappingProxyType(
                {
                    "provider": "google",
                    "model": MODEL,
                    "transport": "google_files",
                    "provider_call_count": 2,
                    "current_run_provider_call_count": 1,
                    "duration_seconds": 601.0,
                    "byte_size": 4096,
                    "remote_file_deleted": True,
                    "provider_client_closed": True,
                    "current_model_token_usage": (
                        {"model": MODEL, "input_tokens": 100, "output_tokens": 10},
                    ),
                }
            ),
        )

    monkeypatch.setattr(smoke, "recognize_long_mp3", fake_resume)
    arguments = smoke.parse_arguments(
        [
            "--model",
            MODEL,
            "--audio",
            "lecture.mp3",
            "--long",
            "--interval-minutes",
            "6",
            "--output-dir",
            str(output_dir),
            "--resume",
        ]
    )
    summary = smoke.run_google_genai_audio_smoke(arguments)

    assert summary["recognition"]["provider_call_count"] == 2
    assert summary["recognition"]["current_run_provider_call_count"] == 1
    assert summary["recognition"]["resume"] is True


def test_audio_live_interval_summary_rejects_unremoved_temporary_state(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "lecture" / "result.md"
    output_path.parent.mkdir()
    output_path.write_text("private transcript", encoding="utf-8")
    (output_path.parent / ".ocrllm-long-audio-resume.json").write_text(
        "private state",
        encoding="utf-8",
    )
    result = SimpleNamespace(
        source_type="audio",
        status="complete",
        output_path=output_path,
        metadata=MappingProxyType({}),
    )

    with pytest.raises(ConfigError):
        smoke._safe_recognition_summary(
            result,
            MODEL,
            require_google_files=True,
            interval_minutes=6,
            expected_output_dir=tmp_path,
        )


@pytest.mark.parametrize("failure_stage", ["catalog", "recognition"])
def test_audio_live_smoke_reports_sanitized_provider_failure_stage(
    failure_stage, monkeypatch, capsys
):
    secret = "PRIVATE-GOOGLE-STAGE-FAILURE"
    source = "private-stage-source.mp3"

    def failure():
        return ProviderError(
            secret,
            code="PROVIDER_UNAVAILABLE",
            details={
                "failure_scope": "provider",
                "http_status": 400,
                "provider_status": "FAILED_PRECONDITION",
                "raw_response": secret,
            },
        )

    def fake_list(settings, timeout_seconds):
        if failure_stage == "catalog":
            raise failure()
        return (MODEL,)

    def fake_recognize(actual_source, *, config):
        raise failure()

    monkeypatch.setattr(smoke, "list_google_genai_models", fake_list)
    monkeypatch.setattr(smoke, "recognize", fake_recognize)

    assert smoke.main(["--model", MODEL, "--audio", source]) == 1
    raw = capsys.readouterr().out.strip()
    assert json.loads(raw) == {
        "error": {
            "code": "PROVIDER_UNAVAILABLE",
            "http_status": 400,
            "provider_status": "FAILED_PRECONDITION",
            "scope": "provider",
            "stage": failure_stage,
        },
        "status": "failed",
    }
    assert secret not in raw
    assert source not in raw


def test_audio_live_smoke_omits_untrusted_provider_status_fields(
    monkeypatch, capsys
):
    secret = "PRIVATE STATUS WITH PUNCTUATION!"

    def fail_catalog(settings, timeout_seconds):
        raise ProviderError(
            code="PROVIDER_REQUEST_INVALID",
            details={
                "failure_scope": "request",
                "http_status": True,
                "provider_status": secret,
            },
        )

    monkeypatch.setattr(smoke, "list_google_genai_models", fail_catalog)

    assert smoke.main(["--model", MODEL, "--audio", "private.mp3"]) == 1
    raw = capsys.readouterr().out
    assert json.loads(raw) == {
        "error": {
            "code": "PROVIDER_REQUEST_INVALID",
            "scope": "request",
            "stage": "catalog",
        },
        "status": "failed",
    }
    assert secret not in raw


def test_audio_live_smoke_reports_default_disposition_and_cleanup(
    monkeypatch, capsys
):
    monkeypatch.setattr(
        smoke,
        "list_google_genai_models",
        lambda settings, timeout_seconds: (MODEL,),
    )

    def fail_after_owned_cleanup(actual_source, *, config):
        raise ProviderError(
            code="PROVIDER_RESPONSE_INVALID",
            details={
                "remote_file_deleted": True,
                "provider_client_closed": True,
                "provider_operation": "upload",
                "provider_sdk_type": "RuntimeError",
            },
        )

    monkeypatch.setattr(smoke, "recognize_long_mp3", fail_after_owned_cleanup)

    assert smoke.main(
        ["--model", MODEL, "--audio", "private.mp3", "--long"]
    ) == 1
    assert json.loads(capsys.readouterr().out) == {
        "cleanup": {
            "provider_client_closed": True,
            "remote_file_deleted": True,
        },
        "error": {
            "code": "PROVIDER_RESPONSE_INVALID",
            "operation": "upload",
            "sdk_type": "RuntimeError",
            "scope": "request",
            "stage": "recognition",
        },
        "status": "failed",
    }


def test_audio_live_smoke_reports_safe_interval_failure_progress(
    monkeypatch, capsys
):
    monkeypatch.setattr(
        smoke,
        "list_google_genai_models",
        lambda settings, timeout_seconds: (MODEL,),
    )

    def fail_after_one_settled_interval(actual_source, *, config, interval_minutes):
        raise ProviderError(
            code="PROVIDER_RESPONSE_INVALID",
            details={
                "provider_calls_attempted": 2,
                "persisted_interval_count": 1,
                "remote_file_deleted": False,
                "provider_client_closed": True,
                "private_transcript": "must not leak",
                "private_path": str(actual_source),
            },
        )

    monkeypatch.setattr(smoke, "recognize_long_mp3", fail_after_one_settled_interval)

    assert smoke.main(
        [
            "--model",
            MODEL,
            "--audio",
            "private.mp3",
            "--long",
            "--interval-minutes",
            "6",
            "--output-dir",
            "private-output",
        ]
    ) == 1
    raw = capsys.readouterr().out
    assert json.loads(raw) == {
        "cleanup": {
            "provider_client_closed": True,
            "remote_file_deleted": False,
        },
        "error": {
            "code": "PROVIDER_RESPONSE_INVALID",
            "scope": "request",
            "stage": "recognition",
        },
        "progress": {
            "provider_calls_attempted": 2,
            "persisted_interval_count": 1,
        },
        "status": "failed",
    }
    assert "must not leak" not in raw
    assert "private.mp3" not in raw
    assert "private-output" not in raw


def test_audio_live_smoke_reports_missing_model_selection_stage(monkeypatch, capsys):
    monkeypatch.setattr(
        smoke,
        "list_google_genai_models",
        lambda settings, timeout_seconds: ("another-model",),
    )

    assert smoke.main(["--model", MODEL, "--audio", "private-source.mp3"]) == 1
    assert json.loads(capsys.readouterr().out) == {
        "error": {
            "code": "CONFIG_INVALID",
            "scope": None,
            "stage": "model_selection",
        },
        "status": "failed",
    }


def test_audio_live_smoke_reports_sanitized_source_failure(monkeypatch, capsys):
    secret = "PRIVATE-SOURCE-FAILURE"
    source = "private-missing-source.mp3"

    def raise_source_failure(actual_source, *, config):
        raise InvalidSource(secret, code="SOURCE_NOT_FOUND")

    monkeypatch.setattr(
        smoke,
        "list_google_genai_models",
        lambda settings, timeout_seconds: (MODEL,),
    )
    monkeypatch.setattr(smoke, "recognize", raise_source_failure)

    assert smoke.main(["--model", MODEL, "--audio", source]) == 1
    raw = capsys.readouterr().out.strip()
    assert json.loads(raw) == {
        "error": {
            "code": "SOURCE_NOT_FOUND",
            "scope": None,
            "stage": "recognition",
        },
        "status": "failed",
    }
    assert secret not in raw
    assert source not in raw


@pytest.mark.parametrize("failure_stage", ["catalog", "recognition"])
def test_audio_live_smoke_reports_sanitized_unexpected_failure(
    failure_stage, monkeypatch, capsys
):
    secret = "PRIVATE-UNEXPECTED-FAILURE"
    source = "private-unexpected-source.mp3"

    def fake_list(settings, timeout_seconds):
        if failure_stage == "catalog":
            raise RuntimeError(secret)
        return (MODEL,)

    def raise_unexpected_failure(actual_source, *, config):
        raise RuntimeError(secret)

    monkeypatch.setattr(smoke, "list_google_genai_models", fake_list)
    monkeypatch.setattr(smoke, "recognize", raise_unexpected_failure)

    assert smoke.main(["--model", MODEL, "--audio", source]) == 1
    raw = capsys.readouterr().out.strip()
    assert json.loads(raw) == {
        "error": {
            "code": "UNEXPECTED_SAFE_FAILURE",
            "scope": None,
            "stage": failure_stage,
        },
        "status": "failed",
    }
    assert secret not in raw
    assert source not in raw


def test_audio_live_summary_rejects_unproven_result_or_source_evidence():
    base_metadata = {
        "provider": "google",
        "model": MODEL,
        "provider_call_count": 1,
        "duration_seconds": 1.0,
        "byte_size": 10,
        "current_model_token_usage": (
            {"model": MODEL, "input_tokens": None, "output_tokens": None},
        ),
    }
    invalid_results = (
        SimpleNamespace(
            source_type="image",
            output_path=None,
            metadata=MappingProxyType(base_metadata),
        ),
        SimpleNamespace(
            source_type="audio",
            output_path="unexpected.md",
            metadata=MappingProxyType(base_metadata),
        ),
        SimpleNamespace(
            source_type="audio",
            output_path=None,
            metadata=MappingProxyType({**base_metadata, "duration_seconds": float("nan")}),
        ),
        SimpleNamespace(
            source_type="audio",
            output_path=None,
            metadata=MappingProxyType({**base_metadata, "byte_size": True}),
        ),
    )

    for result in invalid_results:
        with pytest.raises(ConfigError):
            smoke._safe_recognition_summary(result, MODEL)
