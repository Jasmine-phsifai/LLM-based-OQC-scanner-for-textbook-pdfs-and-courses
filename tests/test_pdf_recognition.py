"""Public offline regressions for the bounded PDF-through-image slice."""

from __future__ import annotations

import json
import importlib
import os
import subprocess
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
    ConfigError,
    GoogleGenAISettings,
    InvalidSource,
    OutputError,
    PDFError,
    RecognitionExecutionPolicy,
    VisionModelSettings,
    recognize,
    recognize_batch,
)
from ocrllm.errors import ProviderError
from ocrllm.pdf.combine_pdf_group_results import combine_pdf_group_results
from ocrllm.pdf.snapshot_pdf import MAX_PDF_SOURCE_BYTES
from ocrllm.providers.vision_provider_response import VisionProviderResponse
from ocrllm.result import RecognitionResult

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
    overwrite: bool = False,
    cancellation: object | None = None,
) -> Config:
    return Config(
        provider=provider,
        output_dir=output_dir,
        resume=resume,
        overwrite=overwrite,
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


def test_public_pdf_preserves_aggregated_local_ocr_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_pdfium(monkeypatch, page_count=9)
    source = _write_pdf_placeholder(tmp_path / "notes.pdf")
    local_ocr = importlib.import_module(
        "ocrllm.local_ocr.recognize_images_with_rapidocr"
    )
    calls: list[Path] = []

    class RecordingEngine:
        def __call__(self, path: Path):
            calls.append(path)
            return SimpleNamespace(
                txts=(f"Page {len(calls)}",),
                scores=(0.9,),
            )

    engine = RecordingEngine()
    monkeypatch.setattr(local_ocr, "load_rapidocr", lambda: lambda **_: engine)
    monkeypatch.setattr(local_ocr, "resolve_rapidocr_version", lambda: "3.9.test")

    result = recognize(source, config=Config(image_mode="ocr"))

    assert len(calls) == 9
    assert result.status == "complete"
    assert result.source_type == "pdf"
    assert result.metadata["page_count"] == 9
    assert result.metadata["pdf_group_count"] == 2
    assert result.metadata["recognition_mode"] == "ocr"
    assert result.metadata["ocr_engine"] == "rapidocr"
    assert result.metadata["ocr_engine_version"] == "3.9.test"
    assert result.metadata["image_count"] == 9
    assert result.metadata["retained_line_count"] == 9
    assert result.metadata["provider_call_count"] == 0
    assert result.metadata["current_run_provider_call_count"] == 0
    assert result.metadata["network_call_count"] == 0


def test_memory_only_pdf_snapshot_exit_preserves_settled_cleanup_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_pdfium(monkeypatch, page_count=1)
    source = _write_pdf_placeholder(tmp_path / "book.pdf")
    source_bytes = source.read_bytes()
    cleanup_error = OutputError(
        "test-only PDF snapshot exit failure",
        code="OUTPUT_WRITE_FAILED",
        retryable=True,
    )
    snapshot_root = tmp_path / "request-snapshot"

    class StructuredProvider(_RecordingProvider):
        def recognize_images(self, image_paths, *, prompt: str, config: Config):
            super().recognize_images(image_paths, prompt=prompt, config=config)
            return VisionProviderResponse(
                markdown="# Paid PDF group\n",
                input_tokens=31,
                output_tokens=7,
                client_closed=False,
            )

    @contextmanager
    def fail_after_snapshot_exit(source_path, *, temp_dir):
        snapshot_root.mkdir()
        snapshot_path = snapshot_root / "source.pdf"
        snapshot_path.write_bytes(source_bytes)
        try:
            yield SimpleNamespace(
                path=snapshot_path,
                root=snapshot_root,
                byte_size=len(source_bytes),
            )
        finally:
            snapshot_path.unlink()
            (snapshot_root / "rendered-pages").rmdir()
            snapshot_root.rmdir()
            raise cleanup_error

    processor = importlib.import_module("ocrllm.processors.recognize_pdf")
    monkeypatch.setattr(processor, "snapshot_pdf", fail_after_snapshot_exit)
    provider = StructuredProvider()

    with pytest.raises(OutputError) as captured:
        recognize(
            source,
            config=Config(
                provider=provider,
                vision_model=VisionModelSettings(name="model-a"),
                execution=RecognitionExecutionPolicy(max_parallel_requests=4),
            ),
        )

    assert captured.value is cleanup_error
    assert type(captured.value) is OutputError
    assert captured.value.code == "OUTPUT_WRITE_FAILED"
    assert captured.value.retryable is True
    assert len(provider.calls) == 1
    assert captured.value.details["provider_calls_attempted"] == 1
    assert captured.value.details["settled_pdf_group_count"] == 1
    assert [
        dict(usage) for usage in captured.value.details["settled_model_usage"]
    ] == [
        {
            "model": "model-a",
            "input_count": 31,
            "output_count": 7,
            "unit": "tokens",
        }
    ]
    assert captured.value.details["provider_client_closed"] is False
    assert source.read_bytes() == source_bytes
    assert set(tmp_path.iterdir()) == {source}


def test_existing_pdf_output_rejects_before_snapshot_or_backend_inspection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _write_pdf_placeholder(tmp_path / "book.pdf")
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    target = output_dir / "book_board.md"
    target.write_text("original", encoding="utf-8")
    provider = _RecordingProvider()
    processor = importlib.import_module("ocrllm.processors.recognize_pdf")
    calls = {"snapshot": 0, "inspect": 0}

    @contextmanager
    def counted_snapshot(*_args, **_kwargs):
        calls["snapshot"] += 1
        yield SimpleNamespace(path=source, root=tmp_path / "snapshot")

    def counted_inspect(_path):
        calls["inspect"] += 1
        return ((72.0, 72.0),)

    monkeypatch.setattr(processor, "snapshot_pdf", counted_snapshot)
    monkeypatch.setattr(processor, "inspect_pdf", counted_inspect)

    with pytest.raises(OutputError) as captured:
        recognize(
            source,
            config=_pdf_config(provider, output_dir=output_dir),
        )

    assert captured.value.code == "OUTPUT_EXISTS"
    assert calls == {"snapshot": 0, "inspect": 0}
    assert provider.calls == []
    assert target.read_text(encoding="utf-8") == "original"


@pytest.mark.parametrize(
    ("provider", "expected_code"),
    (
        (None, "CONFIG_MISSING"),
        (object(), "CONFIG_INVALID"),
    ),
)
def test_pdf_preflights_invalid_provider_before_output_or_backend_work(
    tmp_path: Path,
    monkeypatch,
    provider,
    expected_code: str,
) -> None:
    _install_fake_pdfium(monkeypatch, page_count=1)
    source = _write_pdf_placeholder(tmp_path / "book.pdf")
    output_dir = tmp_path / "output"
    temp_dir = tmp_path / "temp"
    processor = importlib.import_module("ocrllm.processors.recognize_pdf")
    inspect_calls = 0
    inspect_pdf = processor.inspect_pdf

    def count_inspection(snapshot_path):
        nonlocal inspect_calls
        inspect_calls += 1
        return inspect_pdf(snapshot_path)

    monkeypatch.setattr(processor, "inspect_pdf", count_inspection)

    with pytest.raises(ConfigError) as captured:
        recognize(
            source,
            config=Config(
                provider=provider,
                output_dir=output_dir,
                temp_dir=temp_dir,
            ),
        )

    assert captured.value.code == expected_code
    assert captured.value.details["workflow_pass"] == "draft"
    assert captured.value.details["provider_calls_attempted"] == 0
    assert [dict(attempt) for attempt in captured.value.details["model_attempts"]] == [
        {
            "model": None,
            "outcome": expected_code,
            "disposition": "fix_request",
            "provider_calls_attempted": 0,
        }
    ]
    assert inspect_calls == 0
    assert not output_dir.exists()
    assert not temp_dir.exists()


def test_public_pdf_provider_receives_all_four_page_corners(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from PIL import Image

    class CornerMarkedBitmap:
        def to_pil(self):
            image = Image.new("RGB", (40, 30), "black")
            image.paste((255, 0, 0), (0, 0, 8, 8))
            image.paste((0, 255, 0), (32, 0, 40, 8))
            image.paste((0, 0, 255), (0, 22, 8, 30))
            image.paste((255, 255, 0), (32, 22, 40, 30))
            return image

        def close(self) -> None:
            pass

    class CornerMarkedPage:
        def render(self, *, scale: float):
            assert scale > 0
            return CornerMarkedBitmap()

        def close(self) -> None:
            pass

    class CornerMarkedDocument:
        def __len__(self) -> int:
            return 1

        def get_page_size(self, page_index: int) -> tuple[float, float]:
            assert page_index == 0
            return 40.0, 30.0

        def get_page(self, page_index: int) -> CornerMarkedPage:
            assert page_index == 0
            return CornerMarkedPage()

        def close(self) -> None:
            pass

    class CornerCheckingProvider:
        resume_identity = "offline-pdf-four-corners-v1"

        def recognize_images(self, image_paths, *, prompt: str, config: Config) -> str:
            assert "input order" in prompt
            paths = tuple(Path(path) for path in image_paths)
            assert len(paths) == 1
            with Image.open(paths[0]) as rendered:
                assert rendered.size == (40, 30)
                assert rendered.getpixel((3, 3)) == (255, 0, 0)
                assert rendered.getpixel((36, 3)) == (0, 255, 0)
                assert rendered.getpixel((3, 26)) == (0, 0, 255)
                assert rendered.getpixel((36, 26)) == (255, 255, 0)
            return "Complete page."

    monkeypatch.setitem(
        sys.modules,
        "pypdfium2",
        SimpleNamespace(
            PYPDFIUM_INFO=SimpleNamespace(api_tag=(5, 11, 0), beta=None),
            PdfDocument=lambda _path: CornerMarkedDocument(),
        ),
    )
    source = _write_pdf_placeholder(tmp_path / "four-corners.pdf")

    result = recognize(source, config=_pdf_config(CornerCheckingProvider()))

    assert result.status == "complete"


def test_pdf_group_combination_preserves_partial_image_status() -> None:
    warning = "The Google GenAI client could not be closed after recognition."
    combined = combine_pdf_group_results(
        (
            RecognitionResult(
                markdown="first",
                source_type="image",
                status="partial",
                warnings=(warning,),
            ),
            RecognitionResult(
                markdown="second",
                source_type="image",
            ),
        ),
        ((1, 8), (9, 16)),
        profile="board",
    )

    assert combined.status == "partial"
    assert combined.warnings == (warning,)


def test_public_pdf_resumes_mixed_partial_and_complete_google_image_groups(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _install_fake_pdfium(monkeypatch, page_count=16)
    source = _write_pdf_placeholder(tmp_path / "book.pdf")
    output_dir = tmp_path / "output"
    state_directory = output_dir / "book_board"
    observed: list[tuple[Path, ...]] = []
    adapter = importlib.import_module("ocrllm.providers.google_genai.recognize_images")

    def fake_google_image(image_paths, *, prompt, config):
        assert "input order" in prompt
        observed.append(tuple(Path(path) for path in image_paths))
        call_index = len(observed)
        return VisionProviderResponse(
            markdown=f"Google PDF group {call_index}.\n",
            input_tokens=11,
            output_tokens=3,
            client_closed=call_index != 1,
        )

    monkeypatch.setattr(adapter, "recognize_images", fake_google_image)

    def config(*, resume: bool = False) -> Config:
        return Config(
            provider=GoogleGenAISettings(api_key="test-only-google-key"),
            vision_model=VisionModelSettings(name="test-image-model"),
            output_dir=output_dir,
            resume=resume,
            temp_dir=tmp_path / "snapshots",
            execution=RecognitionExecutionPolicy(max_parallel_requests=4),
        )

    result = recognize(source, config=config())

    assert [len(call) for call in observed] == [8, 8]
    assert tuple(path.name for path in observed[0]) == tuple(
        f"page-{page_number:06d}.png" for page_number in range(1, 9)
    )
    assert tuple(path.name for path in observed[1]) == tuple(
        f"page-{page_number:06d}.png" for page_number in range(9, 17)
    )
    assert all(not path.exists() for call in observed for path in call)
    assert result.status == "partial"
    assert result.warnings == (
        "The Google GenAI client could not be closed after recognition.",
    )
    assert result.output_path == output_dir / "book_board.md"
    assert result.output_path.read_text(encoding="utf-8") == result.markdown
    assert result.markdown.index("Google PDF group 1.") < result.markdown.index(
        "Google PDF group 2."
    )
    assert result.metadata["current_run_provider_call_count"] == 2
    assert result.metadata["current_model_token_usage"] == (
        {
            "model": "test-image-model",
            "input_tokens": 22,
            "output_tokens": 6,
        },
    )

    state_paths = sorted(state_directory.glob("*.ocrllm-state.json"))
    assert len(state_paths) == 2
    states = [json.loads(path.read_text(encoding="utf-8")) for path in state_paths]
    assert [state["result"]["status"] for state in states] == [
        "partial",
        "complete",
    ]
    assert states[0]["result"]["warnings"] == [
        "The Google GenAI client could not be closed after recognition."
    ]
    assert states[0]["result"]["metadata"]["provider_client_closed"] is False
    assert states[1]["result"]["metadata"]["provider_client_closed"] is True

    resumed = recognize(source, config=config(resume=True))

    assert len(observed) == 2
    assert resumed.status == "partial"
    assert resumed.warnings == result.warnings
    assert resumed.markdown == result.markdown
    assert resumed.output_path == result.output_path
    assert resumed.metadata["current_run_provider_call_count"] == 0
    assert "current_model_token_usage" not in resumed.metadata
    assert resumed.output_path.read_text(encoding="utf-8") == resumed.markdown


@pytest.mark.skipif(sys.platform != "win32", reason="Windows junction regression")
def test_pdf_rejects_junction_state_directory_before_provider_dispatch(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _install_fake_pdfium(monkeypatch, page_count=1)
    source = _write_pdf_placeholder(tmp_path / "book.pdf")
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    outside_target = tmp_path / "outside"
    outside_target.mkdir()
    state_directory = output_dir / "book_board"
    created = subprocess.run(
        [
            "cmd.exe",
            "/d",
            "/c",
            "mklink",
            "/J",
            str(state_directory),
            str(outside_target),
        ],
        capture_output=True,
        check=False,
        text=True,
    )
    if created.returncode != 0:
        pytest.skip("This Windows test environment cannot create a junction")
    provider = _RecordingProvider()

    try:
        with pytest.raises(OutputError) as captured:
            recognize(
                source,
                config=_pdf_config(
                    provider,
                    output_dir=output_dir,
                    overwrite=True,
                ),
            )

        assert captured.value.code == "OUTPUT_PATH_INVALID"
        assert provider.calls == []
        assert not (output_dir / "book_board.md").exists()
        assert list(outside_target.iterdir()) == []
    finally:
        if os.path.lexists(state_directory):
            os.rmdir(state_directory)


def test_pdf_overwrite_accepts_existing_ordinary_state_directory(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _install_fake_pdfium(monkeypatch, page_count=1)
    source = _write_pdf_placeholder(tmp_path / "book.pdf")
    output_dir = tmp_path / "output"
    state_directory = output_dir / "book_board"
    state_directory.mkdir(parents=True)
    provider = _RecordingProvider(state_directory=state_directory)

    result = recognize(
        source,
        config=_pdf_config(
            provider,
            output_dir=output_dir,
            overwrite=True,
        ),
    )

    assert len(provider.calls) == 1
    assert result.output_path == output_dir / "book_board.md"
    assert list(state_directory.glob("*.ocrllm-state.json"))


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
    assert interrupted.value.details["settled_pdf_group_count"] == 0
    assert not (output_dir / "book_board.md").exists()
    state_directory = output_dir / "book_board"
    state_paths = tuple(state_directory.glob("*.ocrllm-state.json"))
    assert len(state_paths) == 1
    assert not tuple(state_directory.glob("*.md"))
    partial_result = json.loads(
        state_paths[0].read_text(encoding="utf-8")
    )["result"]
    assert partial_result["markdown"] == ""
    assert partial_result["status"] == "partial"

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


def test_cancel_after_final_pdf_group_blocks_parent_publication_and_resumes(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _install_fake_pdfium(monkeypatch, page_count=1)
    source = _write_pdf_placeholder(tmp_path / "book.pdf")
    output_dir = tmp_path / "output"
    state_directory = output_dir / "book_board"
    cancellation = threading.Event()
    provider = _RecordingProvider()
    processor = importlib.import_module("ocrllm.processors.recognize_pdf")
    snapshot_pdf = processor.snapshot_pdf

    @contextmanager
    def cancel_after_snapshot_exit(*args, **kwargs):
        with snapshot_pdf(*args, **kwargs) as snapshot:
            yield snapshot
        cancellation.set()

    monkeypatch.setattr(processor, "snapshot_pdf", cancel_after_snapshot_exit)

    with pytest.raises(Cancelled) as interrupted:
        recognize(
            source,
            config=_pdf_config(
                provider,
                output_dir=output_dir,
                cancellation=cancellation,
            ),
        )

    assert len(provider.calls) == 1
    assert interrupted.value.details["provider_calls_attempted"] == 1
    assert not (output_dir / "book_board.md").exists()
    assert len(tuple(state_directory.glob("*.ocrllm-state.json"))) == 1
    assert len(tuple(state_directory.glob("*.md"))) == 1

    monkeypatch.setattr(processor, "snapshot_pdf", snapshot_pdf)
    cancellation.clear()
    resumed = recognize(
        source,
        config=_pdf_config(
            provider,
            output_dir=output_dir,
            resume=True,
            cancellation=cancellation,
        ),
    )

    assert len(provider.calls) == 1
    assert resumed.status == "complete"
    assert resumed.metadata["current_run_provider_call_count"] == 0
    assert resumed.output_path == output_dir / "book_board.md"
    assert resumed.output_path.read_text(encoding="utf-8") == resumed.markdown


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


def test_first_pdf_group_publication_failure_resumes_without_replay(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _install_fake_pdfium(monkeypatch, page_count=8)
    source = _write_pdf_placeholder(tmp_path / "book.pdf")
    output_dir = tmp_path / "output"
    state_directory = output_dir / "book_board"
    provider = _RecordingProvider()
    writer = importlib.import_module(
        "ocrllm.output.write_markdown_atomically"
    )
    write_markdown_atomically = writer.write_markdown_atomically

    def fail_child_publication(*_args, **_kwargs):
        raise OutputError("test-only child publication failure")

    monkeypatch.setattr(
        writer,
        "write_markdown_atomically",
        fail_child_publication,
    )

    with pytest.raises(OutputError) as captured:
        recognize(
            source,
            config=_pdf_config(provider, output_dir=output_dir),
        )

    assert captured.value.code == "OUTPUT_WRITE_FAILED"
    assert captured.value.details["provider_calls_attempted"] == 1
    assert captured.value.details["settled_pdf_group_count"] == 0
    assert "pdf_state_cleanup_failed" not in captured.value.details
    assert provider.calls == [
        tuple(f"page-{page_number:06d}.png" for page_number in range(1, 9))
    ]
    assert len(tuple(state_directory.glob("*.ocrllm-state.json"))) == 1
    assert not tuple(state_directory.glob("*.md"))
    assert not (output_dir / "book_board.md").exists()

    monkeypatch.setattr(
        writer,
        "write_markdown_atomically",
        write_markdown_atomically,
    )
    resumed = recognize(
        source,
        config=_pdf_config(provider, output_dir=output_dir, resume=True),
    )

    assert len(provider.calls) == 1
    assert resumed.status == "complete"
    assert resumed.metadata["current_run_provider_call_count"] == 0
    assert resumed.metadata["pdf_group_count"] == 1
    assert resumed.output_path == output_dir / "book_board.md"
    assert resumed.output_path.read_text(encoding="utf-8") == resumed.markdown
    assert len(tuple(state_directory.glob("*.ocrllm-state.json"))) == 1
    assert len(tuple(state_directory.glob("*.md"))) == 1


def test_pdf_child_publication_failure_reports_saved_token_usage(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _install_fake_pdfium(monkeypatch, page_count=1)
    source = _write_pdf_placeholder(tmp_path / "book.pdf")
    output_dir = tmp_path / "output"
    state_directory = output_dir / "book_board"
    observed: list[tuple[Path, ...]] = []
    adapter = importlib.import_module(
        "ocrllm.providers.google_genai.recognize_images"
    )

    def fake_google_image(image_paths, *, prompt, config):
        assert "input order" in prompt
        observed.append(tuple(Path(path) for path in image_paths))
        return VisionProviderResponse(
            markdown="Google PDF group.\n",
            input_tokens=17,
            output_tokens=4,
        )

    monkeypatch.setattr(adapter, "recognize_images", fake_google_image)
    writer = importlib.import_module("ocrllm.output.write_markdown_atomically")

    def fail_child_publication(*_args, **_kwargs):
        raise OutputError("test-only child publication failure")

    monkeypatch.setattr(
        writer,
        "write_markdown_atomically",
        fail_child_publication,
    )

    with pytest.raises(OutputError) as captured:
        recognize(
            source,
            config=Config(
                provider=GoogleGenAISettings(api_key="test-only-google-key"),
                vision_model=VisionModelSettings(name="test-image-model"),
                output_dir=output_dir,
                temp_dir=tmp_path / "snapshots",
            ),
        )

    assert captured.value.code == "OUTPUT_WRITE_FAILED"
    assert captured.value.details["provider_calls_attempted"] == 1
    assert captured.value.details["settled_pdf_group_count"] == 0
    assert captured.value.details["settled_model_usage"] == (
        {
            "model": "test-image-model",
            "input_count": 17,
            "output_count": 4,
            "unit": "tokens",
        },
    )
    assert len(observed) == 1
    state_paths = tuple(state_directory.glob("*.ocrllm-state.json"))
    assert len(state_paths) == 1
    state = json.loads(state_paths[0].read_text(encoding="utf-8"))
    assert state["result"]["metadata"]["current_model_token_usage"] == [
        {
            "model": "test-image-model",
            "input_tokens": 17,
            "output_tokens": 4,
        }
    ]
    assert not tuple(state_directory.glob("*.md"))
    assert not (output_dir / "book_board.md").exists()


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
