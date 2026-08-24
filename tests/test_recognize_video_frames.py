"""Public contract for recognizing library-owned retained video frames."""

from __future__ import annotations

from pathlib import Path

import pytest

from ocrllm import (
    Cancelled,
    Config,
    ConfigError,
    InvalidSource,
    RecognitionExecutionPolicy,
    RetainedVideoFrame,
    recognize_video_frames,
)
from ocrllm.errors import ProviderUnavailable

from write_test_image import write_test_image


class _RecordingProvider:
    def __init__(self, *, fail_on_call: int | None = None) -> None:
        self.fail_on_call = fail_on_call
        self.groups: list[tuple[str, ...]] = []

    def recognize_images(self, image_paths, *, prompt, config):
        self.groups.append(tuple(path.name for path in image_paths))
        if len(self.groups) == self.fail_on_call:
            raise ProviderUnavailable(details={"failure_scope": "provider"})
        return f"# Group {len(self.groups)}\n"


def _retained_frames(tmp_path: Path, count: int) -> tuple[RetainedVideoFrame, ...]:
    return tuple(
        RetainedVideoFrame(
            frame_index=index * 10,
            timestamp_seconds=float(index * 5),
            path=write_test_image(
                tmp_path / f"frame-{index:08d}.jpg",
                color=(index % 255, 0, 0),
            ),
        )
        for index in range(count)
    )


def test_recognize_video_frames_groups_at_eight_and_preserves_order(
    tmp_path: Path,
) -> None:
    frames = _retained_frames(tmp_path, 17)
    provider = _RecordingProvider()

    outcomes = recognize_video_frames(frames, config=Config(provider=provider))

    assert [len(group) for group in provider.groups] == [8, 8, 1]
    assert [name for group in provider.groups for name in group] == [
        frame.path.name for frame in frames
    ]
    assert [outcome.index for outcome in outcomes] == [0, 1, 2]
    assert [outcome.succeeded for outcome in outcomes] == [True, True, True]
    assert [
        outcome.result.metadata["video_frame_indices"]
        for outcome in outcomes
        if outcome.result is not None
    ] == [tuple(range(0, 80, 10)), tuple(range(80, 160, 10)), (160,)]
    assert [
        outcome.result.metadata["video_frame_timestamps_seconds"]
        for outcome in outcomes
        if outcome.result is not None
    ] == [
        tuple(float(value) for value in range(0, 40, 5)),
        tuple(float(value) for value in range(40, 80, 5)),
        (80.0,),
    ]


def test_recognize_video_frames_respects_lower_image_limit(tmp_path: Path) -> None:
    frames = _retained_frames(tmp_path, 7)
    provider = _RecordingProvider()

    outcomes = recognize_video_frames(
        frames,
        config=Config(
            provider=provider,
            execution=RecognitionExecutionPolicy(maximum_images_per_request=3),
        ),
    )

    assert [len(group) for group in provider.groups] == [3, 3, 1]
    assert all(outcome.succeeded for outcome in outcomes)
    assert [
        outcome.result.metadata["video_frame_indices"]
        for outcome in outcomes
        if outcome.result is not None
    ] == [(0, 10, 20), (30, 40, 50), (60,)]


def test_recognize_video_frames_keeps_honest_failure_outcomes(tmp_path: Path) -> None:
    frames = _retained_frames(tmp_path, 17)
    provider = _RecordingProvider(fail_on_call=2)

    outcomes = recognize_video_frames(frames, config=Config(provider=provider))

    assert len(provider.groups) == 2
    assert outcomes[0].succeeded
    assert isinstance(outcomes[1].error, ProviderUnavailable)
    assert isinstance(outcomes[2].error, Cancelled)
    assert outcomes[1].error.details["video_frame_indices"] == tuple(
        range(80, 160, 10)
    )
    assert outcomes[1].error.details["video_frame_timestamps_seconds"] == tuple(
        float(value) for value in range(40, 80, 5)
    )
    assert outcomes[1].error.details["provider_calls_attempted"] == 1
    assert outcomes[2].error.details["video_frame_indices"] == (160,)
    assert outcomes[2].error.details["video_frame_timestamps_seconds"] == (80.0,)
    assert "provider_calls_attempted" not in outcomes[2].error.details


@pytest.mark.parametrize(
    "build_frames",
    (
        lambda frames: list(frames),
        lambda frames: (frame for frame in frames),
        lambda frames: type("FrameTuple", (tuple,), {})(frames),
    ),
)
def test_recognize_video_frames_requires_exact_tuple_before_dispatch(
    tmp_path: Path,
    build_frames,
) -> None:
    frames = _retained_frames(tmp_path, 1)
    provider = _RecordingProvider()

    with pytest.raises(InvalidSource):
        recognize_video_frames(build_frames(frames), config=Config(provider=provider))

    assert provider.groups == []


@pytest.mark.parametrize(
    "frames",
    (
        (),
        (object(),),
    ),
)
def test_recognize_video_frames_rejects_empty_or_foreign_members(frames) -> None:
    provider = _RecordingProvider()

    with pytest.raises(InvalidSource):
        recognize_video_frames(frames, config=Config(provider=provider))

    assert provider.groups == []


@pytest.mark.parametrize(
    "mutate",
    (
        lambda frames: (frames[1], frames[0]),
        lambda frames: (
            frames[0],
            RetainedVideoFrame(
                frame_index=frames[0].frame_index,
                timestamp_seconds=frames[1].timestamp_seconds,
                path=frames[1].path,
            ),
        ),
    ),
)
def test_recognize_video_frames_rejects_non_increasing_positions(
    tmp_path: Path,
    mutate,
) -> None:
    frames = _retained_frames(tmp_path, 2)
    provider = _RecordingProvider()

    with pytest.raises(InvalidSource):
        recognize_video_frames(mutate(frames), config=Config(provider=provider))

    assert provider.groups == []


def test_recognize_video_frames_preflights_every_image_before_dispatch(
    tmp_path: Path,
) -> None:
    frames = list(_retained_frames(tmp_path, 9))
    frames[-1].path.write_bytes(b"not a JPEG")
    provider = _RecordingProvider()

    with pytest.raises(InvalidSource):
        recognize_video_frames(tuple(frames), config=Config(provider=provider))

    assert provider.groups == []


@pytest.mark.parametrize(
    "config",
    (
        Config(output_dir="output"),
        Config(output_dir="output", resume=True),
        Config(overwrite=True),
    ),
)
def test_recognize_video_frames_rejects_persistence_options(config: Config) -> None:
    provider = _RecordingProvider()
    frames = (
        RetainedVideoFrame(
            frame_index=0,
            timestamp_seconds=0.0,
            path=Path("not-opened.jpg"),
        ),
    )

    with pytest.raises(ConfigError):
        recognize_video_frames(
            frames,
            config=Config(
                provider=provider,
                output_dir=config.output_dir,
                resume=config.resume,
                overwrite=config.overwrite,
            ),
        )

    assert provider.groups == []
