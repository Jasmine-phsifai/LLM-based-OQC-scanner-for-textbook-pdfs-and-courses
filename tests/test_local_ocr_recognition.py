from __future__ import annotations

import importlib
import threading
from collections.abc import Sequence
from pathlib import Path

import pytest

from ocrllm import Config, LocalOCRSettings, recognize
from ocrllm.errors import (
    Cancelled,
    DependencyMissing,
    NoTextDetected,
    OCRBackendError,
)
from ocrllm.local_ocr.parse_rapidocr_result import parse_rapidocr_result
from write_test_image import write_test_image


class FakeRapidOCRResult:
    def __init__(self, texts, scores) -> None:
        self.txts = texts
        self.scores = scores


class HostileSequence(Sequence):
    def __len__(self):
        raise RuntimeError("secret-hostile-sequence-sentinel")

    def __getitem__(self, index):
        raise RuntimeError("secret-hostile-sequence-sentinel")


class RecordingRapidOCREngine:
    def __init__(self, results, *, cancellation=None) -> None:
        self.results = list(results)
        self.cancellation = cancellation
        self.calls: list[Path] = []
        self.snapshot_bytes: list[bytes] = []

    def __call__(self, path: Path):
        self.calls.append(path)
        self.snapshot_bytes.append(path.read_bytes())
        if self.cancellation is not None:
            self.cancellation.set()
        return self.results[len(self.calls) - 1]


def _install_fake_engine(monkeypatch, results, *, cancellation=None):
    module = importlib.import_module(
        "ocrllm.local_ocr.recognize_images_with_rapidocr"
    )
    engine = RecordingRapidOCREngine(results, cancellation=cancellation)
    constructor_calls: list[dict[str, object]] = []

    def factory(**kwargs):
        constructor_calls.append(kwargs)
        return engine

    monkeypatch.setattr(module, "load_rapidocr", lambda: factory)
    monkeypatch.setattr(module, "resolve_rapidocr_version", lambda: "3.9.test")
    return engine, constructor_calls


def test_public_recognize_uses_one_local_engine_and_no_provider(tmp_path, monkeypatch) -> None:
    source = write_test_image(tmp_path / "课程 board.png")
    engine, constructor_calls = _install_fake_engine(
        monkeypatch,
        [FakeRapidOCRResult(("First line", "第二行 +"), (0.91, 0.82))],
    )

    result = recognize(source, config=Config(image_mode="ocr"))

    assert result.markdown == "First line\n\n第二行 +"
    assert result.source_type == "image"
    assert result.profile == "board"
    assert result.status == "complete"
    assert result.output_path is None
    assert result.metadata == {
        "recognition_mode": "ocr",
        "ocr_engine": "rapidocr",
        "ocr_engine_version": "3.9.test",
        "image_count": 1,
        "detected_line_count": 2,
        "retained_line_count": 2,
        "empty_image_count": 0,
        "minimum_confidence": 0.5,
        "mean_confidence": pytest.approx(0.865),
        "provider_call_count": 0,
        "current_run_provider_call_count": 0,
        "network_call_count": 0,
    }
    assert len(result.warnings) == 1
    assert "does not reconstruct" in result.warnings[0]
    assert constructor_calls == [
        {
            "params": {
                "Global.log_level": "critical",
                "Global.text_score": 0.5,
            }
        }
    ]
    assert len(engine.calls) == 1
    assert engine.calls[0].name == source.name
    assert engine.snapshot_bytes == [source.read_bytes()]
    assert not engine.calls[0].exists()


def test_ordered_multi_image_ocr_filters_confidence_and_marks_boundaries(
    tmp_path,
    monkeypatch,
) -> None:
    first = write_test_image(tmp_path / "first.png", color=(1, 2, 3))
    second = write_test_image(tmp_path / "second.jpg", color=(4, 5, 6))
    engine, _ = _install_fake_engine(
        monkeypatch,
        [
            FakeRapidOCRResult(("drop", "Keep first"), (0.69, 0.70)),
            FakeRapidOCRResult(("Keep second",), (0.99,)),
        ],
    )
    config = Config(
        image_mode="ocr",
        local_ocr=LocalOCRSettings(minimum_confidence=0.70),
    )

    result = recognize((first, second), config=config)

    assert result.markdown == (
        "## Image 1\n\nKeep first\n\n## Image 2\n\nKeep second"
    )
    assert [path.name for path in engine.calls] == [first.name, second.name]
    assert result.metadata["image_count"] == 2
    assert result.metadata["detected_line_count"] == 3
    assert result.metadata["retained_line_count"] == 2
    assert result.metadata["minimum_confidence"] == 0.70
    assert all(not path.exists() for path in engine.calls)


def test_local_ocr_writes_only_final_markdown_atomically(tmp_path, monkeypatch) -> None:
    source = write_test_image(tmp_path / "board.jpeg")
    _install_fake_engine(
        monkeypatch,
        [FakeRapidOCRResult(("Offline OCR",), (0.9,))],
    )

    result = recognize(
        source,
        config=Config(image_mode="ocr", output_dir=tmp_path / "output"),
    )

    assert result.output_path == tmp_path / "output" / "board_board.md"
    assert result.output_path.read_text(encoding="utf-8") == "Offline OCR"
    assert {path.name for path in result.output_path.parent.iterdir()} == {
        result.output_path.name,
        "board_board.ocrllm-state.json",
    }


def test_missing_local_ocr_dependency_is_typed_and_writes_nothing(
    tmp_path,
    monkeypatch,
) -> None:
    source = write_test_image(tmp_path / "board.png")
    output_dir = tmp_path / "output"
    module = importlib.import_module(
        "ocrllm.local_ocr.recognize_images_with_rapidocr"
    )

    def missing_dependency():
        raise DependencyMissing(
            "Local OCR requires the optional 'ocr' dependencies.",
            details={"extra": "ocr", "engine": "rapidocr"},
        )

    monkeypatch.setattr(module, "load_rapidocr", missing_dependency)

    with pytest.raises(DependencyMissing) as caught:
        recognize(
            source,
            config=Config(image_mode="ocr", output_dir=output_dir),
        )

    assert caught.value.code == "DEPENDENCY_MISSING"
    assert caught.value.details["extra"] == "ocr"
    assert output_dir.is_dir()
    assert tuple(output_dir.iterdir()) == ()


def test_local_ocr_initialization_failure_is_typed_and_secret_safe(
    tmp_path,
    monkeypatch,
) -> None:
    source = write_test_image(tmp_path / "board.png")
    module = importlib.import_module(
        "ocrllm.local_ocr.recognize_images_with_rapidocr"
    )

    def factory(**kwargs):
        raise RuntimeError("secret-initialization-sentinel")

    monkeypatch.setattr(module, "load_rapidocr", lambda: factory)

    with pytest.raises(OCRBackendError) as caught:
        recognize(source, config=Config(image_mode="ocr"))

    assert caught.value.code == "OCR_BACKEND_FAILED"
    assert caught.value.details == {
        "engine": "rapidocr",
        "phase": "initialization",
    }
    assert "secret-initialization-sentinel" not in repr(caught.value)


def test_local_ocr_rejects_noncallable_initialized_engine(
    tmp_path,
    monkeypatch,
) -> None:
    source = write_test_image(tmp_path / "board.png")
    module = importlib.import_module(
        "ocrllm.local_ocr.recognize_images_with_rapidocr"
    )
    monkeypatch.setattr(module, "load_rapidocr", lambda: lambda **_: object())

    with pytest.raises(OCRBackendError) as caught:
        recognize(source, config=Config(image_mode="ocr"))

    assert caught.value.code == "OCR_BACKEND_FAILED"
    assert caught.value.details["phase"] == "initialization"


def test_local_ocr_inference_failure_reports_image_index_without_secret(
    tmp_path,
    monkeypatch,
) -> None:
    source = write_test_image(tmp_path / "board.png")
    module = importlib.import_module(
        "ocrllm.local_ocr.recognize_images_with_rapidocr"
    )

    class FailingEngine:
        def __call__(self, path):
            raise RuntimeError("secret-inference-sentinel")

    monkeypatch.setattr(module, "load_rapidocr", lambda: lambda **_: FailingEngine())

    with pytest.raises(OCRBackendError) as caught:
        recognize(source, config=Config(image_mode="ocr"))

    assert caught.value.code == "OCR_BACKEND_FAILED"
    assert caught.value.details["phase"] == "inference"
    assert caught.value.details["image_index"] == 0
    assert "secret-inference-sentinel" not in repr(caught.value)


@pytest.mark.parametrize(
    "result",
    [
        object(),
        FakeRapidOCRResult(("text",), ()),
        FakeRapidOCRResult(("text",), (float("nan"),)),
        FakeRapidOCRResult(("text",), (1.1,)),
        FakeRapidOCRResult((object(),), (0.9,)),
        FakeRapidOCRResult(("text",), (object(),)),
        FakeRapidOCRResult(HostileSequence(), HostileSequence()),
    ],
)
def test_rapidocr_parser_rejects_malformed_backend_results(result) -> None:
    with pytest.raises(OCRBackendError) as caught:
        parse_rapidocr_result(result, minimum_confidence=0.5)

    assert caught.value.code == "OCR_RESULT_INVALID"
    assert caught.value.details == {"engine": "rapidocr"}


def test_local_ocr_no_retained_text_is_distinct_typed_error(
    tmp_path,
    monkeypatch,
) -> None:
    source = write_test_image(tmp_path / "blank.png")
    _install_fake_engine(
        monkeypatch,
        [FakeRapidOCRResult(("low confidence", "..."), (0.49, 0.99))],
    )

    with pytest.raises(NoTextDetected) as caught:
        recognize(source, config=Config(image_mode="ocr"))

    assert caught.value.code == "OCR_NO_TEXT"
    assert caught.value.retryable is False
    assert caught.value.details["image_count"] == 1
    assert caught.value.details["minimum_confidence"] == 0.5


def test_local_ocr_honors_cancellation_between_ordered_images(
    tmp_path,
    monkeypatch,
) -> None:
    first = write_test_image(tmp_path / "first.png")
    second = write_test_image(tmp_path / "second.png")
    cancellation = threading.Event()
    engine, _ = _install_fake_engine(
        monkeypatch,
        [FakeRapidOCRResult(("first",), (0.9,))],
        cancellation=cancellation,
    )

    with pytest.raises(Cancelled) as caught:
        recognize(
            (first, second),
            config=Config(image_mode="ocr", cancellation=cancellation),
        )

    assert len(engine.calls) == 1
    assert not engine.calls[0].exists()
    assert caught.value.details["provider_calls_attempted"] == 0
