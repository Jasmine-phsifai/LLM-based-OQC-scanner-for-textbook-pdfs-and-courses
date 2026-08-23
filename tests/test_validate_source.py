from __future__ import annotations

import builtins
import importlib
import warnings
from pathlib import Path

import pytest

from ocrllm.errors import DependencyMissing, InvalidSource, UnsupportedFormat
from ocrllm.imaging.decode_image import _read_image_bytes_bounded, decode_image
from ocrllm.imaging.decode_image_bytes import MAX_IMAGE_PIXELS
from ocrllm.imaging.decoded_image_info import DecodedImageInfo
from ocrllm.validate_image_group import (
    MAX_AGGREGATE_PIXELS,
    MAX_AGGREGATE_SOURCE_BYTES,
    MAX_IMAGE_GROUP_COUNT,
)
from ocrllm.validate_source import MAX_SOURCE_BYTES, validate_source
from install_close_failing_stream import install_close_failing_stream
from write_test_image import write_test_image


@pytest.mark.parametrize(
    ("suffix", "expected_format"),
    [(".png", "PNG"), (".jpg", "JPEG"), (".jpeg", "JPEG")],
)
def test_validate_and_decode_valid_phase_zero_images(tmp_path, suffix, expected_format):
    source = write_test_image(tmp_path / f"valid{suffix}")

    assert validate_source(source) == source.stat().st_size
    decoded = decode_image(source)

    assert decoded == DecodedImageInfo(format=expected_format, width=8, height=6)


def test_validate_source_reports_a_missing_file_before_decode(tmp_path):
    with pytest.raises(InvalidSource) as raised:
        validate_source(tmp_path / "missing.png")

    assert raised.value.code == "SOURCE_NOT_FOUND"


def test_validate_source_rejects_a_directory(tmp_path):
    source = tmp_path / "directory.png"
    source.mkdir()

    with pytest.raises(InvalidSource) as raised:
        validate_source(source)

    assert raised.value.code == "SOURCE_INVALID"


def test_validate_source_rejects_an_empty_file(tmp_path):
    source = tmp_path / "empty.png"
    source.touch()

    with pytest.raises(InvalidSource) as raised:
        validate_source(source)

    assert raised.value.code == "SOURCE_INVALID"


def test_validate_source_maps_open_failures_to_unreadable(tmp_path, monkeypatch):
    source = write_test_image(tmp_path / "unreadable.png")
    original_open = Path.open

    def deny_open(path, *args, **kwargs):
        if path == source:
            raise PermissionError("test-only denial")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", deny_open)

    with pytest.raises(InvalidSource) as raised:
        validate_source(source)

    assert raised.value.code == "SOURCE_UNREADABLE"


@pytest.mark.parametrize("primary_kind", ["typed", "ordinary", "keyboard_interrupt"])
def test_validate_source_preserves_read_failure_when_close_also_fails(
    tmp_path,
    monkeypatch,
    primary_kind,
) -> None:
    source = write_test_image(tmp_path / "read-close-failure.png")
    if primary_kind == "typed":
        primary = InvalidSource("primary source failure", code="SOURCE_INVALID")
    elif primary_kind == "ordinary":
        primary = RuntimeError("primary ordinary failure")
    else:
        primary = KeyboardInterrupt("primary process control")
    install_close_failing_stream(
        monkeypatch,
        matches=lambda path, mode: path == source and mode == "rb",
        read_error=primary,
        close_error=OSError("validation-close-secret-4158"),
    )

    with pytest.raises(type(primary)) as caught:
        validate_source(source)

    assert caught.value is primary
    if isinstance(primary, InvalidSource):
        assert primary.details["source_stream_cleanup_failed"] is True


def test_validate_source_propagates_process_control_from_close(
    tmp_path,
    monkeypatch,
) -> None:
    source = write_test_image(tmp_path / "close-process-control.png")
    control = SystemExit("validation close process control")
    install_close_failing_stream(
        monkeypatch,
        matches=lambda path, mode: path == source and mode == "rb",
        close_error=control,
    )

    with pytest.raises(SystemExit) as caught:
        validate_source(source)

    assert caught.value is control


@pytest.mark.parametrize(
    ("limit_offset", "accepted"),
    [(-1, True), (0, True), (1, False)],
    ids=["one-below", "at", "one-above"],
)
def test_validate_source_byte_limit_boundary(tmp_path, limit_offset, accepted):
    source_size = MAX_SOURCE_BYTES + limit_offset
    source = tmp_path / f"byte-limit-{limit_offset}.png"
    with source.open("wb") as source_file:
        source_file.write(b"x")
        source_file.truncate(source_size)

    if accepted:
        assert validate_source(source) == source_size
        return

    with pytest.raises(InvalidSource) as raised:
        validate_source(source)

    assert raised.value.code == "SOURCE_TOO_LARGE"
    assert raised.value.details == {
        "byte_size": source_size,
        "maximum_byte_size": MAX_SOURCE_BYTES,
    }


def test_validate_source_rejects_an_unapproved_extension(tmp_path):
    source = tmp_path / "image.webp"
    source.write_bytes(b"not inspected because the suffix is unsupported")

    with pytest.raises(UnsupportedFormat) as raised:
        validate_source(source)

    assert raised.value.code == "UNSUPPORTED_FORMAT"


def test_validate_source_maps_an_invalid_path_to_source_invalid():
    with pytest.raises(InvalidSource) as raised:
        validate_source(Path("invalid\x00path.png"))

    assert raised.value.code == "SOURCE_INVALID"


def test_decode_image_rejects_corrupt_and_truncated_data(tmp_path):
    corrupt = tmp_path / "corrupt.png"
    corrupt.write_bytes(b"not an image")
    valid = write_test_image(tmp_path / "valid.png")
    truncated = tmp_path / "truncated.png"
    truncated.write_bytes(valid.read_bytes()[:-10])

    for source in (corrupt, truncated):
        with pytest.raises(InvalidSource) as raised:
            decode_image(source)
        assert raised.value.code == "SOURCE_INVALID"


@pytest.mark.parametrize("primary_kind", ["typed", "ordinary", "keyboard_interrupt"])
def test_bounded_image_read_preserves_primary_when_close_also_fails(
    tmp_path,
    monkeypatch,
    primary_kind,
) -> None:
    source = write_test_image(tmp_path / "bounded-read-close.png")
    if primary_kind == "typed":
        primary = InvalidSource("primary decode failure", code="SOURCE_INVALID")
    elif primary_kind == "ordinary":
        primary = RuntimeError("primary ordinary decode failure")
    else:
        primary = KeyboardInterrupt("primary decode process control")
    install_close_failing_stream(
        monkeypatch,
        matches=lambda path, mode: path == source and mode == "rb",
        read_error=primary,
        close_error=OSError("decode-close-secret-2916"),
    )

    with pytest.raises(type(primary)) as caught:
        _read_image_bytes_bounded(source)

    assert caught.value is primary
    if isinstance(primary, InvalidSource):
        assert primary.details["source_stream_cleanup_failed"] is True


@pytest.mark.parametrize(
    ("close_error", "expected_code"),
    [
        (OSError("decode-close-os-secret-3827"), "SOURCE_UNREADABLE"),
        (ValueError("decode-close-value-secret-4938"), "SOURCE_INVALID"),
    ],
)
def test_bounded_image_read_maps_close_only_failure(
    tmp_path,
    monkeypatch,
    close_error,
    expected_code,
) -> None:
    source = write_test_image(tmp_path / "bounded-close-only.png")
    install_close_failing_stream(
        monkeypatch,
        matches=lambda path, mode: path == source and mode == "rb",
        close_error=close_error,
    )

    with pytest.raises(InvalidSource) as caught:
        _read_image_bytes_bounded(source)

    assert caught.value.code == expected_code
    assert str(close_error) not in str(caught.value)
    assert str(close_error) not in repr(caught.value.details)


def test_bounded_image_read_propagates_process_control_from_close(
    tmp_path,
    monkeypatch,
) -> None:
    source = write_test_image(tmp_path / "bounded-close-control.png")
    control = SystemExit("decode close process control")
    install_close_failing_stream(
        monkeypatch,
        matches=lambda path, mode: path == source and mode == "rb",
        close_error=control,
    )

    with pytest.raises(SystemExit) as caught:
        _read_image_bytes_bounded(source)

    assert caught.value is control


def test_decode_image_rejects_content_that_does_not_match_the_suffix(tmp_path):
    from PIL import Image

    source = tmp_path / "claims-jpeg.jpg"
    Image.new("RGB", (8, 6)).save(source, format="PNG")

    with pytest.raises(InvalidSource) as raised:
        decode_image(source)

    assert raised.value.code == "SOURCE_INVALID"


def test_decode_image_maps_missing_pillow_to_the_image_extra(tmp_path, monkeypatch):
    source = write_test_image(tmp_path / "valid.png")
    original_import = builtins.__import__

    def import_without_pillow(name, *args, **kwargs):
        if name == "PIL" or name.startswith("PIL."):
            raise ModuleNotFoundError("test-only missing Pillow")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", import_without_pillow)

    with pytest.raises(DependencyMissing) as raised:
        decode_image(source)

    assert raised.value.code == "DEPENDENCY_MISSING"
    assert raised.value.details["extra"] == "image"


def test_decode_image_does_not_change_pillow_global_pixel_limit(tmp_path):
    from PIL import Image

    source = write_test_image(tmp_path / "valid.png")
    original_limit = Image.MAX_IMAGE_PIXELS

    decode_image(source)

    assert Image.MAX_IMAGE_PIXELS == original_limit


@pytest.mark.parametrize(
    ("limit_offset", "accepted"),
    [(-1, True), (0, True), (1, False)],
    ids=["one-below", "at", "one-above"],
)
def test_decode_image_pixel_limit_boundary(monkeypatch, limit_offset, accepted):
    decode_module = importlib.import_module("ocrllm.imaging.decode_image_bytes")
    pixel_count = MAX_IMAGE_PIXELS + limit_offset
    fake_module = _FakeImageModule(
        size=(pixel_count, 1),
        image_format="PNG",
    )
    monkeypatch.setattr(decode_module, "_load_pillow", lambda: (fake_module, OSError))

    if accepted:
        decoded = decode_module.decode_image_bytes(b"fake image", suffix=".png")
        assert decoded.pixel_count == pixel_count
        return

    with pytest.raises(InvalidSource) as raised:
        decode_module.decode_image_bytes(b"fake image", suffix=".png")

    assert raised.value.code == "SOURCE_TOO_LARGE"
    assert raised.value.details == {
        "pixel_count": pixel_count,
        "maximum_pixel_count": MAX_IMAGE_PIXELS,
    }


def test_decode_image_maps_decompression_bomb_warning_to_too_large(tmp_path, monkeypatch):
    decode_module = importlib.import_module("ocrllm.imaging.decode_image_bytes")
    fake_module = _FakeImageModule(
        size=(1, 1),
        image_format="PNG",
        warn_about_bomb=True,
    )
    monkeypatch.setattr(decode_module, "_load_pillow", lambda: (fake_module, OSError))

    with pytest.raises(InvalidSource) as raised:
        decode_module.decode_image_bytes(b"fake image", suffix=".png")

    assert raised.value.code == "SOURCE_TOO_LARGE"


@pytest.mark.parametrize(
    ("limit_offset", "accepted"),
    [(-1, True), (0, True), (1, False)],
    ids=["one-below", "at", "one-above"],
)
def test_validate_image_group_count_boundary(monkeypatch, limit_offset, accepted):
    group_module = importlib.import_module("ocrllm.validate_image_group")
    image_count = MAX_IMAGE_GROUP_COUNT + limit_offset
    sources = tuple(Path(f"{index}.png") for index in range(image_count))

    if accepted:
        monkeypatch.setattr(group_module, "validate_source", lambda _source: 1)
        monkeypatch.setattr(
            group_module,
            "decode_image",
            lambda _source: DecodedImageInfo(format="PNG", width=1, height=1),
        )
        assert len(group_module.validate_image_group(sources)) == image_count
        return

    def fail_on_file_access(_source):
        raise AssertionError("group count must fail before file access")

    monkeypatch.setattr(group_module, "validate_source", fail_on_file_access)
    monkeypatch.setattr(group_module, "decode_image", fail_on_file_access)

    with pytest.raises(InvalidSource) as raised:
        group_module.validate_image_group(sources)

    assert raised.value.code == "SOURCE_TOO_LARGE"
    assert raised.value.details == {
        "image_count": image_count,
        "maximum_image_count": MAX_IMAGE_GROUP_COUNT,
    }


@pytest.mark.parametrize(
    ("limit_offset", "accepted"),
    [(-1, True), (0, True), (1, False)],
    ids=["one-below", "at", "one-above"],
)
def test_validate_image_group_aggregate_source_byte_boundary(
    monkeypatch,
    limit_offset,
    accepted,
):
    group_module = importlib.import_module("ocrllm.validate_image_group")
    sources = tuple(Path(f"{index}.png") for index in range(5))
    aggregate_bytes = MAX_AGGREGATE_SOURCE_BYTES + limit_offset
    base_size, remainder = divmod(aggregate_bytes, len(sources))
    source_sizes = iter(
        base_size + (1 if index < remainder else 0)
        for index in range(len(sources))
    )
    monkeypatch.setattr(group_module, "validate_source", lambda _source: next(source_sizes))

    if accepted:
        monkeypatch.setattr(
            group_module,
            "decode_image",
            lambda _source: DecodedImageInfo(format="PNG", width=1, height=1),
        )
        assert len(group_module.validate_image_group(sources)) == len(sources)
        return

    def fail_if_decoded(_source):
        raise AssertionError("aggregate byte rejection must happen before decode")

    monkeypatch.setattr(group_module, "decode_image", fail_if_decoded)

    with pytest.raises(InvalidSource) as raised:
        group_module.validate_image_group(sources)

    assert raised.value.code == "SOURCE_TOO_LARGE"
    assert raised.value.details == {
        "aggregate_byte_size": aggregate_bytes,
        "maximum_aggregate_byte_size": MAX_AGGREGATE_SOURCE_BYTES,
    }


@pytest.mark.parametrize(
    ("limit_offset", "accepted"),
    [(-1, True), (0, True), (1, False)],
    ids=["one-below", "at", "one-above"],
)
def test_validate_image_group_aggregate_pixel_boundary(
    monkeypatch,
    limit_offset,
    accepted,
):
    group_module = importlib.import_module("ocrllm.validate_image_group")
    sources = tuple(Path(f"{index}.png") for index in range(4))
    monkeypatch.setattr(group_module, "validate_source", lambda _source: 1)
    aggregate_pixels = MAX_AGGREGATE_PIXELS + limit_offset
    base_pixels, remainder = divmod(aggregate_pixels, len(sources))
    decoded_images = iter(
        DecodedImageInfo(
            format="PNG",
            width=base_pixels + (1 if index < remainder else 0),
            height=1,
        )
        for index in range(len(sources))
    )
    monkeypatch.setattr(group_module, "decode_image", lambda _source: next(decoded_images))

    if accepted:
        decoded = group_module.validate_image_group(sources)
        assert sum(image.pixel_count for image in decoded) == aggregate_pixels
        return

    with pytest.raises(InvalidSource) as raised:
        group_module.validate_image_group(sources)

    assert raised.value.code == "SOURCE_TOO_LARGE"
    assert raised.value.details == {
        "aggregate_pixel_count": aggregate_pixels,
        "maximum_aggregate_pixel_count": MAX_AGGREGATE_PIXELS,
    }


class _FakeBombWarning(RuntimeWarning):
    pass


class _FakeBombError(Exception):
    pass


class _FakeImage:
    def __init__(self, *, size, image_format):
        self.size = size
        self.format = image_format

    def __enter__(self):
        return self

    def __exit__(self, _error_type, _error, _traceback):
        return False

    def verify(self):
        return None

    def load(self):
        return None


class _FakeImageModule:
    DecompressionBombWarning = _FakeBombWarning
    DecompressionBombError = _FakeBombError

    def __init__(self, *, size, image_format, warn_about_bomb=False):
        self._size = size
        self._format = image_format
        self._warn_about_bomb = warn_about_bomb

    def open(self, _source):
        if self._warn_about_bomb:
            warnings.warn("test-only decompression bomb", self.DecompressionBombWarning)
        return _FakeImage(size=self._size, image_format=self._format)
