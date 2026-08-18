from __future__ import annotations

import builtins

import pytest

from ocrllm.errors import DependencyMissing, OCRBackendError
from ocrllm.local_ocr.load_rapidocr import load_rapidocr


def test_load_rapidocr_maps_missing_optional_dependency(monkeypatch) -> None:
    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name == "rapidocr":
            raise ImportError("secret-missing-dependency-sentinel")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)

    with pytest.raises(DependencyMissing) as caught:
        load_rapidocr()

    assert caught.value.code == "DEPENDENCY_MISSING"
    assert caught.value.details == {
        "extra": "ocr",
        "engine": "rapidocr",
        "required_distribution": "rapidocr>=3.9,<4",
        "incompatible_distribution": "rapidocr-onnxruntime",
    }
    assert "secret-missing-dependency-sentinel" not in repr(caught.value)


def test_load_rapidocr_maps_broken_backend_import(monkeypatch) -> None:
    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name == "rapidocr":
            raise RuntimeError("secret-broken-import-sentinel")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)

    with pytest.raises(OCRBackendError) as caught:
        load_rapidocr()

    assert caught.value.code == "OCR_BACKEND_FAILED"
    assert caught.value.details == {"engine": "rapidocr", "phase": "import"}
    assert "secret-broken-import-sentinel" not in repr(caught.value)
