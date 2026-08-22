from pathlib import Path

import pytest

from OCRLLM.config import AppConfig
from OCRLLM.core.provider_errors import ProviderSetupError
from OCRLLM.core.task_runner import CancelledError
from OCRLLM.processors.board import BoardProcessor


class _ScriptedBoardLLM:
    def __init__(self, responses):
        self._responses = iter(responses)

    def chat_with_images(self, **_kwargs):
        response = next(self._responses)
        if isinstance(response, Exception):
            raise response
        return response


def _board_processor(tmp_path: Path, responses):
    processor = BoardProcessor.__new__(BoardProcessor)
    processor.cfg = AppConfig().with_updates(
        paths={"output_dir": str(tmp_path), "temp_dir": str(tmp_path)},
    )
    processor.llm = _ScriptedBoardLLM(responses)
    processor._report = lambda *_args: None
    processor._check_cancelled = lambda: None
    processor._report_content = lambda *_args: None
    return processor


def test_board_repair_publishes_success_and_propagates_cancellation(tmp_path):
    image_paths = [tmp_path / "board-1.png", tmp_path / "board-2.png"]
    for path in image_paths:
        path.write_bytes(b"image")
    md_path = tmp_path / "board.md"
    md_path.write_text(
        "<!-- 批次 1 (board-1.png) 识别失败: timeout -->\n\n"
        "<!-- 批次 2 (board-2.png) 识别失败: timeout -->",
        encoding="utf-8",
    )
    processor = _board_processor(
        tmp_path,
        ["第一批已修复", CancelledError("任务已取消")],
    )

    with pytest.raises(CancelledError):
        processor.repair(
            [str(path) for path in image_paths],
            str(md_path),
            skip_preprocess=True,
        )

    content = md_path.read_text(encoding="utf-8")
    assert "第一批已修复" in content
    assert "批次 1" not in content
    assert "批次 2" in content


def test_board_repair_propagates_provider_setup_errors(tmp_path):
    image_path = tmp_path / "board.png"
    image_path.write_bytes(b"image")
    md_path = tmp_path / "board.md"
    md_path.write_text(
        "<!-- 批次 1 (board.png) 识别失败: timeout -->",
        encoding="utf-8",
    )
    processor = _board_processor(
        tmp_path,
        [ProviderSetupError("provider SDK missing")],
    )

    with pytest.raises(ProviderSetupError, match="provider SDK missing"):
        processor.repair([str(image_path)], str(md_path), skip_preprocess=True)

    assert "批次 1" in md_path.read_text(encoding="utf-8")
