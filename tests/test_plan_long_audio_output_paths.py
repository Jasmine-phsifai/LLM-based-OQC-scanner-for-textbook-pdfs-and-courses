"""Plan deterministic long-audio publication paths without side effects."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from ocrllm.audio.plan_long_audio_output_paths import (
    plan_long_audio_output_paths,
)
from ocrllm.errors import OutputError


def test_plan_uses_one_normalized_same_name_directory(tmp_path: Path) -> None:
    source = tmp_path / "课程:公式.最终版.mp3"
    output_dir = tmp_path / "results"

    paths = plan_long_audio_output_paths(source, output_dir)

    assert paths.root == output_dir / "课程_公式.最终版"
    assert paths.result == paths.root / "result.md"
    assert paths.resume_state == paths.root / ".ocrllm-long-audio-resume.json"
    assert not output_dir.exists()


def test_plan_is_lifecycle_neutral_when_job_directory_exists(tmp_path: Path) -> None:
    output_dir = tmp_path / "results"
    existing_root = output_dir / "lecture"
    existing_root.mkdir(parents=True)

    paths = plan_long_audio_output_paths(tmp_path / "lecture.mp3", output_dir)

    assert paths.root == existing_root


def test_plan_allows_an_absent_output_directory(tmp_path: Path) -> None:
    output_dir = tmp_path / "not-created"

    plan_long_audio_output_paths(tmp_path / "lecture.mp3", output_dir)

    assert not output_dir.exists()


def test_plan_rejects_an_existing_nondirectory_output_parent(tmp_path: Path) -> None:
    output_dir = tmp_path / "occupied"
    output_dir.write_text("not a directory", encoding="utf-8")

    with pytest.raises(OutputError) as captured:
        plan_long_audio_output_paths(tmp_path / "lecture.mp3", output_dir)

    assert captured.value.code == "OUTPUT_PATH_INVALID"


@pytest.mark.parametrize("bad_value", ["audio.mp3", b"audio.mp3", object(), None])
def test_plan_requires_path_inputs(tmp_path: Path, bad_value: object) -> None:
    with pytest.raises(OutputError) as captured:
        plan_long_audio_output_paths(bad_value, tmp_path)  # type: ignore[arg-type]

    assert captured.value.code == "OUTPUT_PATH_INVALID"

    with pytest.raises(OutputError) as captured:
        plan_long_audio_output_paths(tmp_path / "audio.mp3", bad_value)  # type: ignore[arg-type]

    assert captured.value.code == "OUTPUT_PATH_INVALID"


@pytest.mark.skipif(os.name != "nt", reason="Windows legacy path boundary")
def test_plan_rejects_a_windows_path_beyond_the_legacy_limit(tmp_path: Path) -> None:
    output_dir = tmp_path / ("a" * 150) / ("b" * 80)

    with pytest.raises(OutputError) as captured:
        plan_long_audio_output_paths(tmp_path / "lecture.mp3", output_dir)

    assert captured.value.code == "OUTPUT_PATH_INVALID"
    assert not output_dir.exists()
