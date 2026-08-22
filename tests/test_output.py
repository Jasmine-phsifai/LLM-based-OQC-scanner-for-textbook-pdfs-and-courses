"""Black-box tests for optional and atomic Markdown output."""

from __future__ import annotations

import importlib
import os
import shutil
from pathlib import Path

import pytest

from ocrllm import Config, OutputError, OutputExists, ProviderError, recognize

from write_test_image import write_test_image


def test_output_stem_normalization_replaces_ascii_delete_control():
    normalize_module = importlib.import_module("ocrllm.output.normalize_output_stem")

    assert normalize_module.normalize_output_stem("before\x7fafter") == "before_after"


class CountingProvider:
    """Return fixed Markdown while exposing the invocation count."""

    def __init__(self, markdown: str = "# Fresh board\n") -> None:
        self.markdown = markdown
        self.calls = 0

    def recognize_images(self, image_paths, *, prompt, config):
        self.calls += 1
        return self.markdown


def _windows_path_units(path: Path) -> int:
    return len(str(path).encode("utf-16-le")) // 2


def _make_directory_with_windows_path_units(
    base: Path,
    target_units: int,
) -> Path:
    current = base
    while _windows_path_units(current) < target_units:
        remaining = target_units - _windows_path_units(current) - 1
        if remaining < 1:
            raise AssertionError(
                "target path length cannot be reached by adding a directory"
            )
        current /= "d" * min(40, remaining)
    assert _windows_path_units(current) == target_units
    current.mkdir(parents=True)
    return current


def _enforce_legacy_windows_open_limit(monkeypatch) -> None:
    original_open = Path.open

    def open_with_legacy_limit(path, *args, **kwargs):
        if _windows_path_units(path) > 259:
            raise OSError(
                206,
                "test-only simulated legacy Windows path limit",
                str(path),
            )
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", open_with_legacy_limit)


def test_output_dir_none_keeps_result_in_memory_and_writes_nothing(tmp_path):
    source = write_test_image(tmp_path / "board.png")
    files_before = set(tmp_path.iterdir())

    result = recognize(source, config=Config(provider=CountingProvider()))

    assert result.output_path is None
    assert result.markdown == "# Fresh board\n"
    assert set(tmp_path.iterdir()) == files_before


def test_single_and_ordered_group_output_names_are_deterministic(tmp_path):
    first = write_test_image(tmp_path / "lecture.png", color=(1, 2, 3))
    second = write_test_image(tmp_path / "later.jpg", color=(4, 5, 6))
    third = write_test_image(tmp_path / "last.jpeg", color=(7, 8, 9))
    single_dir = tmp_path / "single-output"
    group_dir = tmp_path / "group-output"

    single = recognize(
        first,
        config=Config(provider=CountingProvider("# Single\n"), output_dir=single_dir),
    )
    group = recognize(
        [first, second, third],
        config=Config(provider=CountingProvider("# Group\n"), output_dir=group_dir),
    )

    assert single.output_path == single_dir / "lecture_board.md"
    assert group.output_path == group_dir / "lecture_plus_2_board.md"
    assert single.output_path.read_text(encoding="utf-8") == single.markdown
    assert group.output_path.read_text(encoding="utf-8") == group.markdown


@pytest.mark.skipif(
    os.name != "nt",
    reason="Windows legacy path-limit regression",
)
def test_markdown_publish_does_not_amplify_near_limit_output_path(
    tmp_path,
    monkeypatch,
) -> None:
    if _windows_path_units(tmp_path) >= 213:
        pytest.skip("pytest temporary root is already beyond the controlled path range")
    source = write_test_image(tmp_path / "board.png")
    output_dir = _make_directory_with_windows_path_units(tmp_path, 213)
    provider = CountingProvider()
    _enforce_legacy_windows_open_limit(monkeypatch)

    result = recognize(source, config=Config(provider=provider, output_dir=output_dir))

    assert result.output_path == output_dir / "board_board.md"
    assert _windows_path_units(result.output_path) == 228
    assert result.output_path.read_text(encoding="utf-8") == "# Fresh board\n"
    assert provider.calls == 1


def test_existing_output_fails_before_provider_invocation(tmp_path):
    source = write_test_image(tmp_path / "board.png")
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    target = output_dir / "board_board.md"
    target.write_text("original", encoding="utf-8")
    provider = CountingProvider()

    with pytest.raises(OutputExists) as captured:
        recognize(source, config=Config(provider=provider, output_dir=output_dir))

    assert captured.value.code == "OUTPUT_EXISTS"
    assert provider.calls == 0
    assert target.read_text(encoding="utf-8") == "original"


def test_overwrite_reuses_the_reported_path_and_replaces_content(tmp_path):
    source = write_test_image(tmp_path / "board.jpeg")
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    target = output_dir / "board_board.md"
    target.write_text("stale", encoding="utf-8")
    provider = CountingProvider("# Replacement\n")

    result = recognize(
        source,
        config=Config(provider=provider, output_dir=output_dir, overwrite=True),
    )

    assert provider.calls == 1
    assert result.output_path == target
    assert target.read_text(encoding="utf-8") == "# Replacement\n"


def test_atomic_publish_failure_preserves_old_target_and_cleans_temporary_file(
    tmp_path,
    monkeypatch,
):
    source = write_test_image(tmp_path / "board.png")
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    target = output_dir / "board_board.md"
    target.write_text("durable old content", encoding="utf-8")
    provider = CountingProvider("# Content that must not be published\n")
    writer_module = importlib.import_module("ocrllm.output.write_markdown_atomically")

    def fail_replace(source_path, destination_path):
        raise OSError("ATOMIC_REPLACE_FAILURE_642adb9a")

    monkeypatch.setattr(writer_module.os, "replace", fail_replace)

    with pytest.raises(OutputError) as captured:
        recognize(
            source,
            config=Config(provider=provider, output_dir=output_dir, overwrite=True),
        )

    assert captured.value.code == "OUTPUT_WRITE_FAILED"
    assert provider.calls == 1
    assert target.read_text(encoding="utf-8") == "durable old content"
    assert list(output_dir.glob(".*.tmp")) == []


def test_post_publish_temp_cleanup_failure_does_not_report_final_output_failure(
    tmp_path,
    monkeypatch,
):
    source = write_test_image(tmp_path / "board.png")
    output_dir = tmp_path / "output"
    provider = CountingProvider("# Published content\n")
    original_unlink = Path.unlink

    def deny_hidden_temp_unlink(path, *args, **kwargs):
        if path.parent == output_dir and path.name.startswith(".ocrllm-"):
            raise PermissionError("test-only delayed cleanup")
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", deny_hidden_temp_unlink)

    result = recognize(
        source,
        config=Config(provider=provider, output_dir=output_dir),
    )

    assert result.output_path == output_dir / "board_board.md"
    assert result.output_path.read_text(encoding="utf-8") == "# Published content\n"
    assert provider.calls == 1
    assert len(list(output_dir.glob(".*.tmp"))) == 1


@pytest.mark.skipif(os.name != "nt", reason="Windows no-clobber rename fallback")
def test_no_overwrite_publish_falls_back_when_hard_links_are_unavailable(
    tmp_path,
    monkeypatch,
):
    source = write_test_image(tmp_path / "board.png")
    output_dir = tmp_path / "output"
    writer_module = importlib.import_module("ocrllm.output.write_markdown_atomically")

    def hard_link_unavailable(_source, _destination):
        raise OSError("test-only filesystem without hard links")

    monkeypatch.setattr(writer_module.os, "link", hard_link_unavailable)

    result = recognize(
        source,
        config=Config(provider=CountingProvider(), output_dir=output_dir),
    )

    assert result.output_path == output_dir / "board_board.md"
    assert result.output_path.read_text(encoding="utf-8") == "# Fresh board\n"
    assert list(output_dir.glob(".*.tmp")) == []


def test_snapshot_cleanup_failure_is_typed_and_never_reported_as_success(
    tmp_path,
    monkeypatch,
):
    source = write_test_image(tmp_path / "board.png")
    temp_dir = tmp_path / "snapshots"
    provider = CountingProvider()
    snapshot_module = importlib.import_module("ocrllm.imaging.snapshot_image_group")
    real_rmtree = shutil.rmtree

    def fail_normal_cleanup(path, *args, **kwargs):
        if not kwargs.get("ignore_errors", False):
            raise PermissionError("test-only retained provider handle")
        return real_rmtree(path, *args, **kwargs)

    monkeypatch.setattr(snapshot_module.shutil, "rmtree", fail_normal_cleanup)

    with pytest.raises(OutputError) as captured:
        recognize(
            source,
            config=Config(provider=provider, temp_dir=temp_dir),
        )

    assert captured.value.code == "OUTPUT_WRITE_FAILED"
    assert provider.calls == 1
    leaked_directories = list(temp_dir.glob("ocrllm-images-*"))
    assert len(leaked_directories) == 1
    real_rmtree(leaked_directories[0])


def test_snapshot_cleanup_failure_does_not_mask_primary_provider_failure(
    tmp_path,
    monkeypatch,
):
    source = write_test_image(tmp_path / "board.png")
    temp_dir = tmp_path / "snapshots"
    snapshot_module = importlib.import_module("ocrllm.imaging.snapshot_image_group")
    real_rmtree = shutil.rmtree

    class TimeoutProvider:
        def recognize_images(self, image_paths, *, prompt, config):
            raise TimeoutError("raw provider timeout")

    def fail_normal_cleanup(path, *args, **kwargs):
        if not kwargs.get("ignore_errors", False):
            raise PermissionError("test-only retained provider handle")
        return real_rmtree(path, *args, **kwargs)

    monkeypatch.setattr(snapshot_module.shutil, "rmtree", fail_normal_cleanup)

    with pytest.raises(ProviderError) as captured:
        recognize(
            source,
            config=Config(provider=TimeoutProvider(), temp_dir=temp_dir),
        )

    assert captured.value.code == "PROVIDER_TIMEOUT"
    assert captured.value.retryable is True
    assert captured.value.details["snapshot_cleanup_failed"] is True
    leaked_directories = list(temp_dir.glob("ocrllm-images-*"))
    assert len(leaked_directories) == 1
    real_rmtree(leaked_directories[0])
