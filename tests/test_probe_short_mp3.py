from __future__ import annotations

import importlib
import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from ocrllm.errors import InvalidSource


probe_module = importlib.import_module("ocrllm.audio.probe_short_mp3")
FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "audio" / "a1"


@dataclass(frozen=True)
class _FakeInfo:
    nchannels: int
    sample_rate: int
    num_frames: int


class _SizedChunk:
    def __init__(self, sample_count: int) -> None:
        self._sample_count = sample_count

    def __len__(self) -> int:
        return self._sample_count


class _FakeMiniaudio:
    def __init__(
        self,
        *,
        info: _FakeInfo,
        sample_counts: tuple[int, ...],
        metadata_error: Exception | None = None,
        stream_error: Exception | None = None,
    ) -> None:
        self.info = info
        self.sample_counts = sample_counts
        self.metadata_error = metadata_error
        self.stream_error = stream_error

    def mp3_get_file_info(self, _snapshot: str) -> _FakeInfo:
        if self.metadata_error is not None:
            raise self.metadata_error
        return self.info

    def mp3_stream_file(self, _snapshot: str, *, frames_to_read: int):
        assert frames_to_read == 4096
        for sample_count in self.sample_counts:
            yield _SizedChunk(sample_count)
        if self.stream_error is not None:
            raise self.stream_error


def _install_fake_backend(
    monkeypatch,
    *,
    reported_frames: int,
    decoded_frames: int,
    sample_rate: int = 10,
    channels: int = 1,
) -> None:
    backend = _FakeMiniaudio(
        info=_FakeInfo(
            nchannels=channels,
            sample_rate=sample_rate,
            num_frames=reported_frames,
        ),
        sample_counts=(
            () if decoded_frames == 0 else (decoded_frames * channels,)
        ),
    )
    monkeypatch.setattr(probe_module, "load_miniaudio", lambda: backend)


def test_probe_short_mp3_accepts_exact_five_minute_boundary(monkeypatch) -> None:
    _install_fake_backend(
        monkeypatch,
        reported_frames=3000,
        decoded_frames=3000,
    )

    assert probe_module.probe_short_mp3(Path("owned-snapshot.mp3")) == 300.0


def test_probe_short_mp3_rejects_one_frame_over_five_minutes(monkeypatch) -> None:
    _install_fake_backend(
        monkeypatch,
        reported_frames=3001,
        decoded_frames=3001,
    )

    with pytest.raises(InvalidSource) as caught:
        probe_module.probe_short_mp3(Path("owned-snapshot.mp3"))

    assert caught.value.code == "SOURCE_TOO_LARGE"
    assert caught.value.details == {
        "decoded_duration_seconds": 300.1,
        "maximum_duration_seconds": 300.0,
    }


def test_probe_short_mp3_rejects_zero_decoded_frames(monkeypatch) -> None:
    _install_fake_backend(
        monkeypatch,
        reported_frames=1,
        decoded_frames=0,
    )

    with pytest.raises(InvalidSource, match="no decodable audio frames") as caught:
        probe_module.probe_short_mp3(Path("owned-snapshot.mp3"))

    assert caught.value.code == "SOURCE_INVALID"
    assert caught.value.details == {}


def test_probe_short_mp3_uses_fully_decoded_duration_within_padding(
    monkeypatch,
) -> None:
    _install_fake_backend(
        monkeypatch,
        reported_frames=3001,
        decoded_frames=3000,
    )

    assert probe_module.probe_short_mp3(Path("owned-snapshot.mp3")) == 300.0


def test_probe_short_mp3_accepts_two_mpeg_frames_of_padding(monkeypatch) -> None:
    _install_fake_backend(
        monkeypatch,
        reported_frames=242304,
        decoded_frames=240000,
        sample_rate=48000,
    )

    assert probe_module.probe_short_mp3(Path("owned-snapshot.mp3")) == 5.0


def test_probe_short_mp3_accepts_exact_relative_padding_boundary(monkeypatch) -> None:
    _install_fake_backend(
        monkeypatch,
        reported_frames=28800,
        decoded_frames=26496,
        sample_rate=48000,
    )

    assert probe_module.probe_short_mp3(Path("owned-snapshot.mp3")) == 0.552


def test_probe_short_mp3_rejects_material_frame_count_difference(
    monkeypatch,
) -> None:
    _install_fake_backend(
        monkeypatch,
        reported_frames=242305,
        decoded_frames=240000,
        sample_rate=48000,
    )

    with pytest.raises(InvalidSource, match="differs materially") as caught:
        probe_module.probe_short_mp3(Path("owned-snapshot.mp3"))

    assert caught.value.code == "SOURCE_INVALID"
    assert caught.value.details == {
        "reported_frame_count": 242305,
        "decoded_frame_count": 240000,
    }


def test_probe_short_mp3_rejects_above_relative_padding_boundary(monkeypatch) -> None:
    _install_fake_backend(
        monkeypatch,
        reported_frames=28799,
        decoded_frames=26495,
        sample_rate=48000,
    )

    with pytest.raises(InvalidSource, match="differs materially") as caught:
        probe_module.probe_short_mp3(Path("owned-snapshot.mp3"))

    assert caught.value.code == "SOURCE_INVALID"


def test_probe_short_mp3_rejects_large_relative_difference(monkeypatch) -> None:
    _install_fake_backend(
        monkeypatch,
        reported_frames=2305,
        decoded_frames=1,
        sample_rate=48000,
    )

    with pytest.raises(InvalidSource, match="differs materially") as caught:
        probe_module.probe_short_mp3(Path("owned-snapshot.mp3"))

    assert caught.value.code == "SOURCE_INVALID"
    assert caught.value.details == {
        "reported_frame_count": 2305,
        "decoded_frame_count": 1,
    }


@pytest.mark.parametrize("failure_phase", ["metadata", "stream"])
def test_probe_short_mp3_redacts_backend_and_snapshot_failures(
    tmp_path,
    monkeypatch,
    failure_phase,
) -> None:
    secret = "secret-parent-sensitive-name.mp3"
    error = RuntimeError(secret)
    backend = _FakeMiniaudio(
        info=_FakeInfo(nchannels=1, sample_rate=10, num_frames=1),
        sample_counts=(1,),
        metadata_error=error if failure_phase == "metadata" else None,
        stream_error=error if failure_phase == "stream" else None,
    )
    monkeypatch.setattr(probe_module, "load_miniaudio", lambda: backend)

    with pytest.raises(InvalidSource) as caught:
        probe_module.probe_short_mp3(tmp_path / secret)

    assert str(caught.value) == (
        "The MP3 source is malformed or could not be decoded completely."
    )
    assert caught.value.code == "SOURCE_INVALID"
    assert caught.value.details == {}
    assert secret not in repr(caught.value)


@pytest.mark.parametrize(
    "fixture_name",
    ["valid_cbr.mp3", "valid_vbr.mp3", "valid_id3.mp3", "incomplete_tail.mp3"],
)
def test_probe_short_mp3_fully_decodes_committed_accepted_fixtures(
    fixture_name,
) -> None:
    pytest.importorskip("miniaudio")
    manifest = json.loads((FIXTURE_ROOT / "manifest.json").read_text("utf-8"))
    expected = {item["filename"]: item for item in manifest["fixtures"]}[
        fixture_name
    ]

    duration = probe_module.probe_short_mp3(FIXTURE_ROOT / "mp3" / fixture_name)

    assert duration == (
        expected["decoded_frame_count"] / expected["sample_rate_hz"]
    )


@pytest.mark.parametrize(
    "fixture_name",
    ["one_frame.mp3", "corrupted_middle.mp3"],
)
def test_probe_short_mp3_rejects_committed_invalid_fixtures(fixture_name) -> None:
    pytest.importorskip("miniaudio")

    with pytest.raises(InvalidSource) as caught:
        probe_module.probe_short_mp3(FIXTURE_ROOT / "mp3" / fixture_name)

    assert caught.value.code == "SOURCE_INVALID"


@pytest.mark.parametrize("payload", [b"", bytes(range(256)) * 4])
def test_probe_short_mp3_rejects_empty_and_junk_bytes(tmp_path, payload) -> None:
    pytest.importorskip("miniaudio")
    source = tmp_path / "invalid.mp3"
    source.write_bytes(payload)

    with pytest.raises(InvalidSource) as caught:
        probe_module.probe_short_mp3(source)

    assert caught.value.code == "SOURCE_INVALID"


def test_probe_short_mp3_rejects_non_interleaved_decoder_chunk(
    monkeypatch,
) -> None:
    backend = _FakeMiniaudio(
        info=_FakeInfo(nchannels=2, sample_rate=10, num_frames=1),
        sample_counts=(3,),
    )
    monkeypatch.setattr(probe_module, "load_miniaudio", lambda: backend)

    with pytest.raises(InvalidSource) as caught:
        probe_module.probe_short_mp3(Path("owned-snapshot.mp3"))

    assert caught.value.code == "SOURCE_INVALID"
