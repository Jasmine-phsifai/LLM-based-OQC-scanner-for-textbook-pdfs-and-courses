"""Regression tests for bounded resume-source fingerprinting."""

from __future__ import annotations

import hashlib

import pytest

from ocrllm.errors import OutputError
from ocrllm.fingerprint_image_sources import fingerprint_image_sources

from install_close_failing_stream import install_close_failing_stream


def test_fingerprint_uses_original_uri_and_exact_snapshot_bytes(tmp_path) -> None:
    source = tmp_path / "original.png"
    snapshot = tmp_path / "owned.snapshot"
    source.write_bytes(b"original")
    snapshot.write_bytes(b"owned bytes")

    fingerprint = fingerprint_image_sources((source,), (snapshot,))[0]

    assert fingerprint.uri == source.resolve().as_uri()
    assert fingerprint.byte_size == len(b"owned bytes")
    assert fingerprint.sha256 == hashlib.sha256(b"owned bytes").hexdigest()


def test_fingerprint_rejects_snapshot_growth_beyond_the_validated_limit(
    tmp_path,
    monkeypatch,
) -> None:
    source = tmp_path / "original.png"
    snapshot = tmp_path / "owned.snapshot"
    source.write_bytes(b"original")
    snapshot.write_bytes(b"12345")
    module = __import__("ocrllm.fingerprint_image_sources", fromlist=["unused"])
    monkeypatch.setattr(module, "MAX_SOURCE_BYTES", 4)

    with pytest.raises(OutputError) as raised:
        fingerprint_image_sources((source,), (snapshot,))

    assert raised.value.code == "OUTPUT_WRITE_FAILED"
    assert str(snapshot) not in str(raised.value)


def test_fingerprint_reports_missing_owned_snapshot_as_output_failure(tmp_path) -> None:
    source = tmp_path / "original.png"
    source.write_bytes(b"original")

    with pytest.raises(OutputError) as raised:
        fingerprint_image_sources((source,), (tmp_path / "missing.snapshot",))

    assert raised.value.code == "OUTPUT_WRITE_FAILED"


@pytest.mark.parametrize(
    "read_error",
    [OutputError("typed", code="OUTPUT_WRITE_FAILED"), KeyboardInterrupt()],
)
def test_fingerprint_preserves_primary_failure_over_close_failure(
    tmp_path,
    monkeypatch,
    read_error,
) -> None:
    source = tmp_path / "original.png"
    snapshot = tmp_path / "owned.snapshot"
    source.write_bytes(b"original")
    snapshot.write_bytes(b"owned")
    install_close_failing_stream(
        monkeypatch,
        matches=lambda path, mode: path == snapshot and mode == "rb",
        read_error=read_error,
        close_error=OSError("close detail must stay private"),
    )

    with pytest.raises(type(read_error)) as raised:
        fingerprint_image_sources((source,), (snapshot,))

    if isinstance(read_error, OutputError):
        assert raised.value is read_error
        assert raised.value.details["snapshot_stream_cleanup_failed"] is True


def test_fingerprint_maps_close_only_failure_without_leaking_details(
    tmp_path,
    monkeypatch,
) -> None:
    source = tmp_path / "original.png"
    snapshot = tmp_path / "owned.snapshot"
    source.write_bytes(b"original")
    snapshot.write_bytes(b"owned")
    install_close_failing_stream(
        monkeypatch,
        matches=lambda path, mode: path == snapshot and mode == "rb",
        close_error=OSError("close detail must stay private"),
    )

    with pytest.raises(OutputError) as raised:
        fingerprint_image_sources((source,), (snapshot,))

    assert raised.value.code == "OUTPUT_WRITE_FAILED"
    assert "close detail" not in str(raised.value)
