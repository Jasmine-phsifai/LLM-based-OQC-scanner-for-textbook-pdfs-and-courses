"""Black-box proof that invalid images never spend a provider call."""

from __future__ import annotations

import importlib
import traceback
from pathlib import Path

import pytest

from ocrllm import Config, InvalidSource, OutputError, UnsupportedFormat, recognize
from ocrllm.imaging.decode_image_bytes import MAX_IMAGE_PIXELS
from ocrllm.imaging.decoded_image_info import DecodedImageInfo
from ocrllm.validate_image_group import (
    MAX_AGGREGATE_PIXELS,
    MAX_AGGREGATE_SOURCE_BYTES,
)
from ocrllm.validate_source import MAX_SOURCE_BYTES
from install_close_failing_stream import install_close_failing_stream
from write_test_image import write_test_image


class CountingProvider:
    def __init__(self) -> None:
        self.calls = 0

    def recognize_images(self, image_paths, *, prompt, config):
        self.calls += 1
        return "# Unexpected provider call\n"


@pytest.mark.parametrize(
    ("filename", "contents", "expected_error", "expected_code"),
    [
        ("empty.png", b"", InvalidSource, "SOURCE_INVALID"),
        ("corrupt.png", b"not an image", InvalidSource, "SOURCE_INVALID"),
        ("unsupported.webp", b"not inspected", UnsupportedFormat, "UNSUPPORTED_FORMAT"),
    ],
)
def test_invalid_source_content_fails_before_provider(
    tmp_path,
    filename,
    contents,
    expected_error,
    expected_code,
):
    source = tmp_path / filename
    source.write_bytes(contents)
    provider = CountingProvider()

    with pytest.raises(expected_error) as captured:
        recognize(source, config=Config(provider=provider))

    assert captured.value.code == expected_code
    assert provider.calls == 0


def test_missing_source_fails_before_provider(tmp_path):
    provider = CountingProvider()
    path_sentinel = "MISSING_SOURCE_PATH_SECRET_475a"

    with pytest.raises(InvalidSource) as captured:
        recognize(
            tmp_path / f"{path_sentinel}.png",
            config=Config(provider=provider),
        )

    assert captured.value.code == "SOURCE_NOT_FOUND"
    assert provider.calls == 0
    rendered = "".join(
        traceback.format_exception(
            type(captured.value),
            captured.value,
            captured.value.__traceback__,
        )
    )
    assert path_sentinel not in rendered
    assert captured.value.__cause__ is None
    assert captured.value.__context__ is None


def test_unreadable_source_fails_before_provider(tmp_path, monkeypatch):
    source = write_test_image(tmp_path / "unreadable.png")
    provider = CountingProvider()
    original_open = Path.open

    def deny_source_open(path, *args, **kwargs):
        if path == source:
            raise PermissionError("test-only source denial")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", deny_source_open)

    with pytest.raises(InvalidSource) as captured:
        recognize(source, config=Config(provider=provider))

    assert captured.value.code == "SOURCE_UNREADABLE"
    assert provider.calls == 0


def test_short_snapshot_write_fails_before_provider(tmp_path, monkeypatch):
    source = write_test_image(tmp_path / "short-write.png")
    temp_dir = tmp_path / "snapshots"
    provider = CountingProvider()
    original_open = Path.open

    class ShortWriter:
        def __init__(self, wrapped) -> None:
            self.wrapped = wrapped

        def __getattr__(self, name):
            return getattr(self.wrapped, name)

        def write(self, data):
            return self.wrapped.write(data[:-1])

    def short_write_snapshot(path, *args, **kwargs):
        opened = original_open(path, *args, **kwargs)
        if path.parent.name.isdigit() and path.parent.parent.name.startswith(
            "ocrllm-images-"
        ):
            return ShortWriter(opened)
        return opened

    monkeypatch.setattr(Path, "open", short_write_snapshot)

    with pytest.raises(OutputError) as captured:
        recognize(
            source,
            config=Config(provider=provider, temp_dir=temp_dir),
        )

    assert captured.value.code == "OUTPUT_WRITE_FAILED"
    assert provider.calls == 0
    assert list(temp_dir.glob("ocrllm-images-*")) == []


def test_validation_stream_close_failure_is_typed_before_snapshot_and_provider(
    tmp_path,
    monkeypatch,
) -> None:
    source = write_test_image(tmp_path / "validation-close.png")
    temp_dir = tmp_path / "snapshots"
    provider = CountingProvider()
    secret = "validation-close-secret-7341"
    install_close_failing_stream(
        monkeypatch,
        matches=lambda path, mode: path == source and mode == "rb",
        close_error=OSError(secret),
    )

    with pytest.raises(InvalidSource) as captured:
        recognize(
            source,
            config=Config(provider=provider, temp_dir=temp_dir),
        )

    assert captured.value.code == "SOURCE_UNREADABLE"
    assert provider.calls == 0
    assert not temp_dir.exists()
    rendered = "".join(
        traceback.format_exception(
            type(captured.value),
            captured.value,
            captured.value.__traceback__,
        )
    )
    assert secret not in rendered
    assert secret not in str(captured.value)
    assert secret not in repr(captured.value.details)


@pytest.mark.parametrize(
    ("stream_kind", "expected_error", "expected_code"),
    [
        ("source", InvalidSource, "SOURCE_UNREADABLE"),
        ("destination", OutputError, "OUTPUT_WRITE_FAILED"),
    ],
)
def test_snapshot_stream_close_failure_is_typed_before_provider(
    tmp_path,
    monkeypatch,
    stream_kind,
    expected_error,
    expected_code,
) -> None:
    sources = tuple(
        write_test_image(tmp_path / f"board-{index}.png", color=(index, 2, 3))
        for index in range(3)
    )
    target_source = sources[1]
    temp_dir = tmp_path / "snapshots"
    provider = CountingProvider()
    secret = f"{stream_kind}-close-secret-6254"
    snapshot_source_opens: list[Path] = []

    def matches(path: Path, mode: str) -> bool:
        snapshot_started = any(temp_dir.glob("ocrllm-images-*"))
        if snapshot_started and mode == "rb" and path in sources:
            snapshot_source_opens.append(path)
        if stream_kind == "source":
            return snapshot_started and path == target_source and mode == "rb"
        return (
            mode == "xb"
            and path.name == target_source.name
            and path.parent.parent.name.startswith("ocrllm-images-")
        )

    install_close_failing_stream(
        monkeypatch,
        matches=matches,
        close_error=OSError(secret),
    )

    with pytest.raises(expected_error) as captured:
        recognize(
            sources,
            config=Config(provider=provider, temp_dir=temp_dir),
        )

    assert captured.value.code == expected_code
    assert provider.calls == 0
    assert sources[2] not in snapshot_source_opens
    assert list(temp_dir.glob("ocrllm-images-*")) == []
    rendered = "".join(
        traceback.format_exception(
            type(captured.value),
            captured.value,
            captured.value.__traceback__,
        )
    )
    assert secret not in rendered
    assert secret not in str(captured.value)
    assert secret not in repr(captured.value.details)


def test_oversized_source_fails_before_provider(tmp_path):
    source = tmp_path / "oversized.png"
    with source.open("wb") as stream:
        stream.write(b"x")
        stream.truncate(MAX_SOURCE_BYTES + 1)
    provider = CountingProvider()

    with pytest.raises(InvalidSource) as captured:
        recognize(source, config=Config(provider=provider))

    assert captured.value.code == "SOURCE_TOO_LARGE"
    assert provider.calls == 0


def test_decoded_pixel_one_above_fails_before_provider(tmp_path, monkeypatch):
    decode_module = importlib.import_module("ocrllm.imaging.decode_image_bytes")
    source = write_test_image(tmp_path / "pixel-limit.png")

    class FakeImage:
        size = (MAX_IMAGE_PIXELS + 1, 1)
        format = "PNG"

        def __enter__(self):
            return self

        def __exit__(self, _error_type, _error, _traceback):
            return False

        def verify(self):
            return None

        def load(self):
            return None

    class FakeBombWarning(RuntimeWarning):
        pass

    class FakeBombError(Exception):
        pass

    class FakeImageModule:
        DecompressionBombWarning = FakeBombWarning
        DecompressionBombError = FakeBombError

        @staticmethod
        def open(_source):
            return FakeImage()

    monkeypatch.setattr(
        decode_module,
        "_load_pillow",
        lambda: (FakeImageModule, OSError),
    )
    provider = CountingProvider()

    with pytest.raises(InvalidSource) as captured:
        recognize(
            source,
            config=Config(provider=provider, temp_dir=tmp_path / "snapshots"),
        )

    assert captured.value.code == "SOURCE_TOO_LARGE"
    assert captured.value.details == {
        "pixel_count": MAX_IMAGE_PIXELS + 1,
        "maximum_pixel_count": MAX_IMAGE_PIXELS,
    }
    assert provider.calls == 0


def test_invalid_later_group_member_fails_before_provider(tmp_path):
    valid = write_test_image(tmp_path / "valid.png")
    invalid = tmp_path / "invalid.jpg"
    invalid.write_bytes(b"not a JPEG")
    provider = CountingProvider()

    with pytest.raises(InvalidSource) as captured:
        recognize((valid, invalid), config=Config(provider=provider))

    assert captured.value.code == "SOURCE_INVALID"
    assert provider.calls == 0


def test_too_many_images_fail_before_file_or_provider_access(tmp_path):
    sources = tuple(tmp_path / f"missing-{index}.png" for index in range(11))
    provider = CountingProvider()

    with pytest.raises(InvalidSource) as captured:
        recognize(sources, config=Config(provider=provider))

    assert captured.value.code == "SOURCE_TOO_LARGE"
    assert provider.calls == 0


def test_aggregate_source_one_above_fails_before_provider_or_temp_access(
    tmp_path,
    monkeypatch,
):
    snapshot_module = importlib.import_module("ocrllm.imaging.snapshot_image_group")
    sources = tuple(tmp_path / f"missing-{index}.png" for index in range(5))
    aggregate_bytes = MAX_AGGREGATE_SOURCE_BYTES + 1
    base_size, remainder = divmod(aggregate_bytes, len(sources))
    source_sizes = iter(
        base_size + (1 if index < remainder else 0)
        for index in range(len(sources))
    )
    monkeypatch.setattr(
        snapshot_module,
        "validate_source",
        lambda _source: next(source_sizes),
    )

    def fail_on_temp_access(_configured_parent):
        raise AssertionError("aggregate bytes must fail before temporary output")

    monkeypatch.setattr(
        snapshot_module,
        "_prepare_temporary_parent",
        fail_on_temp_access,
    )
    provider = CountingProvider()

    with pytest.raises(InvalidSource) as captured:
        recognize(sources, config=Config(provider=provider))

    assert captured.value.code == "SOURCE_TOO_LARGE"
    assert provider.calls == 0


def test_aggregate_pixels_one_above_fails_before_provider(tmp_path, monkeypatch):
    group_module = importlib.import_module("ocrllm.validate_image_group")
    sources = tuple(
        write_test_image(tmp_path / f"pixel-{index}.png") for index in range(4)
    )
    aggregate_pixels = MAX_AGGREGATE_PIXELS + 1
    base_pixels, remainder = divmod(aggregate_pixels, len(sources))
    decoded_images = iter(
        DecodedImageInfo(
            format="PNG",
            width=base_pixels + (1 if index < remainder else 0),
            height=1,
        )
        for index in range(len(sources))
    )
    monkeypatch.setattr(
        group_module,
        "decode_image",
        lambda _source: next(decoded_images),
    )
    provider = CountingProvider()

    with pytest.raises(InvalidSource) as captured:
        recognize(
            sources,
            config=Config(provider=provider, temp_dir=tmp_path / "snapshots"),
        )

    assert captured.value.code == "SOURCE_TOO_LARGE"
    assert captured.value.details == {
        "aggregate_pixel_count": aggregate_pixels,
        "maximum_aggregate_pixel_count": MAX_AGGREGATE_PIXELS,
    }
    assert provider.calls == 0
