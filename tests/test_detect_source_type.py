from pathlib import Path

import pytest

from ocrllm.detect_source_type import detect_source_type
from ocrllm.errors import InvalidSource, UnsupportedFormat
from ocrllm.validate_same_type_group import validate_same_type_group


@pytest.mark.parametrize("suffix", [".png", ".jpg", ".jpeg", ".PNG", ".JpG", ".JPEG"])
def test_detect_source_type_accepts_only_phase_zero_image_suffixes(suffix):
    assert detect_source_type(Path(f"does-not-need-to-exist{suffix}")) == "image"


@pytest.mark.parametrize("suffix", [".mp3", ".MP3", ".Mp3"])
def test_detect_source_type_accepts_stage_a1_mp3(suffix):
    assert detect_source_type(Path(f"does-not-need-to-exist{suffix}")) == "audio"


@pytest.mark.parametrize(
    "name",
    [
        "board.bmp",
        "board.webp",
        "board.heic",
        "board.heif",
        "board.tif",
        "board.tiff",
        "lecture.pdf",
        "no-extension",
    ],
)
def test_detect_source_type_rejects_unapproved_or_missing_suffixes(name):
    with pytest.raises(UnsupportedFormat) as raised:
        detect_source_type(name)

    assert raised.value.code == "UNSUPPORTED_FORMAT"


def test_validate_same_type_group_accepts_an_ordered_image_group():
    sources = (Path("third.jpeg"), Path("first.png"), Path("second.jpg"))

    assert validate_same_type_group(sources) == "image"
    assert sources == (Path("third.jpeg"), Path("first.png"), Path("second.jpg"))


def test_validate_same_type_group_accepts_one_mp3():
    assert validate_same_type_group((Path("lecture.mp3"),)) == "audio"


def test_validate_same_type_group_rejects_an_empty_group():
    with pytest.raises(InvalidSource) as raised:
        validate_same_type_group(())

    assert raised.value.code == "SOURCE_INVALID"


def test_validate_same_type_group_rejects_an_unsupported_member():
    with pytest.raises(UnsupportedFormat) as raised:
        validate_same_type_group((Path("board.png"), Path("lecture.pdf")))

    assert raised.value.code == "UNSUPPORTED_FORMAT"
