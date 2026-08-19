import tempfile
import subprocess
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from OCRLLM.config import CodexVisionConfig
from OCRLLM.core.codex_vision import CodexCLIUnavailableError, CodexVisionRunner


def _run_codex_with_output(output_text: str):
    def fake_run(cmd, **_kwargs):
        output_path = cmd[cmd.index("--output-last-message") + 1]
        with open(output_path, "w", encoding="utf-8") as output_file:
            output_file.write(output_text)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    cfg = CodexVisionConfig(enabled=True, command="codex")
    with tempfile.NamedTemporaryFile(suffix=".png") as image_file, \
            patch("OCRLLM.core.codex_vision.shutil.which", return_value="codex"), \
            patch("OCRLLM.core.codex_vision.subprocess.run", side_effect=fake_run) as run_mock, \
            patch("OCRLLM.core.codex_vision.time.sleep"):
        runner = CodexVisionRunner(cfg)
        try:
            return runner.recognize("识别图片", [image_file.name]), run_mock.call_count
        except Exception as exc:
            exc.run_call_count = run_mock.call_count
            raise


def test_codex_refusal_retries_then_raises_with_reason():
    with pytest.raises(CodexCLIUnavailableError, match="图片模糊") as exc_info:
        _run_codex_with_output("SORRY4OCRLLM, because 图片模糊")

    assert exc_info.value.run_call_count == 2


def test_codex_sentinel_mid_document_is_returned_as_content():
    content = "转录正文提到了 SORRY4OCRLLM, because 图片模糊，随后继续正常内容。"

    result, call_count = _run_codex_with_output(content)

    assert result == content
    assert call_count == 1


def test_codex_prompt_declares_exact_refusal_contract():
    prompt = CodexVisionRunner._build_prompt("识别图片", 1)

    assert "SORRY4OCRLLM, because {原因}" in prompt
    assert "除此之外不要输出任何内容" in prompt


def test_codex_default_timeout_is_1800_and_timeout_is_not_retried():
    cfg = CodexVisionConfig(enabled=True, command="codex")
    with tempfile.NamedTemporaryFile(suffix=".png") as image_file, \
            patch("OCRLLM.core.codex_vision.shutil.which", return_value="codex"), \
            patch(
                "OCRLLM.core.codex_vision.subprocess.run",
                side_effect=subprocess.TimeoutExpired("codex", 1800),
            ) as run_mock:
        with pytest.raises(CodexCLIUnavailableError, match="超时"):
            CodexVisionRunner(cfg).recognize("识别图片", [image_file.name])

    assert cfg.timeout_seconds == 1800
    assert run_mock.call_count == 1
    assert run_mock.call_args.kwargs["timeout"] == 1800
