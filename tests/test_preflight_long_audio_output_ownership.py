"""Preflight new and resumed long-audio output ownership."""

from __future__ import annotations

from pathlib import Path

import pytest

from ocrllm.audio.long_audio_output_paths import LongAudioOutputPaths
from ocrllm.audio.plan_long_audio_output_paths import plan_long_audio_output_paths
from ocrllm.audio.preflight_long_audio_output_ownership import (
    preflight_long_audio_output_ownership,
)
from ocrllm.errors import ConfigError, OutputError, OutputExists, ResumeStateError


class _PathPlanSubclass(LongAudioOutputPaths):
    pass


def _paths(tmp_path: Path) -> LongAudioOutputPaths:
    return plan_long_audio_output_paths(tmp_path / "lecture.mp3", tmp_path / "out")


def test_new_run_accepts_an_unclaimed_root_without_creating_it(tmp_path: Path) -> None:
    paths = _paths(tmp_path)

    preflight_long_audio_output_ownership(paths, resume=False)

    assert not paths.root.exists()


@pytest.mark.parametrize("existing_kind", ["directory", "file"])
def test_new_run_rejects_any_existing_job_root(
    tmp_path: Path,
    existing_kind: str,
) -> None:
    paths = _paths(tmp_path)
    paths.root.parent.mkdir()
    if existing_kind == "directory":
        paths.root.mkdir()
    else:
        paths.root.write_text("occupied", encoding="utf-8")

    with pytest.raises(OutputExists) as captured:
        preflight_long_audio_output_ownership(paths, resume=False)

    assert captured.value.code == "OUTPUT_EXISTS"


def test_resume_requires_the_owned_job_directory(tmp_path: Path) -> None:
    paths = _paths(tmp_path)

    with pytest.raises(ResumeStateError) as captured:
        preflight_long_audio_output_ownership(paths, resume=True)

    assert captured.value.code == "RESUME_STATE_INVALID"


def test_resume_rejects_a_nondirectory_job_root(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    paths.root.parent.mkdir()
    paths.root.write_text("not a directory", encoding="utf-8")

    with pytest.raises(ResumeStateError) as captured:
        preflight_long_audio_output_ownership(paths, resume=True)

    assert captured.value.code == "RESUME_STATE_INVALID"


def test_resume_requires_the_fixed_regular_state_file(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    paths.root.mkdir(parents=True)

    with pytest.raises(ResumeStateError) as captured:
        preflight_long_audio_output_ownership(paths, resume=True)
    assert captured.value.code == "RESUME_STATE_INVALID"

    paths.resume_state.mkdir()
    with pytest.raises(ResumeStateError) as captured:
        preflight_long_audio_output_ownership(paths, resume=True)
    assert captured.value.code == "RESUME_STATE_INVALID"


def test_resume_accepts_state_and_ignores_unrelated_files(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    paths.root.mkdir(parents=True)
    paths.resume_state.write_bytes(b"state is parsed by the next boundary")
    (paths.root / "interrupted-note.txt").write_text("unowned", encoding="utf-8")

    preflight_long_audio_output_ownership(paths, resume=True)

    assert paths.resume_state.read_bytes().startswith(b"state")


def test_resume_rejects_an_already_published_result(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    paths.root.mkdir(parents=True)
    paths.resume_state.write_bytes(b"state")
    paths.result.write_text("# complete", encoding="utf-8")

    with pytest.raises(OutputExists) as captured:
        preflight_long_audio_output_ownership(paths, resume=True)

    assert captured.value.code == "OUTPUT_EXISTS"


def test_preflight_rejects_a_forged_path_plan(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    forged = LongAudioOutputPaths(
        root=paths.root,
        result=tmp_path / "elsewhere.md",
        resume_state=paths.resume_state,
    )

    with pytest.raises(OutputError) as captured:
        preflight_long_audio_output_ownership(forged, resume=False)

    assert captured.value.code == "OUTPUT_PATH_INVALID"


def test_preflight_rejects_a_path_plan_subclass(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    subclass = _PathPlanSubclass(
        root=paths.root,
        result=paths.result,
        resume_state=paths.resume_state,
    )

    with pytest.raises(OutputError) as captured:
        preflight_long_audio_output_ownership(subclass, resume=False)

    assert captured.value.code == "OUTPUT_PATH_INVALID"


@pytest.mark.parametrize("bad_paths", [None, object(), ("root", "result", "state")])
def test_preflight_requires_the_exact_path_plan(bad_paths: object) -> None:
    with pytest.raises(OutputError) as captured:
        preflight_long_audio_output_ownership(bad_paths, resume=False)  # type: ignore[arg-type]

    assert captured.value.code == "OUTPUT_PATH_INVALID"


@pytest.mark.parametrize("bad_resume", [0, 1, None, "yes"])
def test_preflight_requires_an_exact_boolean_mode(
    tmp_path: Path,
    bad_resume: object,
) -> None:
    with pytest.raises(ConfigError) as captured:
        preflight_long_audio_output_ownership(
            _paths(tmp_path),
            resume=bad_resume,  # type: ignore[arg-type]
        )

    assert captured.value.code == "CONFIG_INVALID"
