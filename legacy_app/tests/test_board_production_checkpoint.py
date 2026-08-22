import json
from pathlib import Path

import pytest
from PIL import Image

from OCRLLM.config import AppConfig
from OCRLLM.core.provider_errors import ProviderSetupError
from OCRLLM.core.task_runner import CancelledError, ProgressReporter
from OCRLLM.processors.board import BoardProcessor
from OCRLLM.processors.board_repair_manifest import board_repair_manifest_path


def _make_png(path: Path, color: str) -> None:
    Image.new("RGB", (8, 8), color).save(path)


def _processor(tmp_path: Path, llm) -> BoardProcessor:
    processor = BoardProcessor.__new__(BoardProcessor)
    processor.cfg = AppConfig().with_updates(
        paths={"output_dir": str(tmp_path), "temp_dir": str(tmp_path / "temp")},
        processing={"batch_size": 1},
    )
    processor.llm = llm
    processor.reporter = ProgressReporter()
    return processor


def _inputs(tmp_path: Path) -> tuple[list[str], Path]:
    first = tmp_path / "board-1.png"
    second = tmp_path / "board-2.png"
    _make_png(first, "white")
    _make_png(second, "black")
    return [str(first), str(second)], tmp_path / "board.md"


class _ObserveInitialCheckpointLLM:
    def __init__(self, output: Path):
        self.output = output
        self.saw_repairable_checkpoint = False

    def chat_with_images_contextual(self, **_kwargs):
        manifest_path = board_repair_manifest_path(self.output)
        if self.output.exists() and manifest_path.exists():
            markdown = self.output.read_text(encoding="utf-8")
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.saw_repairable_checkpoint = self.saw_repairable_checkpoint or (
                manifest["schema"] == "ocrllm.board_repair_manifest"
                and markdown.count("status=failed") == 2
                and markdown.count("识别失败: 任务未完成") == 2
            )
        return "可用的板书识别正文" * 20


class _CancelAfterPaidSuccessLLM:
    def __init__(self, reporter: ProgressReporter):
        self.reporter = reporter
        self.calls = 0

    def chat_with_images_contextual(self, **_kwargs):
        self.calls += 1
        if self.calls == 1:
            self.reporter.cancel()
            return "第一批已付费成功正文" * 20
        raise AssertionError("cancellation must stop the second provider call")


class _SuccessThenTerminalErrorLLM:
    def __init__(self, terminal_error: Exception):
        self.terminal_error = terminal_error
        self.calls = 0

    def chat_with_images_contextual(self, **_kwargs):
        self.calls += 1
        if self.calls == 1:
            return "第一批已付费成功正文" * 20
        raise self.terminal_error


def test_board_publishes_repairable_skeleton_before_provider_dispatch(tmp_path):
    image_paths, output = _inputs(tmp_path)
    llm = _ObserveInitialCheckpointLLM(output)
    processor = _processor(tmp_path, llm)

    processor.process(image_paths, output_path=str(output), skip_preprocess=True)

    assert llm.saw_repairable_checkpoint


def test_board_preserves_paid_success_when_reporter_cancels_before_next_batch(tmp_path):
    image_paths, output = _inputs(tmp_path)
    processor = _processor(tmp_path, llm=None)
    llm = _CancelAfterPaidSuccessLLM(processor.reporter)
    processor.llm = llm

    with pytest.raises(CancelledError):
        processor.process(image_paths, output_path=str(output), skip_preprocess=True)

    markdown = output.read_text(encoding="utf-8")
    assert llm.calls == 1
    assert "第一批已付费成功正文" in markdown
    assert markdown.count("status=complete") == 1
    assert markdown.count("status=failed") == 1
    assert "批次 2 识别失败: 任务未完成" in markdown


@pytest.mark.parametrize(
    "terminal_error",
    [
        CancelledError("provider observed cancellation"),
        ProviderSetupError("provider SDK unavailable"),
    ],
    ids=["provider-cancellation", "provider-setup"],
)
def test_board_preserves_paid_success_and_propagates_terminal_provider_error(
    tmp_path,
    terminal_error,
):
    image_paths, output = _inputs(tmp_path)
    llm = _SuccessThenTerminalErrorLLM(terminal_error)
    processor = _processor(tmp_path, llm)

    with pytest.raises(type(terminal_error), match=str(terminal_error)):
        processor.process(image_paths, output_path=str(output), skip_preprocess=True)

    markdown = output.read_text(encoding="utf-8")
    assert llm.calls == 2
    assert "第一批已付费成功正文" in markdown
    assert markdown.count("status=complete") == 1
    assert markdown.count("status=failed") == 1
    assert "批次 2 识别失败: 任务未完成" in markdown
