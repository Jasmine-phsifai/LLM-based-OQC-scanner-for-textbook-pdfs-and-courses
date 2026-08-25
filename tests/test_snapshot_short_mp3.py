from __future__ import annotations

import hashlib
import importlib
import os
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from ocrllm.errors import ConfigError, InvalidSource, OutputError, UnsupportedFormat
from install_close_failing_stream import install_close_failing_stream


snapshot_module = importlib.import_module("ocrllm.audio.snapshot_short_mp3")
generic_snapshot_module = importlib.import_module("ocrllm.audio.snapshot_mp3")
FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "audio"
    / "a1"
    / "mp3"
    / "valid_cbr.mp3"
)


def _install_stream_close_failure(
    monkeypatch,
    *,
    source: Path,
    stream_kind: str,
    close_error: BaseException,
    write_error: BaseException | None = None,
) -> None:
    def matches(path: Path, mode: str) -> bool:
        return (
            stream_kind == "source" and path == source and mode == "rb"
        ) or (
            stream_kind == "destination"
            and path.name == "source.mp3"
            and mode == "xb"
        )

    install_close_failing_stream(
        monkeypatch,
        matches=matches,
        close_error=close_error,
        write_error=write_error,
    )


def _primary_error(primary_kind: str) -> BaseException:
    if primary_kind == "typed":
        return OutputError("primary output failure", code="OUTPUT_WRITE_FAILED")
    if primary_kind == "ordinary":
        return RuntimeError("primary ordinary failure")
    if primary_kind == "keyboard_interrupt":
        return KeyboardInterrupt("primary keyboard interrupt")
    if primary_kind == "system_exit":
        return SystemExit("primary system exit")
    raise AssertionError(f"unknown primary kind: {primary_kind}")


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
        assert snapshot.sha256 == hashlib.sha256(original_bytes).hexdigest()
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
        assert snapshot.sha256 == hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
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
        generic_snapshot_module,
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

    monkeypatch.setattr(generic_snapshot_module.os, "fstat", report_smaller_opened_source)

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

        def close(self) -> None:
            self.wrapped.close()

    def wrap_source_open(path, *args, **kwargs):
        opened = original_open(path, *args, **kwargs)
        return FailingReader(opened) if path == source else opened

    monkeypatch.setattr(Path, "open", wrap_source_open)
    monkeypatch.setattr(generic_snapshot_module, "COPY_CHUNK_BYTES", 2)

    with pytest.raises(InvalidSource) as caught:
        with snapshot_module.snapshot_short_mp3(source, temp_dir=tmp_path / "temp"):
            raise AssertionError("unreachable")

    assert caught.value.code == "SOURCE_UNREADABLE"
    assert secret not in repr(caught.value)
    assert list((tmp_path / "temp").glob("ocrllm-audio-*")) == []


def test_snapshot_short_mp3_closes_source_before_probe_and_yield(
    tmp_path,
    monkeypatch,
) -> None:
    source = tmp_path / "valid.mp3"
    source.write_bytes(b"bytes")
    original_open = Path.open
    source_closed = False

    class ObservedReader:
        def __init__(self, wrapped) -> None:
            self.wrapped = wrapped

        def fileno(self):
            return self.wrapped.fileno()

        def read(self, size):
            return self.wrapped.read(size)

        def close(self) -> None:
            nonlocal source_closed
            self.wrapped.close()
            source_closed = True

    def observe_source_open(path, *args, **kwargs):
        opened = original_open(path, *args, **kwargs)
        return ObservedReader(opened) if path == source else opened

    def assert_source_closed_before_probe(_snapshot_path: Path) -> float:
        assert source_closed is True
        return 0.25

    monkeypatch.setattr(Path, "open", observe_source_open)
    monkeypatch.setattr(
        snapshot_module,
        "probe_short_mp3",
        assert_source_closed_before_probe,
    )

    with snapshot_module.snapshot_short_mp3(
        source,
        temp_dir=tmp_path / "temp",
    ):
        assert source_closed is True


def test_snapshot_short_mp3_rejects_short_snapshot_write(
    tmp_path,
    monkeypatch,
) -> None:
    source = tmp_path / "valid.mp3"
    source.write_bytes(b"bytes")
    original_open = Path.open

    class ShortWriter:
        def __init__(self, wrapped) -> None:
            self.wrapped = wrapped

        def write(self, data):
            return self.wrapped.write(data[:-1])

        def close(self) -> None:
            self.wrapped.close()

    def short_write_snapshot(path, *args, **kwargs):
        opened = original_open(path, *args, **kwargs)
        return ShortWriter(opened) if path.name == "source.mp3" else opened

    monkeypatch.setattr(Path, "open", short_write_snapshot)

    with pytest.raises(OutputError) as caught:
        with snapshot_module.snapshot_short_mp3(source, temp_dir=tmp_path / "temp"):
            raise AssertionError("unreachable")

    assert caught.value.code == "OUTPUT_WRITE_FAILED"
    assert list((tmp_path / "temp").glob("ocrllm-audio-*")) == []


@pytest.mark.parametrize(
    ("stream_kind", "expected_error", "expected_code"),
    [
        ("source", InvalidSource, "SOURCE_UNREADABLE"),
        ("destination", OutputError, "OUTPUT_WRITE_FAILED"),
    ],
)
def test_snapshot_short_mp3_types_close_only_stream_failure(
    tmp_path,
    monkeypatch,
    stream_kind,
    expected_error,
    expected_code,
) -> None:
    secret = f"{stream_kind}-close-secret-4328"
    source = tmp_path / "valid.mp3"
    source.write_bytes(b"bytes")
    _install_stream_close_failure(
        monkeypatch,
        source=source,
        stream_kind=stream_kind,
        close_error=OSError(secret),
    )
    monkeypatch.setattr(
        snapshot_module,
        "probe_short_mp3",
        lambda _path: (_ for _ in ()).throw(
            AssertionError("probe must not run after a stream-close failure")
        ),
    )

    with pytest.raises(expected_error) as caught:
        with snapshot_module.snapshot_short_mp3(source, temp_dir=tmp_path / "temp"):
            raise AssertionError("unreachable")

    assert caught.value.code == expected_code
    assert secret not in str(caught.value)
    assert secret not in repr(caught.value)
    assert secret not in repr(caught.value.details)
    assert list((tmp_path / "temp").glob("ocrllm-audio-*")) == []


@pytest.mark.parametrize("stream_kind", ["source", "destination"])
@pytest.mark.parametrize(
    "primary_kind",
    ["typed", "ordinary", "keyboard_interrupt", "system_exit"],
)
def test_snapshot_short_mp3_preserves_primary_when_stream_close_fails(
    tmp_path,
    monkeypatch,
    stream_kind,
    primary_kind,
) -> None:
    secret = f"{stream_kind}-close-secret-8731"
    source = tmp_path / "valid.mp3"
    source.write_bytes(b"bytes")
    primary = _primary_error(primary_kind)
    write_error = primary if stream_kind == "destination" else None
    _install_stream_close_failure(
        monkeypatch,
        source=source,
        stream_kind=stream_kind,
        close_error=OSError(secret),
        write_error=write_error,
    )
    if stream_kind == "source":

        def fail_copy(*_args, **_kwargs):
            raise primary

        monkeypatch.setattr(
            generic_snapshot_module,
            "_copy_and_hash_open_source",
            fail_copy,
        )
    monkeypatch.setattr(
        snapshot_module,
        "probe_short_mp3",
        lambda _path: (_ for _ in ()).throw(
            AssertionError("probe must not run after a copy failure")
        ),
    )

    with pytest.raises(type(primary)) as caught:
        with snapshot_module.snapshot_short_mp3(source, temp_dir=tmp_path / "temp"):
            raise AssertionError("unreachable")

    assert caught.value is primary
    assert secret not in str(caught.value)
    assert secret not in repr(caught.value)
    if isinstance(primary, OutputError):
        detail_name = (
            "source_stream_cleanup_failed"
            if stream_kind == "source"
            else "snapshot_stream_cleanup_failed"
        )
        assert primary.details[detail_name] is True
    assert list((tmp_path / "temp").glob("ocrllm-audio-*")) == []


@pytest.mark.parametrize("stream_kind", ["source", "destination"])
@pytest.mark.parametrize("control_type", [KeyboardInterrupt, SystemExit])
def test_snapshot_short_mp3_propagates_process_control_from_stream_close(
    tmp_path,
    monkeypatch,
    stream_kind,
    control_type,
) -> None:
    source = tmp_path / "valid.mp3"
    source.write_bytes(b"bytes")
    control = control_type(f"{stream_kind} close process control")
    _install_stream_close_failure(
        monkeypatch,
        source=source,
        stream_kind=stream_kind,
        close_error=control,
    )
    monkeypatch.setattr(
        snapshot_module,
        "probe_short_mp3",
        lambda _path: (_ for _ in ()).throw(
            AssertionError("probe must not run after process control")
        ),
    )

    with pytest.raises(control_type) as caught:
        with snapshot_module.snapshot_short_mp3(source, temp_dir=tmp_path / "temp"):
            raise AssertionError("unreachable")

    assert caught.value is control
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
            generic_snapshot_module.os,
            "fsync",
            lambda _descriptor: (_ for _ in ()).throw(OSError(secret)),
        )

    with pytest.raises(OutputError) as caught:
        with snapshot_module.snapshot_short_mp3(source, temp_dir=tmp_path / "temp"):
            raise AssertionError("unreachable")

    assert caught.value.code == "OUTPUT_WRITE_FAILED"
    assert secret not in repr(caught.value)
    assert list((tmp_path / "temp").glob("ocrllm-audio-*")) == []


def test_snapshot_cleanup_failure_is_typed_despite_ambient_exception(
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

    monkeypatch.setattr(generic_snapshot_module.shutil, "rmtree", fail_normal_cleanup)

    try:
        raise RuntimeError("ambient caller exception")
    except RuntimeError:
        with pytest.raises(OutputError) as caught:
            with snapshot_module.snapshot_short_mp3(
                source,
                temp_dir=tmp_path / "temp",
            ):
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

    monkeypatch.setattr(generic_snapshot_module.shutil, "rmtree", fail_normal_cleanup)

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
