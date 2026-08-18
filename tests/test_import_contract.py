from ocrllm import Config, RecognitionResult, recognize, recognize_batch
from ocrllm.errors import ConfigError, UnsupportedFormat

from write_test_image import write_test_image


class FakeProvider:
    def recognize_images(self, image_paths, *, prompt, config):
        names = ", ".join(path.name for path in image_paths)
        return f"# Board\n\nImages: {names}\n"


def test_import_contract_recognizes_board_without_writing(tmp_path):
    source = write_test_image(tmp_path / "board.png")

    result = recognize(source, config=Config(provider=FakeProvider()))

    assert isinstance(result, RecognitionResult)
    assert result.source_type == "image"
    assert result.profile == "board"
    assert result.status == "complete"
    assert result.output_path is None
    assert "board.png" in result.markdown


def test_import_contract_writes_when_output_dir_is_set(tmp_path):
    source = write_test_image(tmp_path / "board.jpg")
    out_dir = tmp_path / "out"

    result = recognize(source, config=Config(provider=FakeProvider(), output_dir=out_dir))

    assert result.output_path == out_dir / "board_board.md"
    assert result.output_path.read_text(encoding="utf-8") == result.markdown


def test_batch_returns_one_outcome_per_source(tmp_path):
    first = write_test_image(tmp_path / "a.png", color=(255, 0, 0))
    second = write_test_image(tmp_path / "b.jpeg", color=(0, 255, 0))

    outcomes = recognize_batch([first, second], config=Config(provider=FakeProvider()))
    results = [outcome.result for outcome in outcomes]

    assert [outcome.index for outcome in outcomes] == [0, 1]
    assert all(outcome.succeeded for outcome in outcomes)
    assert [result.source_type for result in results] == ["image", "image"]
    assert [result.profile for result in results] == ["board", "board"]
    assert [result.markdown.split("Images: ", 1)[1].strip() for result in results] == [
        "a.png",
        "b.jpeg",
    ]


def test_provider_is_required_for_board(tmp_path):
    source = write_test_image(tmp_path / "board.png")

    try:
        recognize(source)
    except ConfigError as exc:
        assert "Config.provider" in str(exc)
    else:
        raise AssertionError("ConfigError was not raised")


def test_unsupported_extension_is_explicit(tmp_path):
    source = tmp_path / "lecture.pdf"
    source.write_bytes(b"fake")

    try:
        recognize(source, config=Config(provider=FakeProvider()))
    except UnsupportedFormat as exc:
        assert exc.code == "UNSUPPORTED_FORMAT"
        assert exc.details["extension"] == ".pdf"
    else:
        raise AssertionError("UnsupportedFormat was not raised")
