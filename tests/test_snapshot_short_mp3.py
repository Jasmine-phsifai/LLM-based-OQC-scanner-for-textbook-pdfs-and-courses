from __future__ import annotations

import importlib
import os
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from ocrllm.errors import ConfigError, InvalidSource, OutputError, UnsupportedFormat


snapshot_module = importlib.import_module("ocrllm.audio.snapshot_short_mp3")
FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "audio"
    / "a1"
    / "mp3"
    / "valid_cbr.mp3"
)


def test_snapshot_short_mp3_owns_compact_validated_bytes_and_cleans_up(
    tmp_path,
    monkeypatch,
) -> None:
    source = tmp_path / ("caller-secret-name-" + "x" * 80 + ".MP3")
    original_bytes = FIXTURE.read_bytes()
    source.write_bytes(original_bytes)
    observed_snapshot_bytes: list[bytes] = []

    def inspect_owned_snapshot(snapshot_path: Path) -> float:
        source.write_bytes(b"caller replaced the source")
        observed_snapshot_bytes.append(snapshot_path.read_bytes())
        return 0.5

    monkeypatch.setattr(snapshot_module, "probe_short_mp3", inspect_owned_snapshot)
    temp_dir = tmp_path / "snapshots"

    with snapshot_module.snapshot_short_mp3(
        source,
        temp_dir=temp_dir,
    ) as snapshot:
        snapshot_root = snapshot.path.parent
        assert snapshot.path.name == "source.mp3"
        assert source.name not in str(snapshot.path)
        assert snapshot.path.read_bytes() == original_bytes
        assert snapshot.byte_size == len(original_bytes)
        assert snapshot.duration_seconds == 0.5

    assert observed_snapshot_bytes == [original_bytes]
    assert not snapshot_root.exists()
    assert temp_dir.is_dir()


def test_snapshot_short_mp3_runs_real_probe_on_committed_fixture(tmp_path) -> None:
    pytest.importorskip("miniaudio")

    with snapshot_module.snapshot_short_mp3(
        FIXTURE,
        temp_dir=tmp_path,
    ) as snapshot:
        assert snapshot.byte_size == FIXTURE.stat().st_size
        assert snapshot.duration_seconds == 0.5


def test_snapshot_short_mp3_rejects_wrong_suffix_before_temp_access(
    tmp_path,
    monkeypatch,
) -> None:
    source = tmp_path / "audio.wav"
    source.write_bytes(b"not inspected")

    def fail_on_temp_access(_temp_dir):
        raise AssertionError("unsupported formats must fail before temp access")

    monkeypatch.setattr(
        snapshot_module,
        "_prepare_temporary_parent",
        fail_on_temp_access,
    )

    with pytest.raises(UnsupportedFormat) as caught:
        with snapshot_module.snapshot_short_mp3(source, temp_dir=tmp_path):
            raise AssertionError("unreachable")

    assert caught.value.code == "UNSUPPORTED_FORMAT"
    assert caught.value.details == {"extension": ".wav"}


@pytest.mark.parametrize(
    ("source_kind", "expected_code"),
    [
        ("missing", "SOURCE_NOT_FOUND"),
        ("directory", "SOURCE_INVALID"),
        ("empty", "SOURCE_INVALID"),
    ],
)
def test_snapshot_short_mp3_rejects_invalid_source_state(
    tmp_path,
    source_kind,
    expected_code,
) -> None:
    source = tmp_path / f"{source_kind}.mp3"
    if source_kind == "directory":
        source.mkdir()
    elif source_kind == "empty":
        source.write_bytes(b"")

    with pytest.raises(InvalidSource) as caught:
        with snapshot_module.snapshot_short_mp3(source, temp_dir=tmp_path / "temp"):
            raise AssertionError("unreachable")

    assert caught.value.code == expected_code
    assert not (tmp_path / "temp").exists()


def test_snapshot_short_mp3_rejects_initial_local_safety_limit(
    tmp_path,
    monkeypatch,
) -> None:
    source = tmp_path / "large.mp3"
    source.write_bytes(b"four")
    monkeypatch.setattr(snapshot_module, "MAX_SHORT_MP3_SOURCE_BYTES", 3)

    with pytest.raises(InvalidSource) as caught:
        with snapshot_module.snapshot_short_mp3(source, temp_dir=tmp_path / "temp"):
            raise AssertionError("unreachable")

    assert caught.value.code == "SOURCE_TOO_LARGE"
    assert caught.value.details == {"byte_size": 4, "maximum_byte_size": 3}
    assert not (tmp_path / "temp").exists()


def test_snapshot_short_mp3_rejects_source_growth_during_copy(
    tmp_path,
    monkeypatch,
) -> None:
    source = tmp_path / "growing.mp3"
    source.write_bytes(b"four")
    real_fstat = os.fstat

    def report_smaller_opened_source(file_descriptor):
        result = real_fstat(file_descriptor)
        return SimpleNamespace(st_mode=result.st_mode, st_size=result.st_size - 1)

    monkeypatch.setattr(snapshot_module.os, "fstat", report_smaller_opened_source)

    with pytest.raises(InvalidSource, match="changed while") as caught:
        with snapshot_module.snapshot_short_mp3(source, temp_dir=tmp_path / "temp"):
            raise AssertionError("unreachable")

    assert caught.value.code == "SOURCE_INVALID"
    assert list((tmp_path / "temp").glob("ocrllm-audio-*")) == []


def test_snapshot_short_mp3_redacts_source_read_failure(
    tmp_path,
    monkeypatch,
) -> None:
    secret = "source-path-secret-8173"
    source = tmp_path / f"{secret}.mp3"
    source.write_bytes(b"bytes")
    original_open = Path.open

    def deny_source_open(path, *args, **kwargs):
        if path == source:
            raise PermissionError(secret)
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", deny_source_open)

    with pytest.raises(InvalidSource) as caught:
        with snapshot_module.snapshot_short_mp3(source, temp_dir=tmp_path / "temp"):
            raise AssertionError("unreachable")

    assert caught.value.code == "SOURCE_UNREADABLE"
    assert secret not in str(caught.value)
    assert secret not in repr(caught.value)
    assert secret not in repr(caught.value.details)
    assert not (tmp_path / "temp").exists()


def test_snapshot_short_mp3_cleans_partial_copy_after_midstream_read_failure(
    tmp_path,
    monkeypatch,
) -> None:
    secret = "midstream-read-secret-4418"
    source = tmp_path / "valid.mp3"
    source.write_bytes(b"four")
    original_open = Path.open

    class FailingReader:
        def __init__(self, wrapped) -> None:
            self.wrapped = wrapped
            self.read_count = 0

        def fileno(self):
            return self.wrapped.fileno()

        def read(self, size):
            self.read_count += 1
            if self.read_count == 2:
                raise OSError(secret)
            return self.wrapped.read(size)

        def __enter__(self):
            return self

        def __exit__(self, error_type, error, traceback):
            return self.wrapped.__exit__(error_type, error, traceback)

    def wrap_source_open(path, *args, **kwargs):
        opened = original_open(path, *args, **kwargs)
        return FailingReader(opened) if path == source else opened

    monkeypatch.setattr(Path, "open", wrap_source_open)
    monkeypatch.setattr(snapshot_module, "COPY_CHUNK_BYTES", 2)

    with pytest.raises(InvalidSource) as caught:
        with snapshot_module.snapshot_short_mp3(source, temp_dir=tmp_path / "temp"):
            raise AssertionError("unreachable")

    assert caught.value.code == "SOURCE_UNREADABLE"
    assert secret not in repr(caught.value)
    assert list((tmp_path / "temp").glob("ocrllm-audio-*")) == []


def test_snapshot_short_mp3_rejects_non_directory_temp_parent(tmp_path) -> None:
    source = tmp_path / "valid.mp3"
    source.write_bytes(b"bytes")
    temp_parent = tmp_path / "not-a-directory"
    temp_parent.write_bytes(b"occupied")

    with pytest.raises(ConfigError) as caught:
        with snapshot_module.snapshot_short_mp3(source, temp_dir=temp_parent):
            raise AssertionError("unreachable")

    assert caught.value.code == "CONFIG_INVALID"


@pytest.mark.parametrize("failure_phase", ["create", "fsync"])
def test_snapshot_short_mp3_maps_owned_snapshot_write_failures(
    tmp_path,
    monkeypatch,
    failure_phase,
) -> None:
    secret = "owned-write-secret-2194"
    source = tmp_path / "valid.mp3"
    source.write_bytes(b"bytes")
    original_open = Path.open

    def fail_snapshot_create(path, *args, **kwargs):
        if failure_phase == "create" and path.name == "source.mp3":
            raise PermissionError(secret)
        return original_open(path, *args, **kwargs)

    if failure_phase == "create":
        monkeypatch.setattr(Path, "open", fail_snapshot_create)
    else:
        monkeypatch.setattr(
            snapshot_module.os,
            "fsync",
            lambda _descriptor: (_ for _ in ()).throw(OSError(secret)),
        )

    with pytest.raises(OutputError) as caught:
        with snapshot_module.snapshot_short_mp3(source, temp_dir=tmp_path / "temp"):
            raise AssertionError("unreachable")

    assert caught.value.code == "OUTPUT_WRITE_FAILED"
    assert secret not in repr(caught.value)
    assert list((tmp_path / "temp").glob("ocrllm-audio-*")) == []


def test_snapshot_cleanup_failure_is_typed_after_success(
    tmp_path,
    monkeypatch,
) -> None:
    source = tmp_path / "valid.mp3"
    source.write_bytes(b"bytes")
    monkeypatch.setattr(snapshot_module, "probe_short_mp3", lambda _path: 0.25)
    real_rmtree = shutil.rmtree

    def fail_normal_cleanup(path, *args, **kwargs):
        if not kwargs.get("ignore_errors", False):
            raise PermissionError("cleanup-secret")
        return real_rmtree(path, *args, **kwargs)

    monkeypatch.setattr(snapshot_module.shutil, "rmtree", fail_normal_cleanup)

    with pytest.raises(OutputError) as caught:
        with snapshot_module.snapshot_short_mp3(source, temp_dir=tmp_path / "temp"):
            pass

    assert caught.value.code == "OUTPUT_WRITE_FAILED"
    retained = list((tmp_path / "temp").glob("ocrllm-audio-*"))
    assert len(retained) == 1
    real_rmtree(retained[0])


def test_snapshot_cleanup_failure_preserves_typed_primary_error(
    tmp_path,
    monkeypatch,
) -> None:
    source = tmp_path / "valid.mp3"
    source.write_bytes(b"bytes")
    primary = InvalidSource("primary", code="SOURCE_INVALID")

    def fail_probe(_path):
        raise primary

    monkeypatch.setattr(snapshot_module, "probe_short_mp3", fail_probe)
    real_rmtree = shutil.rmtree

    def fail_normal_cleanup(path, *args, **kwargs):
        if not kwargs.get("ignore_errors", False):
            raise PermissionError("cleanup-secret")
        return real_rmtree(path, *args, **kwargs)

    monkeypatch.setattr(snapshot_module.shutil, "rmtree", fail_normal_cleanup)

    with pytest.raises(InvalidSource) as caught:
        with snapshot_module.snapshot_short_mp3(source, temp_dir=tmp_path / "temp"):
            raise AssertionError("unreachable")

    assert caught.value is primary
    assert caught.value.details["snapshot_cleanup_failed"] is True
    retained = list((tmp_path / "temp").glob("ocrllm-audio-*"))
    assert len(retained) == 1
    real_rmtree(retained[0])


def _windows_path_units(path: Path) -> int:
    return len(str(path).encode("utf-16-le")) // 2


def _make_directory_with_windows_path_units(base: Path, target_units: int) -> Path:
    current = base
    while _windows_path_units(current) < target_units:
        remaining = target_units - _windows_path_units(current) - 1
        if remaining < 1:
            raise AssertionError("target units cannot be reached")
        current /= "d" * min(40, remaining)
    assert _windows_path_units(current) == target_units
    current.mkdir(parents=True)
    return current


@pytest.mark.skipif(os.name != "nt", reason="Windows legacy path-limit regression")
def test_snapshot_short_mp3_does_not_repeat_long_source_name(
    tmp_path,
    monkeypatch,
) -> None:
    if _windows_path_units(tmp_path) >= 135:
        pytest.skip("pytest temporary root is too long for controlled path construction")
    source_parent = _make_directory_with_windows_path_units(tmp_path, 145)
    source = source_parent / ("s" * 96 + ".mp3")
    source.write_bytes(b"bytes")
    temp_parent = _make_directory_with_windows_path_units(tmp_path / "temp", 220)
    original_open = Path.open

    def open_with_legacy_limit(path, *args, **kwargs):
        if _windows_path_units(path) > 259:
            raise OSError(206, "test-only path limit", str(path))
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", open_with_legacy_limit)
    monkeypatch.setattr(snapshot_module, "probe_short_mp3", lambda _path: 0.25)

    with snapshot_module.snapshot_short_mp3(
        source,
        temp_dir=temp_parent,
    ) as snapshot:
        assert snapshot.path.name == "source.mp3"
        assert _windows_path_units(snapshot.path) <= 259
        assert _windows_path_units(snapshot.path.parent / source.name) > 259
        assert "s" * 96 not in str(snapshot.path)
