from pathlib import Path

import pytest

from OCRLLM.config import AppConfig
from OCRLLM.core.provider_errors import ProviderSetupError
from OCRLLM.core.task_runner import CancelledError
from OCRLLM.processors.board import BoardProcessor
from OCRLLM.processors.board_repair_manifest import (
    create_board_repair_manifest,
    render_board_batch_failure,
    save_board_repair_manifest,
)


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


def _write_repairable_failures(md_path: Path, image_paths: list[Path]) -> None:
    manifest = create_board_repair_manifest(
        batches=([str(path)] for path in image_paths),
        batch_size=1,
        prompt="test prompt",
        skip_preprocess=True,
    )
    save_board_repair_manifest(md_path, manifest)
    md_path.write_text(
        "\n\n".join(
            render_board_batch_failure(batch, "timeout")
            for batch in manifest.batches
        ),
        encoding="utf-8",
    )


def test_board_repair_publishes_success_and_propagates_cancellation(tmp_path):
    image_paths = [tmp_path / "board-1.png", tmp_path / "board-2.png"]
    for path in image_paths:
        path.write_bytes(b"image")
    md_path = tmp_path / "board.md"
    _write_repairable_failures(md_path, image_paths)
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
    _write_repairable_failures(md_path, [image_path])
    processor = _board_processor(
        tmp_path,
        [ProviderSetupError("provider SDK missing")],
    )

    with pytest.raises(ProviderSetupError, match="provider SDK missing"):
        processor.repair([str(image_path)], str(md_path), skip_preprocess=True)

    assert "批次 1" in md_path.read_text(encoding="utf-8")
