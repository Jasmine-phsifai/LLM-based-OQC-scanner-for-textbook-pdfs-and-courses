from pathlib import Path
from types import SimpleNamespace

import pytest

from OCRLLM.core.provider_errors import ProviderSetupError
from OCRLLM.core.task_runner import CancelledError
from OCRLLM.processors.audio import AudioProcessor


class _ScriptedAudioLLM:
    def __init__(self, responses):
        self._responses = iter(responses)

    def transcribe_short_audio(self, **_kwargs):
        response = next(self._responses)
        if isinstance(response, Exception):
            raise response
        return response


def _audio_processor(tmp_path: Path, responses):
    chunk_paths = [tmp_path / "chunk-1.mp3", tmp_path / "chunk-2.mp3"]
    for path in chunk_paths:
        path.write_bytes(b"chunk")
    processor = AudioProcessor.__new__(AudioProcessor)
    processor.cfg = SimpleNamespace(models=SimpleNamespace(asr_short_model="test-asr"))
    processor.llm = _ScriptedAudioLLM(responses)
    processor._ensure_upload_format = lambda path: path
    processor._should_use_short_asr = lambda _path: (True, 2.0)
    processor._split_audio = lambda _path, duration: [
        SimpleNamespace(path=str(path)) for path in chunk_paths
    ]
    processor._build_system_prompt = lambda *_args: "prompt"
    processor._report = lambda *_args: None
    processor._check_cancelled = lambda: None
    processor._report_content = lambda *_args: None
    return processor


def test_audio_repair_publishes_success_before_cancellation(tmp_path):
    audio_path = tmp_path / "lecture.mp3"
    md_path = tmp_path / "lecture.md"
    audio_path.write_bytes(b"audio")
    md_path.write_text(
        "（分段 1 识别失败: timeout）\n\n（分段 2 识别失败: timeout）",
        encoding="utf-8",
    )
    processor = _audio_processor(
        tmp_path,
        ["第一段已修复", CancelledError("任务已取消")],
    )

    with pytest.raises(CancelledError):
        processor.repair(str(audio_path), str(md_path))

    content = md_path.read_text(encoding="utf-8")
    assert "第一段已修复" in content
    assert "分段 1 识别失败" not in content
    assert "分段 2 识别失败" in content


def test_audio_repair_propagates_provider_setup_errors(tmp_path):
    audio_path = tmp_path / "lecture.mp3"
    md_path = tmp_path / "lecture.md"
    audio_path.write_bytes(b"audio")
    md_path.write_text("（分段 1 识别失败: timeout）", encoding="utf-8")
    processor = _audio_processor(
        tmp_path,
        [ProviderSetupError("provider SDK missing")],
    )

    with pytest.raises(ProviderSetupError, match="provider SDK missing"):
        processor.repair(str(audio_path), str(md_path))

    assert "分段 1 识别失败" in md_path.read_text(encoding="utf-8")
