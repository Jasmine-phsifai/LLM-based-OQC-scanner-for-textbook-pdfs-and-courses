"""Public offline regressions for the bounded PDF-through-image slice."""

from __future__ import annotations

import json
import importlib
import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

from ocrllm import (
    Cancelled,
    Config,
    InvalidSource,
    OutputError,
    PDFError,
    RecognitionExecutionPolicy,
    recognize,
    recognize_batch,
)
from ocrllm.errors import ProviderError
from ocrllm.pdf.snapshot_pdf import MAX_PDF_SOURCE_BYTES

from write_test_image import write_test_image


class _FakePdfPage:
    def __init__(self, page_index: int) -> None:
        self._page_index = page_index
        self.closed = False

    def render(self, *, scale: float):
        assert scale > 0
        return _FakePdfBitmap(self._page_index)

    def close(self) -> None:
        self.closed = True


class _FakePdfBitmap:
    def __init__(self, page_index: int) -> None:
        self._page_index = page_index
        self.closed = False

    def to_pil(self):
        from PIL import Image

        value = (self._page_index + 1) % 251
        return Image.new("RGB", (32, 32), color=(value, value, value))

    def close(self) -> None:
        self.closed = True


class _FakePdfDocument:
    def __init__(self, page_count: int) -> None:
        self._page_count = page_count
        self.closed = False

    def __len__(self) -> int:
        return self._page_count

    def get_page_size(self, page_index: int) -> tuple[float, float]:
        assert 0 <= page_index < self._page_count
        return 72.0, 72.0

    def get_page(self, page_index: int) -> _FakePdfPage:
        assert 0 <= page_index < self._page_count
        return _FakePdfPage(page_index)

    def close(self) -> None:
        self.closed = True


class _RecordingProvider:
    resume_identity = "offline-pdf-provider-v1"

    def __init__(
        self,
        *,
        state_directory: Path | None = None,
        cancel_after_first_call: threading.Event | None = None,
        fail_once_on_call: int | None = None,
    ) -> None:
        self.calls: list[tuple[str, ...]] = []
        self.call_paths: list[tuple[Path, ...]] = []
        self.rendered_counts_during_calls: list[int] = []
        self._state_directory = state_directory
        self._cancel_after_first_call = cancel_after_first_call
        self._fail_once_on_call = fail_once_on_call
        self._call_lock = threading.Lock()
        self._active_calls = 0
        self.maximum_active_calls = 0

    def recognize_images(self, image_paths, *, prompt: str, config: Config) -> str:
        with self._call_lock:
            self._active_calls += 1
            self.maximum_active_calls = max(
                self.maximum_active_calls,
                self._active_calls,
            )
        try:
            assert "input order" in prompt
            paths = tuple(Path(path) for path in image_paths)
            names = tuple(path.name for path in paths)
            self.call_paths.append(paths)
            self.calls.append(names)
            if self._state_directory is not None:
                self.rendered_counts_during_calls.append(
                    len(tuple(self._state_directory.glob("page-*.png")))
                )
            if self._cancel_after_first_call is not None and len(self.calls) == 1:
                self._cancel_after_first_call.set()
            if self._fail_once_on_call == len(self.calls):
                self._fail_once_on_call = None
                raise ConnectionError("test-only provider outage")
            # A small overlap window makes an accidental parallel PDF loop observable.
            time.sleep(0.01)
            return f"Recognized {names[0]} through {names[-1]}."
        finally:
            with self._call_lock:
                self._active_calls -= 1


def _install_fake_pdfium(monkeypatch, *, page_count: int = 16) -> None:
    fake_module = SimpleNamespace(
        PYPDFIUM_INFO=SimpleNamespace(api_tag=(5, 11, 0), beta=None),
        PdfDocument=lambda _path: _FakePdfDocument(page_count),
    )
    monkeypatch.setitem(sys.modules, "pypdfium2", fake_module)


def _write_pdf_placeholder(path: Path) -> Path:
    path.write_bytes(b"%PDF-1.7\n% offline fake backend fixture\n")
    return path


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


def _pdf_config(
    provider: _RecordingProvider,
    *,
    output_dir: Path | None = None,
    resume: bool = False,
    cancellation: object | None = None,
) -> Config:
    return Config(
        provider=provider,
        output_dir=output_dir,
        resume=resume,
        cancellation=cancellation,
        execution=RecognitionExecutionPolicy(max_parallel_requests=4),
    )


def test_public_pdf_uses_two_ordered_bounded_image_groups(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _install_fake_pdfium(monkeypatch, page_count=16)
    source = _write_pdf_placeholder(tmp_path / "book.pdf")
    output_dir = tmp_path / "output"
    state_directory = output_dir / "book_board"
    provider = _RecordingProvider(state_directory=state_directory)

    result = recognize(
        source,
        config=_pdf_config(provider, output_dir=output_dir),
    )

    assert provider.calls == [
        tuple(f"page-{page_number:06d}.png" for page_number in range(1, 9)),
        tuple(f"page-{page_number:06d}.png" for page_number in range(9, 17)),
    ]
    assert provider.rendered_counts_during_calls == [8, 8]
    assert provider.maximum_active_calls == 1
    assert not tuple(state_directory.glob("page-*.png"))
    state_paths = sorted(state_directory.glob("*.ocrllm-state.json"))
    assert len(state_paths) == 2
    assert all(
        json.loads(path.read_text(encoding="utf-8"))["result"]["status"] == "complete"
        for path in state_paths
    )
    first_marker = "<!-- ocrllm:pdf-pages start=1 end=8 -->"
    second_marker = "<!-- ocrllm:pdf-pages start=9 end=16 -->"
    assert result.markdown.count("<!-- ocrllm:pdf-pages") == 2
    assert result.markdown.index(first_marker) < result.markdown.index(second_marker)
    assert result.source_type == "pdf"
    assert result.status == "complete"
    assert result.output_path == output_dir / "book_board.md"
    assert result.output_path.read_text(encoding="utf-8") == result.markdown
    assert result.metadata["page_count"] == 16
    assert result.metadata["pdf_group_count"] == 2
    assert result.metadata["current_run_provider_call_count"] == 2


def test_cancel_after_first_pdf_group_resumes_without_replaying_it(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _install_fake_pdfium(monkeypatch, page_count=16)
    source = _write_pdf_placeholder(tmp_path / "book.pdf")
    output_dir = tmp_path / "output"
    cancellation = threading.Event()
    provider = _RecordingProvider(cancel_after_first_call=cancellation)

    with pytest.raises(Cancelled) as interrupted:
        recognize(
            source,
            config=_pdf_config(
                provider,
                output_dir=output_dir,
                cancellation=cancellation,
            ),
        )

    assert provider.calls == [
        tuple(f"page-{page_number:06d}.png" for page_number in range(1, 9))
    ]
    assert interrupted.value.details["provider_calls_attempted"] == 1
    assert interrupted.value.details["settled_pdf_group_count"] == 1
    assert not (output_dir / "book_board.md").exists()
    assert len(tuple((output_dir / "book_board").glob("*.ocrllm-state.json"))) == 1

    resumed = recognize(
        source,
        config=_pdf_config(provider, output_dir=output_dir, resume=True),
    )

    assert provider.calls == [
        tuple(f"page-{page_number:06d}.png" for page_number in range(1, 9)),
        tuple(f"page-{page_number:06d}.png" for page_number in range(9, 17)),
    ]
    assert resumed.metadata["current_run_provider_call_count"] == 1
    assert resumed.metadata["pdf_group_count"] == 2
    assert resumed.output_path == output_dir / "book_board.md"
    assert provider.maximum_active_calls == 1
    assert len(tuple((output_dir / "book_board").glob("*.ocrllm-state.json"))) == 2


def test_second_pdf_group_provider_failure_keeps_first_state_and_resumes(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _install_fake_pdfium(monkeypatch, page_count=16)
    source = _write_pdf_placeholder(tmp_path / "book.pdf")
    output_dir = tmp_path / "output"
    state_directory = output_dir / "book_board"
    provider = _RecordingProvider(fail_once_on_call=2)

    with pytest.raises(ProviderError) as interrupted:
        recognize(
            source,
            config=_pdf_config(provider, output_dir=output_dir),
        )

    assert interrupted.value.code == "PROVIDER_NETWORK"
    assert interrupted.value.retryable is True
    assert interrupted.value.details["provider_calls_attempted"] == 2
    assert interrupted.value.details["settled_pdf_group_count"] == 1
    assert provider.calls == [
        tuple(f"page-{page_number:06d}.png" for page_number in range(1, 9)),
        tuple(f"page-{page_number:06d}.png" for page_number in range(9, 17)),
    ]
    assert not (output_dir / "book_board.md").exists()
    assert len(tuple(state_directory.glob("*.ocrllm-state.json"))) == 1

    resumed = recognize(
        source,
        config=_pdf_config(provider, output_dir=output_dir, resume=True),
    )

    assert provider.calls == [
        tuple(f"page-{page_number:06d}.png" for page_number in range(1, 9)),
        tuple(f"page-{page_number:06d}.png" for page_number in range(9, 17)),
        tuple(f"page-{page_number:06d}.png" for page_number in range(9, 17)),
    ]
    assert resumed.status == "complete"
    assert resumed.metadata["pdf_group_count"] == 2
    assert resumed.metadata["current_run_provider_call_count"] == 1
    assert resumed.output_path == output_dir / "book_board.md"
    assert (output_dir / "book_board.md").is_file()
    assert len(tuple(state_directory.glob("*.ocrllm-state.json"))) == 2


@pytest.mark.parametrize(
    ("backend_error_code", "expected_code"),
    ((4, "PDF_PASSWORD_REQUIRED"), (3, "PDF_INVALID")),
)
def test_pdf_open_failure_happens_before_provider_dispatch(
    tmp_path: Path,
    monkeypatch,
    backend_error_code: int,
    expected_code: str,
) -> None:
    class BackendOpenError(Exception):
        def __init__(self) -> None:
            self.err_code = backend_error_code

    def fail_open(_path):
        raise BackendOpenError()

    monkeypatch.setitem(
        sys.modules,
        "pypdfium2",
        SimpleNamespace(
            PYPDFIUM_INFO=SimpleNamespace(api_tag=(5, 11, 0), beta=None),
            PdfDocument=fail_open,
        ),
    )
    source = _write_pdf_placeholder(tmp_path / "broken.pdf")
    provider = _RecordingProvider()

    with pytest.raises(PDFError) as captured:
        recognize(source, config=_pdf_config(provider))

    assert captured.value.code == expected_code
    assert provider.calls == []


def test_oversized_pdf_is_rejected_before_backend_or_provider(
    tmp_path: Path,
) -> None:
    source = tmp_path / "oversized.pdf"
    with source.open("wb") as stream:
        stream.truncate(MAX_PDF_SOURCE_BYTES + 1)
    provider = _RecordingProvider()

    with pytest.raises(InvalidSource) as captured:
        recognize(source, config=_pdf_config(provider))

    assert captured.value.code == "SOURCE_TOO_LARGE"
    assert provider.calls == []


def test_grouped_or_mixed_pdf_input_is_rejected_before_provider(
    tmp_path: Path,
) -> None:
    first_pdf = _write_pdf_placeholder(tmp_path / "first.pdf")
    second_pdf = _write_pdf_placeholder(tmp_path / "second.pdf")
    image = write_test_image(tmp_path / "board.png")
    provider = _RecordingProvider()

    for source in ((first_pdf, second_pdf), (first_pdf, image)):
        with pytest.raises(InvalidSource) as captured:
            recognize(source, config=_pdf_config(provider))
        assert captured.value.code == "SOURCE_INVALID"

    assert provider.calls == []


def test_recognize_batch_rejects_pdf_before_backend_or_provider(tmp_path: Path) -> None:
    source = _write_pdf_placeholder(tmp_path / "book.pdf")
    provider = _RecordingProvider()

    with pytest.raises(InvalidSource) as captured:
        recognize_batch((source,), config=_pdf_config(provider))

    assert captured.value.code == "SOURCE_INVALID"
    assert provider.calls == []


def test_pdf_paths_stay_within_legacy_windows_limit(
    tmp_path: Path,
    monkeypatch,
) -> None:
    if _windows_path_units(tmp_path) >= 111:
        pytest.skip("pytest temporary path is already too long for this boundary")
    _install_fake_pdfium(monkeypatch, page_count=8)
    output_dir = _make_directory_with_windows_path_units(tmp_path, 111)
    long_stem = "s" * 96
    source = _write_pdf_placeholder(tmp_path / f"{long_stem}.pdf")
    state_directory = output_dir / f"{long_stem}_board"
    provider = _RecordingProvider(state_directory=state_directory)
    _enforce_legacy_windows_open_limit(monkeypatch)

    result = recognize(
        source,
        config=_pdf_config(provider, output_dir=output_dir),
    )

    created_paths = (
        result.output_path,
        state_directory,
        *tuple(state_directory.iterdir()),
        *(path for call in provider.call_paths for path in call),
    )
    assert all(path is not None for path in created_paths)
    assert (
        max(_windows_path_units(path) for path in created_paths if path is not None)
        <= 259
    )
    assert all(
        str(path).count(long_stem) <= 1
        for path in created_paths
        if path is not None
    )


def test_pre_provider_render_failure_removes_new_empty_pdf_state_directory(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _install_fake_pdfium(monkeypatch, page_count=8)
    source = _write_pdf_placeholder(tmp_path / "book.pdf")
    output_dir = tmp_path / "output"
    state_directory = output_dir / "book_board"
    provider = _RecordingProvider()
    processor = importlib.import_module("ocrllm.processors.recognize_pdf")

    @contextmanager
    def fail_before_render_yield(*_args, **_kwargs):
        raise OutputError("test-only render preparation failure")
        yield ()  # pragma: no cover

    monkeypatch.setattr(
        processor,
        "render_pdf_page_group",
        fail_before_render_yield,
    )

    with pytest.raises(OutputError) as captured:
        recognize(
            source,
            config=_pdf_config(provider, output_dir=output_dir),
        )

    assert captured.value.code == "OUTPUT_WRITE_FAILED"
    assert captured.value.details["provider_calls_attempted"] == 0
    assert provider.calls == []
    assert not state_directory.exists()


def test_generated_pdf_png_decode_failure_is_local_after_settled_group(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _install_fake_pdfium(monkeypatch, page_count=16)
    source = _write_pdf_placeholder(tmp_path / "book.pdf")
    output_dir = tmp_path / "output"
    state_directory = output_dir / "book_board"
    provider = _RecordingProvider()
    rendering = importlib.import_module("ocrllm.pdf.render_pdf_page_group")
    decode_image = rendering.decode_image
    decode_calls = 0

    def fail_ninth_generated_png(path):
        nonlocal decode_calls
        decode_calls += 1
        if decode_calls == 9:
            raise InvalidSource(
                "test-only generated PNG decode failure",
                code="SOURCE_INVALID",
            )
        return decode_image(path)

    monkeypatch.setattr(rendering, "decode_image", fail_ninth_generated_png)

    with pytest.raises(OutputError) as captured:
        recognize(
            source,
            config=_pdf_config(provider, output_dir=output_dir),
        )

    assert captured.value.code == "OUTPUT_WRITE_FAILED"
    assert captured.value.details["page_number"] == 9
    assert captured.value.details["provider_calls_attempted"] == 1
    assert captured.value.details["settled_pdf_group_count"] == 1
    assert "test-only" not in str(captured.value)
    assert provider.calls == [
        tuple(f"page-{page_number:06d}.png" for page_number in range(1, 9))
    ]
    assert not (output_dir / "book_board.md").exists()
    assert len(tuple(state_directory.glob("*.ocrllm-state.json"))) == 1
    assert not tuple(state_directory.glob("page-*.png"))
    assert not tuple(state_directory.glob(".p-*.tmp.png"))
