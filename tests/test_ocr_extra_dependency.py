"""Packaging contract for the maintained local-OCR backend."""

from pathlib import Path


def test_ocr_extra_bounds_the_proven_backend_dependencies() -> None:
    configuration = (Path(__file__).parents[1] / "pyproject.toml").read_text(
        encoding="utf-8"
    )
    ocr_section = configuration.split("ocr = [", maxsplit=1)[1].split(
        "]", maxsplit=1
    )[0]
    requirements = [
        line.strip().rstrip(",").strip('"')
        for line in ocr_section.splitlines()
        if line.strip()
    ]

    assert requirements == [
        "Pillow>=10.4,<13",
        "rapidocr>=3.9,<4",
        "onnxruntime>=1.23,<2",
        "opencv-python>=4.13,<4.14",
        "omegaconf>=2.2.2,<3",
    ]
