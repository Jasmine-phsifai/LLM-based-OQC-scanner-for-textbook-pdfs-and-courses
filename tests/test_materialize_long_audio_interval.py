"""One request-owned MP3 interval materialization lifecycle."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from ocrllm import DependencyMissing, InvalidSource, OutputError
from ocrllm.audio.build_long_audio_interval_windows import LongAudioIntervalWindow
from ocrllm.audio.decode_mp3_duration import decode_mp3_duration
from ocrllm.audio.materialize_long_audio_interval import (
    materialize_long_audio_interval,
)


def _ffmpeg_executable() -> Path:
    import imageio_ffmpeg

    return Path(imageio_ffmpeg.get_ffmpeg_exe())


def _write_mp3(path: Path, *, duration_seconds: int = 4) -> Path:
    completed = subprocess.run(
        [
            str(_ffmpeg_executable()),
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=440:sample_rate=44100:duration={duration_seconds}",
            "-c:a",
            "libmp3lame",
            "-b:a",
            "128k",
            str(path),
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
        timeout=30,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    assert completed.returncode == 0
    return path


def _window() -> LongAudioIntervalWindow:
    return LongAudioIntervalWindow(
        index=1,
        logical_start_seconds=1.25,
        logical_end_seconds=2.75,
        actual_start_seconds=1.0,
        actual_end_seconds=3.0,
    )


def test_materialize_long_audio_interval_yields_then_removes_real_mp3(
    tmp_path: Path,
) -> None:
    import miniaudio

    source = _write_mp3(tmp_path / "source.mp3")

    with materialize_long_audio_interval(source, window=_window()) as segment:
        assert segment.parent == source.parent
        assert segment != source
        assert segment.is_file()
        assert segment.stat().st_size > 0
        assert decode_mp3_duration(segment, backend=miniaudio) == pytest.approx(
            2.0,
            abs=0.1,
        )
        info = miniaudio.mp3_get_file_info(str(segment))
        assert info.nchannels == 1
        assert info.sample_rate == 16000

    assert source.is_file()
    assert not segment.exists()


def test_materialize_long_audio_interval_handles_long_owned_temp_path(
    tmp_path: Path,
) -> None:
    import miniaudio

    if sys.platform != "win32":
        pytest.skip("extended-length path regression is Windows-specific")
    owned_parent = Path("\\\\?\\" + str(tmp_path.resolve()))
    while len(str(owned_parent / "source.mp3")) <= 270:
        owned_parent /= "owned-audio-" + ("x" * 48)
    owned_parent.mkdir(parents=True)
    source = _write_mp3(owned_parent / "source.mp3")

    with materialize_long_audio_interval(source, window=_window()) as segment:
        assert len(str(segment)) > 260
        assert decode_mp3_duration(segment, backend=miniaudio) == pytest.approx(
            2.0,
            abs=0.1,
        )

    assert not segment.exists()


def test_materialize_long_audio_interval_uses_exact_actual_window(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "source.mp3"
    source.write_bytes(b"owned source")
    module = __import__(
        "ocrllm.audio.materialize_long_audio_interval",
        fromlist=["unused"],
    )
    observed: dict[str, object] = {}

    def fake_run(command, **kwargs):
        observed["command"] = command
        observed["kwargs"] = kwargs
        Path(command[-1]).write_bytes(b"segment")
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(
        module,
        "load_audio_ffmpeg_executable",
        lambda: Path("ffmpeg-test"),
    )
    monkeypatch.setattr(module.subprocess, "run", fake_run)

    with materialize_long_audio_interval(source, window=_window()) as segment:
        command = observed["command"]
        assert command[:5] == [
            "ffmpeg-test",
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
        ]
        assert command[command.index("-ss") + 1] == "1.000000"
        assert command[command.index("-t") + 1] == "2.000000"
        assert command[command.index("-i") + 1] == str(source)
        assert command[command.index("-ac") + 1] == "1"
        assert command[command.index("-ar") + 1] == "16000"
        assert command[command.index("-b:a") + 1] == "64k"
        assert command[command.index("-c:a") + 1] == "libmp3lame"
        assert Path(command[-1]) == segment
        assert observed["kwargs"]["timeout"] == 600

    assert not segment.exists()


def test_materialize_long_audio_interval_cleans_after_consumer_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "source.mp3"
    source.write_bytes(b"owned source")
    module = __import__(
        "ocrllm.audio.materialize_long_audio_interval",
        fromlist=["unused"],
    )

    def fake_run(command, **_kwargs):
        Path(command[-1]).write_bytes(b"segment")
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(
        module,
        "load_audio_ffmpeg_executable",
        lambda: Path("ffmpeg-test"),
    )
    monkeypatch.setattr(module.subprocess, "run", fake_run)

    with pytest.raises(RuntimeError, match="consumer failed"):
        with materialize_long_audio_interval(source, window=_window()) as segment:
            raise RuntimeError("consumer failed")

    assert not segment.exists()


def test_materialize_long_audio_interval_does_not_hide_cleanup_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "source.mp3"
    source.write_bytes(b"owned source")
    module = __import__(
        "ocrllm.audio.materialize_long_audio_interval",
        fromlist=["unused"],
    )
    real_unlink = Path.unlink

    def fake_run(command, **_kwargs):
        Path(command[-1]).write_bytes(b"segment")
        return subprocess.CompletedProcess(command, 0)

    def deny_interval_cleanup(path: Path, *args, **kwargs) -> None:
        if path.name.startswith(".ocrllm-long-audio-interval-"):
            raise PermissionError("test-only retained interval handle")
        real_unlink(path, *args, **kwargs)

    monkeypatch.setattr(
        module,
        "load_audio_ffmpeg_executable",
        lambda: Path("ffmpeg-test"),
    )
    monkeypatch.setattr(module.subprocess, "run", fake_run)
    monkeypatch.setattr(Path, "unlink", deny_interval_cleanup)

    with pytest.raises(OutputError) as captured:
        with materialize_long_audio_interval(source, window=_window()) as segment:
            assert segment.is_file()

    assert captured.value.code == "OUTPUT_WRITE_FAILED"
    assert source.read_bytes() == b"owned source"
    assert segment.read_bytes() == b"segment"
    real_unlink(segment)


def test_materialize_long_audio_interval_maps_ffmpeg_rejection_and_cleans(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "source.mp3"
    source.write_bytes(b"owned source")
    module = __import__(
        "ocrllm.audio.materialize_long_audio_interval",
        fromlist=["unused"],
    )
    output_paths: list[Path] = []

    def reject(command, **_kwargs):
        output_paths.append(Path(command[-1]))
        return subprocess.CompletedProcess(command, 1)

    monkeypatch.setattr(
        module,
        "load_audio_ffmpeg_executable",
        lambda: Path("ffmpeg-test"),
    )
    monkeypatch.setattr(module.subprocess, "run", reject)

    with pytest.raises(InvalidSource) as captured:
        with materialize_long_audio_interval(source, window=_window()):
            raise AssertionError("unreachable")

    assert captured.value.code == "SOURCE_INVALID"
    assert captured.value.details == {"stage": "interval_materialization"}
    assert len(output_paths) == 1
    assert not output_paths[0].exists()


def test_materialize_long_audio_interval_rejects_non_planner_window_before_backend(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = __import__(
        "ocrllm.audio.materialize_long_audio_interval",
        fromlist=["unused"],
    )
    monkeypatch.setattr(
        module,
        "load_audio_ffmpeg_executable",
        lambda: pytest.fail("backend must not load"),
    )

    with pytest.raises(TypeError, match="LongAudioIntervalWindow"):
        with materialize_long_audio_interval(
            tmp_path / "source.mp3",
            window=object(),
        ):
            raise AssertionError("unreachable")


def test_materialize_long_audio_interval_rejects_inconsistent_window_before_backend(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = __import__(
        "ocrllm.audio.materialize_long_audio_interval",
        fromlist=["unused"],
    )
    monkeypatch.setattr(
        module,
        "load_audio_ffmpeg_executable",
        lambda: pytest.fail("backend must not load"),
    )
    invalid = LongAudioIntervalWindow(
        index=0,
        logical_start_seconds=10.0,
        logical_end_seconds=20.0,
        actual_start_seconds=11.0,
        actual_end_seconds=21.0,
    )

    with pytest.raises(ValueError, match="inconsistent"):
        with materialize_long_audio_interval(
            tmp_path / "source.mp3",
            window=invalid,
        ):
            raise AssertionError("unreachable")


def test_audio_ffmpeg_loader_reports_the_audio_extra(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sys

    loader = __import__(
        "ocrllm.audio.load_audio_ffmpeg_executable",
        fromlist=["unused"],
    )
    monkeypatch.setitem(sys.modules, "imageio_ffmpeg", None)

    with pytest.raises(DependencyMissing) as captured:
        loader.load_audio_ffmpeg_executable()

    assert captured.value.details == {"extra": "audio"}
