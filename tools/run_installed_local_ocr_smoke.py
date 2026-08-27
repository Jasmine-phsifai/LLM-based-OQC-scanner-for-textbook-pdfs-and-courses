"""Run one real, network-blocked OCR call from an installed package."""

from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import importlib.metadata as metadata
from pathlib import Path
import sys

from PIL import Image, ImageDraw, ImageFont
import requests

from ocrllm import Config, recognize


def run_installed_local_ocr_smoke(image_path: Path) -> None:
    """Recognize generated text through real RapidOCR without network access."""

    image = Image.new("RGB", (900, 220), "white")
    drawing = ImageDraw.Draw(image)
    drawing.text(
        (40, 65),
        "OCRLLM 2026",
        fill="black",
        font=ImageFont.load_default(size=64),
    )
    image.save(image_path, format="PNG")

    def reject_network(*args: object, **kwargs: object) -> None:
        raise AssertionError("RapidOCR attempted a network request")

    original_request = requests.sessions.Session.request
    requests.sessions.Session.request = reject_network
    captured_stdout = StringIO()
    captured_stderr = StringIO()
    try:
        with redirect_stdout(captured_stdout), redirect_stderr(captured_stderr):
            result = recognize(image_path, config=Config(image_mode="ocr"))
    finally:
        requests.sessions.Session.request = original_request

    assert captured_stdout.getvalue() == ""
    assert captured_stderr.getvalue() == ""
    assert "OCRLLM" in result.markdown
    assert "2026" in result.markdown
    assert result.source_type == "image"
    assert result.profile == "board"
    assert result.status == "complete"
    assert result.metadata["recognition_mode"] == "ocr"
    assert result.metadata["ocr_engine"] == "rapidocr"
    assert result.metadata["ocr_engine_version"] == metadata.version("rapidocr")
    assert result.metadata["image_count"] == 1
    assert result.metadata["retained_line_count"] >= 1
    assert result.metadata["provider_call_count"] == 0
    assert result.metadata["current_run_provider_call_count"] == 0
    assert result.metadata["network_call_count"] == 0
    assert result.output_path is None
    print(
        metadata.version("rapidocr"),
        metadata.version("onnxruntime"),
        metadata.version("opencv-python"),
        metadata.version("numpy"),
        metadata.version("omegaconf"),
        result.metadata["retained_line_count"],
    )


def main(argv: list[str]) -> int:
    """Validate the one generated-image path supplied by the release gate."""

    if len(argv) != 2:
        raise SystemExit("usage: run_installed_local_ocr_smoke.py IMAGE_PATH")
    run_installed_local_ocr_smoke(Path(argv[1]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
