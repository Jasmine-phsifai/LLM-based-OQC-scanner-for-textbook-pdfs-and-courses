"""Prove image snapshot stream and directory cleanup precedence."""

from __future__ import annotations

import importlib
import shutil
from pathlib import Path

import pytest

from ocrllm import Config, OutputError
from install_close_failing_stream import install_close_failing_stream
from write_test_image import write_test_image


snapshot_module = importlib.import_module("ocrllm.imaging.snapshot_image_group")


def _matches_stream(source: Path, stream_kind: str, temp_dir: Path):
    def matches(path: Path, mode: str) -> bool:
        if stream_kind == "source":
            return (
                path == source
                and mode == "rb"
                and any(temp_dir.glob("ocrllm-images-*"))
            )
        return (
            mode == "xb"
            and path.name == source.name
            and path.parent.parent.name.startswith("ocrllm-images-")
        )

    return matches


def _primary_error(primary_kind: str) -> BaseException:
    if primary_kind == "typed":
        return OutputError("primary image failure", code="OUTPUT_WRITE_FAILED")
    if primary_kind == "ordinary":
        return RuntimeError("primary ordinary failure")
    if primary_kind == "system_exit":
        return SystemExit("primary system exit")
    raise AssertionError(f"unknown primary kind: {primary_kind}")


@pytest.mark.parametrize(
    ("stream_kind", "primary_kind"),
    [
        ("source", "typed"),
        ("destination", "typed"),
        ("source", "ordinary"),
        ("destination", "system_exit"),
    ],
)
def test_snapshot_image_group_preserves_primary_when_stream_close_fails(
    tmp_path,
    monkeypatch,
    stream_kind,
    primary_kind,
) -> None:
    source = write_test_image(tmp_path / "board.png")
    temp_dir = tmp_path / "snapshots"
    primary = _primary_error(primary_kind)
    install_close_failing_stream(
        monkeypatch,
        matches=_matches_stream(source, stream_kind, temp_dir),
        close_error=OSError(f"{stream_kind}-close-secret-9175"),
        read_error=primary if stream_kind == "source" else None,
        write_error=primary if stream_kind == "destination" else None,
    )
    monkeypatch.setattr(
        snapshot_module,
        "validate_image_group",
        lambda _paths: (_ for _ in ()).throw(
            AssertionError("validation must not run after a copy failure")
        ),
    )

    with pytest.raises(type(primary)) as caught:
        with snapshot_module.snapshot_image_group(
            (source,),
            config=Config(temp_dir=temp_dir),
        ):
            raise AssertionError("unreachable")

    assert caught.value is primary
    if isinstance(primary, OutputError):
        detail_name = (
            "source_stream_cleanup_failed"
            if stream_kind == "source"
            else "snapshot_stream_cleanup_failed"
        )
        assert primary.details[detail_name] is True
    assert list(temp_dir.glob("ocrllm-images-*")) == []


@pytest.mark.parametrize(
    ("stream_kind", "control_type"),
    [("source", SystemExit), ("destination", KeyboardInterrupt)],
)
def test_snapshot_image_group_propagates_process_control_from_stream_close(
    tmp_path,
    monkeypatch,
    stream_kind,
    control_type,
) -> None:
    source = write_test_image(tmp_path / "board.png")
    temp_dir = tmp_path / "snapshots"
    control = control_type(f"{stream_kind} close process control")
    install_close_failing_stream(
        monkeypatch,
        matches=_matches_stream(source, stream_kind, temp_dir),
        close_error=control,
    )
    monkeypatch.setattr(
        snapshot_module,
        "validate_image_group",
        lambda _paths: (_ for _ in ()).throw(
            AssertionError("validation must not run after process control")
        ),
    )

    with pytest.raises(control_type) as caught:
        with snapshot_module.snapshot_image_group(
            (source,),
            config=Config(temp_dir=temp_dir),
        ):
            raise AssertionError("unreachable")

    assert caught.value is control
    assert list(temp_dir.glob("ocrllm-images-*")) == []


def test_snapshot_cleanup_failure_is_typed_despite_ambient_exception(
    tmp_path,
    monkeypatch,
) -> None:
    source = write_test_image(tmp_path / "board.png")
    temp_dir = tmp_path / "snapshots"
    real_rmtree = shutil.rmtree

    def fail_normal_cleanup(path, *args, **kwargs):
        if not kwargs.get("ignore_errors", False):
            raise PermissionError("cleanup-secret")
        return real_rmtree(path, *args, **kwargs)

    monkeypatch.setattr(snapshot_module.shutil, "rmtree", fail_normal_cleanup)

    try:
        raise RuntimeError("ambient caller exception")
    except RuntimeError:
        with pytest.raises(OutputError) as caught:
            with snapshot_module.snapshot_image_group(
                (source,),
                config=Config(temp_dir=temp_dir),
            ):
                pass

    assert caught.value.code == "OUTPUT_WRITE_FAILED"
    retained = list(temp_dir.glob("ocrllm-images-*"))
    assert len(retained) == 1
    real_rmtree(retained[0])
