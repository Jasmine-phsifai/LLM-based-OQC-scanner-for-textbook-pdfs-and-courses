"""Runtime type-hint contract for exported public classes."""

from __future__ import annotations

import subprocess
import sys
import typing
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    ("public_name", "field_name", "type_module", "type_name"),
    (
        (
            "Config",
            "provider",
            "ocrllm.providers.vision_provider",
            "VisionProvider",
        ),
        (
            "BatchItemOutcome",
            "result",
            "ocrllm.result",
            "RecognitionResult",
        ),
        (
            "DashScopeSettings",
            "credential_pool",
            "ocrllm.providers.dashscope.credential_pool",
            "DashScopeCredentialPool",
        ),
    ),
)
def test_exported_public_class_resolves_runtime_type_hint(
    public_name: str,
    field_name: str,
    type_module: str,
    type_name: str,
) -> None:
    package = __import__("ocrllm", fromlist=[public_name])
    expected_module = __import__(type_module, fromlist=[type_name])
    public_class = getattr(package, public_name)
    expected_type = getattr(expected_module, type_name)

    hints = typing.get_type_hints(public_class)

    assert expected_type in typing.get_args(hints[field_name])


def test_dashscope_factory_resolves_credential_pool_type_hint() -> None:
    from ocrllm import DashScopeCredentialPool, DashScopeSettings

    hints = typing.get_type_hints(DashScopeSettings.for_region)

    assert DashScopeCredentialPool in typing.get_args(hints["credential_pool"])
    assert hints["return"] is DashScopeSettings


def test_public_class_type_hints_keep_optional_backends_unloaded() -> None:
    source_root = Path(__file__).resolve().parents[1] / "src"
    probe = (
        "import sys, typing; "
        "sys.path.insert(0, sys.argv[1]); "
        "from ocrllm import BatchItemOutcome, Config, DashScopeSettings; "
        "typing.get_type_hints(Config); "
        "typing.get_type_hints(BatchItemOutcome); "
        "typing.get_type_hints(DashScopeSettings); "
        "typing.get_type_hints(DashScopeSettings.for_region); "
        "loaded={name.split('.')[0] for name in sys.modules}; "
        "forbidden={'PIL','pypdfium2','openai','google','httpx','rapidocr',"
        "'onnxruntime','cv2','numpy','miniaudio','_miniaudio','legacy_app'}; "
        "assert not loaded & forbidden, loaded & forbidden"
    )

    completed = subprocess.run(
        [sys.executable, "-I", "-c", probe, str(source_root)],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 0, completed.stderr
