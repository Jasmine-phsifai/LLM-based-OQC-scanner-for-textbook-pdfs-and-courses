"""Public whole-file long-audio persistence and resume behavior."""

from __future__ import annotations

from contextlib import contextmanager
from hashlib import sha256
import os
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest

from ocrllm import AudioModelSettings, Config, GoogleGenAISettings, recognize_long_mp3
from ocrllm.audio.fingerprint_long_audio_request import (
    LONG_AUDIO_REQUEST_IDENTITY_VERSION,
    fingerprint_long_audio_request,
)
from ocrllm.audio.load_long_audio_partial_state import load_long_audio_partial_state
from ocrllm.audio.long_audio_partial_state import (
    LONG_AUDIO_PARTIAL_STATE_VERSION,
    LongAudioPartialState,
)
from ocrllm.audio.long_audio_settled_slot import LongAudioSettledSlot
from ocrllm.audio.save_long_audio_partial_state_atomically import (
    save_long_audio_partial_state_atomically,
)
from ocrllm.errors import (
    NoSpeechDetected,
    OutputError,
    OutputExists,
    ResumeStateError,
)


MODEL = "gemini-test-whole-audio"
SOURCE_SHA256 = "a" * 64


def _config(output_dir: Path, *, resume: bool = False, model: str = MODEL) -> Config:
    return Config(
        provider=GoogleGenAISettings(api_key="test-only-google-key"),
        audio_model=AudioModelSettings(name=model),
        output_dir=output_dir,
        resume=resume,
    )


def _install_fakes(
    monkeypatch,
    provider_calls: list[str],
    *,
    snapshot_cleanup_error: bool = False,
) -> tuple[object, object]:
    processor = __import__(
        "ocrllm.processors.recognize_long_mp3",
        fromlist=["recognize_long_mp3"],
    )
    whole_processor = __import__(
        "ocrllm.processors.recognize_long_mp3_whole",
        fromlist=["recognize_long_mp3_whole"],
    )

    @contextmanager
    def fake_snapshot(source: Path, *, temp_dir):
        assert temp_dir is None
        try:
            yield SimpleNamespace(
                path=source,
                byte_size=12_345,
                sha256=SOURCE_SHA256,
                duration_seconds=601.5,
            )
        finally:
            if snapshot_cleanup_error:
                raise OutputError(
                    "The validated audio snapshot could not be removed after use.",
                    code="OUTPUT_WRITE_FAILED",
                )

    def fake_provider(snapshot, *, prompt, config):
        provider_calls.append(config.audio_model.name)
        return SimpleNamespace(
            markdown="# Whole transcript\n\n$x^2+y^2$",
            input_tokens=101,
            output_tokens=17,
            remote_file_deleted=True,
            client_closed=True,
        )

    monkeypatch.setattr(processor, "snapshot_long_mp3", fake_snapshot)
    monkeypatch.setattr(whole_processor, "recognize_uploaded_mp3", fake_provider)
    return processor, whole_processor


def _root(output_dir: Path) -> Path:
    return output_dir / "lecture"


def _state_path(output_dir: Path) -> Path:
    return _root(output_dir) / ".ocrllm-long-audio-resume.json"


def test_new_whole_run_saves_before_atomic_publication_then_removes_state(
    tmp_path: Path,
    monkeypatch,
) -> None:
    output_dir = tmp_path / "out"
    provider_calls: list[str] = []
    processor, _whole_processor = _install_fakes(monkeypatch, provider_calls)
    events: list[str] = []
    output_module = __import__(
        "ocrllm.output.write_markdown_atomically",
        fromlist=["write_markdown_atomically"],
    )
    state_module = __import__(
        "ocrllm.audio.save_long_audio_partial_state_atomically",
        fromlist=["save_long_audio_partial_state_atomically"],
    )

    def observed_save(path, state):
        events.append("state")
        state_module.save_long_audio_partial_state_atomically(path, state)

    def observed_publish(path, markdown, *, overwrite):
        assert _state_path(output_dir).is_file()
        events.append("result")
        output_module.write_markdown_atomically(path, markdown, overwrite=overwrite)

    monkeypatch.setattr(
        processor,
        "save_long_audio_partial_state_atomically",
        observed_save,
    )
    monkeypatch.setattr(
        processor,
        "write_markdown_atomically",
        observed_publish,
        raising=False,
    )

    result = recognize_long_mp3(
        tmp_path / "lecture.mp3",
        config=_config(output_dir),
    )

    assert provider_calls == [MODEL]
    assert events == ["state", "result"]
    assert result.output_path == _root(output_dir) / "result.md"
    assert result.output_path.read_text(encoding="utf-8") == result.markdown
    assert not _state_path(output_dir).exists()
    assert result.metadata["current_run_provider_call_count"] == 1
    assert result.metadata["remote_file_deleted"] is True
    assert result.metadata["provider_client_closed"] is True


def test_whole_state_removal_failure_keeps_published_partial_result(
    tmp_path: Path,
    monkeypatch,
) -> None:
    output_dir = tmp_path / "out"
    provider_calls: list[str] = []
    _install_fakes(monkeypatch, provider_calls)
    state_path = _state_path(output_dir)
    real_unlink = Path.unlink

    def fail_state_unlink(path: Path, *args, **kwargs):
        if path == state_path:
            raise PermissionError("injected-state-unlink-failure")
        return real_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fail_state_unlink)

    result = recognize_long_mp3(
        tmp_path / "lecture.mp3",
        config=_config(output_dir),
    )

    assert provider_calls == [MODEL]
    assert result.status == "partial"
    assert result.output_path == _root(output_dir) / "result.md"
    assert result.output_path.read_text(encoding="utf-8") == result.markdown
    assert state_path.is_file()
    assert result.metadata["resume_state_removed"] is False
    assert result.metadata["current_run_provider_call_count"] == 1
    assert result.metadata["remote_file_deleted"] is True
    assert result.metadata["provider_client_closed"] is True
    assert result.warnings == (
        "The temporary long-audio resume state could not be removed.",
    )


def test_failed_publication_preserves_paid_state_for_zero_call_resume(
    tmp_path: Path,
    monkeypatch,
) -> None:
    output_dir = tmp_path / "out"
    provider_calls: list[str] = []
    processor, _ = _install_fakes(monkeypatch, provider_calls)
    output_module = __import__(
        "ocrllm.output.write_markdown_atomically",
        fromlist=["write_markdown_atomically"],
    )

    def fail_publication(*_args, **_kwargs):
        raise OutputError(
            "The requested Markdown output could not be written atomically.",
            code="OUTPUT_WRITE_FAILED",
        )

    monkeypatch.setattr(
        processor,
        "write_markdown_atomically",
        fail_publication,
        raising=False,
    )
    with pytest.raises(OutputError) as first_error:
        recognize_long_mp3(
            tmp_path / "lecture.mp3",
            config=_config(output_dir),
        )

    assert first_error.value.details["provider_calls_attempted"] == 1
    assert first_error.value.details["settled_model_usage"] == (
        {
            "model": MODEL,
            "input_count": 101,
            "output_count": 17,
            "unit": "tokens",
        },
    )
    assert first_error.value.details["remote_file_deleted"] is True
    assert first_error.value.details["provider_client_closed"] is True
    assert provider_calls == [MODEL]
    assert _state_path(output_dir).is_file()
    assert not (_root(output_dir) / "result.md").exists()

    monkeypatch.setattr(
        processor,
        "write_markdown_atomically",
        output_module.write_markdown_atomically,
        raising=False,
    )
    result = recognize_long_mp3(
        tmp_path / "lecture.mp3",
        config=_config(output_dir, resume=True),
    )

    assert provider_calls == [MODEL]
    assert result.markdown == "# Whole transcript\n\n$x^2+y^2$"
    assert result.metadata["current_run_provider_call_count"] == 0
    assert result.metadata["current_model_token_usage"] == ()
    assert result.metadata["historical_model_token_usage"] == (
        {"model": MODEL, "input_tokens": 101, "output_tokens": 17},
    )
    assert result.metadata["remote_file_deleted"] is True
    assert result.metadata["provider_client_closed"] is True
    assert result.output_path is not None and result.output_path.is_file()
    assert not _state_path(output_dir).exists()


def test_whole_no_speech_is_settled_and_replayed_without_provider_call(
    tmp_path: Path,
    monkeypatch,
) -> None:
    output_dir = tmp_path / "out"
    provider_calls: list[str] = []
    _processor, whole_processor = _install_fakes(monkeypatch, provider_calls)

    def no_speech_provider(_snapshot, *, prompt, config):
        provider_calls.append(config.audio_model.name)
        raise NoSpeechDetected(
            details={
                "provider": "google",
                "model": MODEL,
                "provider_calls_attempted": 1,
                "settled_model_usage": (
                    {
                        "model": MODEL,
                        "input_count": 101,
                        "output_count": 17,
                        "unit": "tokens",
                    },
                ),
                "remote_file_deleted": True,
                "provider_client_closed": True,
            }
        )

    monkeypatch.setattr(
        whole_processor,
        "recognize_uploaded_mp3",
        no_speech_provider,
    )

    with pytest.raises(NoSpeechDetected) as first_error:
        recognize_long_mp3(
            tmp_path / "lecture.mp3",
            config=_config(output_dir),
        )

    assert first_error.value.details["provider_calls_attempted"] == 1
    assert first_error.value.details["settled_model_usage"] == (
        {
            "model": MODEL,
            "input_count": 101,
            "output_count": 17,
            "unit": "tokens",
        },
    )
    assert provider_calls == [MODEL]
    assert _state_path(output_dir).is_file()
    saved_state = load_long_audio_partial_state(_state_path(output_dir))
    assert saved_state is not None
    assert saved_state.slots[0].input_tokens == 101
    assert saved_state.slots[0].output_tokens == 17
    assert not (_root(output_dir) / "result.md").exists()

    with pytest.raises(NoSpeechDetected) as resumed_error:
        recognize_long_mp3(
            tmp_path / "lecture.mp3",
            config=_config(output_dir, resume=True),
        )

    assert resumed_error.value.details["provider_calls_attempted"] == 0
    assert "settled_model_usage" not in resumed_error.value.details
    assert resumed_error.value.details["remote_file_deleted"] is True
    assert resumed_error.value.details["provider_client_closed"] is True
    assert provider_calls == [MODEL]
    assert _state_path(output_dir).is_file()
    assert not (_root(output_dir) / "result.md").exists()


def test_whole_state_save_failure_reports_the_completed_provider_call(
    tmp_path: Path,
    monkeypatch,
) -> None:
    output_dir = tmp_path / "out"
    provider_calls: list[str] = []
    processor, _whole_processor = _install_fakes(monkeypatch, provider_calls)

    def fail_state_save(*_args, **_kwargs):
        raise OutputError(
            "The long-audio partial state could not be written atomically.",
            code="OUTPUT_WRITE_FAILED",
        )

    monkeypatch.setattr(
        processor,
        "save_long_audio_partial_state_atomically",
        fail_state_save,
    )

    with pytest.raises(OutputError) as captured:
        recognize_long_mp3(
            tmp_path / "lecture.mp3",
            config=_config(output_dir),
        )

    assert captured.value.details["provider_calls_attempted"] == 1
    assert captured.value.details["settled_model_usage"] == (
        {
            "model": MODEL,
            "input_count": 101,
            "output_count": 17,
            "unit": "tokens",
        },
    )
    assert captured.value.details["remote_file_deleted"] is True
    assert captured.value.details["provider_client_closed"] is True
    assert provider_calls == [MODEL]
    assert not _root(output_dir).exists()


def test_resume_request_mismatch_stops_before_provider_dispatch(
    tmp_path: Path,
    monkeypatch,
) -> None:
    output_dir = tmp_path / "out"
    provider_calls: list[str] = []
    processor, _ = _install_fakes(monkeypatch, provider_calls)

    def fail_publication(*_args, **_kwargs):
        raise OutputError(code="OUTPUT_WRITE_FAILED")

    monkeypatch.setattr(
        processor,
        "write_markdown_atomically",
        fail_publication,
        raising=False,
    )
    with pytest.raises(OutputError):
        recognize_long_mp3(tmp_path / "lecture.mp3", config=_config(output_dir))

    with pytest.raises(ResumeStateError) as mismatch:
        recognize_long_mp3(
            tmp_path / "lecture.mp3",
            config=_config(output_dir, resume=True, model="different-model"),
        )

    assert mismatch.value.code == "RESUME_STATE_MISMATCH"
    assert mismatch.value.details["provider_calls_attempted"] == 0
    assert provider_calls == [MODEL]


def test_new_run_collision_stops_before_snapshot_and_provider(
    tmp_path: Path,
    monkeypatch,
) -> None:
    output_dir = tmp_path / "out"
    _root(output_dir).mkdir(parents=True)
    provider_calls: list[str] = []
    processor, _ = _install_fakes(monkeypatch, provider_calls)
    snapshot_started = False

    def fail_snapshot(*_args, **_kwargs):
        nonlocal snapshot_started
        snapshot_started = True
        raise AssertionError("collision must stop before snapshot")

    monkeypatch.setattr(processor, "snapshot_long_mp3", fail_snapshot)

    with pytest.raises(OutputExists):
        recognize_long_mp3(tmp_path / "lecture.mp3", config=_config(output_dir))

    assert snapshot_started is False
    assert provider_calls == []


@pytest.mark.skipif(os.name != "nt", reason="Windows legacy path-limit regression")
def test_atomic_temporary_path_is_rejected_before_long_audio_provider(
    tmp_path: Path,
    monkeypatch,
) -> None:
    if _windows_path_units(tmp_path) >= 207:
        pytest.skip("pytest temporary root is already beyond the controlled range")
    output_dir = _make_directory_with_windows_path_units(tmp_path, 207)
    provider_calls: list[str] = []
    _install_fakes(monkeypatch, provider_calls)
    _enforce_legacy_windows_open_limit(monkeypatch)

    with pytest.raises(OutputError) as captured:
        recognize_long_mp3(
            tmp_path / "lecture.mp3",
            config=_config(output_dir),
        )

    assert captured.value.code == "OUTPUT_PATH_INVALID"
    assert provider_calls == []
    assert not (output_dir / "lecture").exists()


def test_paid_state_survives_snapshot_cleanup_failure(
    tmp_path: Path,
    monkeypatch,
) -> None:
    output_dir = tmp_path / "out"
    provider_calls: list[str] = []
    _install_fakes(monkeypatch, provider_calls, snapshot_cleanup_error=True)

    with pytest.raises(OutputError) as captured:
        recognize_long_mp3(tmp_path / "lecture.mp3", config=_config(output_dir))

    assert captured.value.details["provider_calls_attempted"] == 1
    assert provider_calls == [MODEL]
    assert _state_path(output_dir).is_file()
    assert not (_root(output_dir) / "result.md").exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows junction ownership regression")
def test_resume_rejects_junction_root_before_snapshot_or_provider(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source = tmp_path / "lecture.mp3"
    source.write_bytes(b"junction-owned-source")
    requested_output = tmp_path / "requested-output"
    external_root = tmp_path / "external-output" / "lecture"
    external_root.mkdir(parents=True)
    state_path = external_root / ".ocrllm-long-audio-resume.json"
    markdown = "# Paid transcript"
    request_fingerprint = fingerprint_long_audio_request(
        source_sha256=sha256(source.read_bytes()).hexdigest(),
        mode="whole",
        provider="google",
        model=MODEL,
        transport="google_files",
    )
    save_long_audio_partial_state_atomically(
        state_path,
        LongAudioPartialState(
            state_version=LONG_AUDIO_PARTIAL_STATE_VERSION,
            identity_version=LONG_AUDIO_REQUEST_IDENTITY_VERSION,
            mode="whole",
            interval_minutes=None,
            request_fingerprints=(request_fingerprint,),
            slots=(
                LongAudioSettledSlot(
                    window_index=0,
                    request_fingerprint=request_fingerprint,
                    markdown=markdown,
                    markdown_sha256=sha256(markdown.encode("utf-8")).hexdigest(),
                    provider="google",
                    model=MODEL,
                    transport="google_files",
                    provider_calls_attempted=1,
                    input_tokens=101,
                    output_tokens=17,
                    status="complete",
                    warnings=(),
                    provider_file_cleanup_succeeded=True,
                    provider_client_cleanup_succeeded=True,
                ),
            ),
        ),
    )
    state_before = state_path.read_bytes()
    requested_output.mkdir()
    junction_root = requested_output / "lecture"
    expected_target = os.path.normcase(os.path.realpath(external_root))
    junction_command = subprocess.run(
        [
            "cmd.exe",
            "/d",
            "/c",
            "mklink",
            "/J",
            os.fspath(junction_root),
            os.fspath(external_root),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if junction_command.returncode != 0:
        if (
            os.path.lexists(junction_root)
            and os.path.normcase(os.path.realpath(junction_root)) == expected_target
        ):
            junction_root.rmdir()
        pytest.skip("the Windows test environment cannot create a junction")

    try:
        actual_target = os.path.normcase(os.path.realpath(junction_root))
        assert junction_root.is_dir()
        assert actual_target == expected_target

        processor = __import__(
            "ocrllm.processors.recognize_long_mp3",
            fromlist=["recognize_long_mp3"],
        )
        whole_processor = __import__(
            "ocrllm.processors.recognize_long_mp3_whole",
            fromlist=["recognize_long_mp3_whole"],
        )
        snapshot_calls: list[str] = []
        provider_calls: list[str] = []

        def fail_snapshot(*_args, **_kwargs):
            snapshot_calls.append("snapshot")
            raise AssertionError("junction ownership must stop before snapshot")

        def fail_provider(*_args, **_kwargs):
            provider_calls.append("provider")
            raise AssertionError("junction ownership must stop before provider")

        monkeypatch.setattr(processor, "snapshot_long_mp3", fail_snapshot)
        monkeypatch.setattr(whole_processor, "recognize_uploaded_mp3", fail_provider)

        with pytest.raises(OutputError) as captured:
            recognize_long_mp3(
                source,
                config=_config(requested_output, resume=True),
            )

        assert captured.value.code == "OUTPUT_PATH_INVALID"
        assert snapshot_calls == []
        assert provider_calls == []
        assert not (external_root / "result.md").exists()
        assert state_path.read_bytes() == state_before
        assert tuple(path.name for path in external_root.iterdir()) == (
            state_path.name,
        )
        assert list(external_root.glob(".ocrllm-*.tmp")) == []
        assert list(requested_output.glob(".ocrllm-*.tmp")) == []
    finally:
        current_target = os.path.normcase(os.path.realpath(junction_root))
        if current_target == expected_target:
            junction_root.rmdir()
            assert not os.path.lexists(junction_root)


def _windows_path_units(path: Path) -> int:
    return len(str(path).encode("utf-16-le")) // 2


def _make_directory_with_windows_path_units(base: Path, target_units: int) -> Path:
    current = base
    while _windows_path_units(current) < target_units:
        remaining = target_units - _windows_path_units(current) - 1
        if remaining < 1:
            raise AssertionError("target path length cannot be reached")
        current /= "d" * min(40, remaining)
    assert _windows_path_units(current) == target_units
    current.mkdir(parents=True)
    return current


def _enforce_legacy_windows_open_limit(monkeypatch) -> None:
    original_open = Path.open

    def open_with_legacy_limit(path: Path, *args, **kwargs):
        if _windows_path_units(path) > 259:
            raise OSError(
                206,
                "test-only simulated legacy Windows path limit",
                str(path),
            )
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", open_with_legacy_limit)
