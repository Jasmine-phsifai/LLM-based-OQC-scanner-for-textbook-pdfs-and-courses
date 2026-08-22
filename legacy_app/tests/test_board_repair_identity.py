import json
import os
from pathlib import Path

import pytest
from PIL import Image

from OCRLLM.config import AppConfig
from OCRLLM.processors.board import BoardProcessor


class _BoardLLM:
    def __init__(self, contextual_responses=()):
        self.contextual_responses = iter(contextual_responses)
        self.repair_calls: list[list[str]] = []
        self.checkpoint_seen = False
        self.output_path: Path | None = None

    def chat_with_images_contextual(self, **_kwargs):
        if self.output_path is not None:
            sidecar = self.output_path.with_name(self.output_path.name + ".board-repair.json")
            self.checkpoint_seen = (
                sidecar.exists()
                and json.loads(sidecar.read_text(encoding="utf-8"))["schema"]
                == "ocrllm.board_repair_manifest"
            )
        response = next(self.contextual_responses)
        if isinstance(response, Exception):
            raise response
        return response

    def chat_with_images(self, *, image_paths, **_kwargs):
        self.repair_calls.append(list(image_paths))
        return "修复后的可靠内容"


def _make_png(path: Path, color: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (8, 8), color).save(path)


def _processor(tmp_path: Path, llm: _BoardLLM, *, batch_size=1) -> BoardProcessor:
    processor = BoardProcessor.__new__(BoardProcessor)
    processor.cfg = AppConfig().with_updates(
        paths={"output_dir": str(tmp_path), "temp_dir": str(tmp_path / "temp")},
        processing={"batch_size": batch_size},
    )
    processor.llm = llm
    processor._report = lambda *_args: None
    processor._check_cancelled = lambda: None
    processor._report_content = lambda *_args: None
    return processor


def _produce_failed_output(
    tmp_path: Path,
    image_paths: list[Path],
    *,
    responses,
    batch_size=1,
) -> tuple[BoardProcessor, _BoardLLM, Path]:
    llm = _BoardLLM(responses)
    processor = _processor(tmp_path, llm, batch_size=batch_size)
    output = tmp_path / "board.md"
    with pytest.raises(RuntimeError):
        processor.process(
            [str(path) for path in image_paths],
            output_path=str(output),
            skip_preprocess=True,
        )
    return processor, llm, output


def test_board_process_publishes_identity_before_provider_dispatch(tmp_path):
    image = tmp_path / "board.png"
    _make_png(image, "white")
    llm = _BoardLLM([RuntimeError("timeout")])
    processor = _processor(tmp_path, llm)
    output = tmp_path / "board.md"
    llm.output_path = output

    with pytest.raises(RuntimeError):
        processor.process([str(image)], output_path=str(output), skip_preprocess=True)

    assert llm.checkpoint_seen


def test_board_repair_resolves_comma_filename_after_rename_by_saved_identity(tmp_path):
    original = tmp_path / "chapter, part.png"
    _make_png(original, "white")
    processor, llm, output = _produce_failed_output(
        tmp_path,
        [original],
        responses=[RuntimeError("timeout")],
    )
    renamed = tmp_path / "renamed.png"
    original.rename(renamed)

    processor.repair([str(renamed)], str(output), skip_preprocess=True)

    assert llm.repair_calls == [[str(renamed)]]
    assert "修复后的可靠内容" in output.read_text(encoding="utf-8")


def test_board_repair_does_not_confuse_duplicate_basenames(tmp_path):
    first = tmp_path / "first" / "board.png"
    second = tmp_path / "second" / "board.png"
    _make_png(first, "white")
    _make_png(second, "black")
    os.utime(first, (1, 1))
    os.utime(second, (2, 2))
    processor, llm, output = _produce_failed_output(
        tmp_path,
        [first, second],
        responses=[RuntimeError("timeout"), "第二张成功"],
    )

    processor.repair([str(first), str(second)], str(output), skip_preprocess=True)

    assert llm.repair_calls == [[str(first)]]


def test_board_repair_rejects_source_byte_drift_before_provider_call(tmp_path):
    image = tmp_path / "board.png"
    _make_png(image, "white")
    processor, llm, output = _produce_failed_output(
        tmp_path,
        [image],
        responses=[RuntimeError("timeout")],
    )
    _make_png(image, "black")

    with pytest.raises(Exception, match="指纹|identity|身份"):
        processor.repair([str(image)], str(output), skip_preprocess=True)

    assert llm.repair_calls == []


def test_board_repair_rejects_markdown_unit_drift_before_provider_call(tmp_path):
    image = tmp_path / "board.png"
    _make_png(image, "white")
    processor, llm, output = _produce_failed_output(
        tmp_path,
        [image],
        responses=[RuntimeError("timeout")],
    )
    content = output.read_text(encoding="utf-8")
    output.write_text(
        content.replace(" unit=", " unit=000000000000000000000000", 1),
        encoding="utf-8",
    )

    with pytest.raises(Exception, match="Markdown|manifest|身份"):
        processor.repair([str(image)], str(output), skip_preprocess=True)

    assert llm.repair_calls == []


def test_board_repair_rejects_legacy_filename_marker_without_identity(tmp_path):
    image = tmp_path / "board.png"
    _make_png(image, "white")
    output = tmp_path / "board.md"
    output.write_text(
        "<!-- 批次 1 (board.png) 识别失败: timeout -->",
        encoding="utf-8",
    )
    llm = _BoardLLM()
    processor = _processor(tmp_path, llm)

    with pytest.raises(Exception, match="manifest|身份"):
        processor.repair([str(image)], str(output), skip_preprocess=True)

    assert llm.repair_calls == []


@pytest.mark.parametrize("damage", ["missing", "corrupt"])
def test_board_repair_rejects_unusable_manifest_before_provider_call(tmp_path, damage):
    image = tmp_path / "board.png"
    _make_png(image, "white")
    processor, llm, output = _produce_failed_output(
        tmp_path,
        [image],
        responses=[RuntimeError("timeout")],
    )
    sidecar = output.with_name(output.name + ".board-repair.json")
    if damage == "missing":
        sidecar.unlink(missing_ok=True)
    else:
        sidecar.write_text(json.dumps({"schema": "wrong"}), encoding="utf-8")

    with pytest.raises(Exception, match="manifest|身份"):
        processor.repair([str(image)], str(output), skip_preprocess=True)

    assert llm.repair_calls == []
