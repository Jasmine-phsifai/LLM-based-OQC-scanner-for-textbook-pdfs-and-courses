import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from OCRLLM.core.task_runner import CancelledError, ProgressReporter
from OCRLLM.core.provider_errors import ProviderSetupError
from OCRLLM.core.write_text_atomically import write_text_atomically as real_atomic_write
from OCRLLM.processors.audio import AudioChunk, AudioProcessor
from OCRLLM.processors.audio_repair_manifest import audio_repair_manifest_path


def _processor(tmp_path: Path, llm, *, chunk_count=2, workers=2):
    source = tmp_path / "lecture.mp3"
    source.write_bytes(b"source")
    chunk_paths = [tmp_path / f"chunk-{index}.mp3" for index in range(1, chunk_count + 1)]
    for index, path in enumerate(chunk_paths, start=1):
        path.write_bytes(f"chunk-{index}".encode("ascii"))
    chunks = [
        AudioChunk(str(path), float(index), float(index + 1), float(index), float(index + 1))
        for index, path in enumerate(chunk_paths)
    ]
    processor = AudioProcessor.__new__(AudioProcessor)
    processor.cfg = SimpleNamespace(
        models=SimpleNamespace(asr_short_model="test-asr"),
        processing=SimpleNamespace(
            asr_short_chunk_seconds=60,
            asr_fallback_chunk_seconds=30,
            asr_fallback_context_seconds=5,
        ),
        concurrency=SimpleNamespace(audio_asr_parallel_requests=workers),
    )
    processor.llm = llm
    processor.reporter = ProgressReporter()
    processor._split_audio = lambda *_args, **_kwargs: chunks
    processor._build_system_prompt = lambda *_args: "prompt"
    processor._report_content = lambda *_args: None
    return processor, source, chunk_paths


class _SuccessThenCancelLLM:
    def __init__(self, first_path: Path):
        self.first_path = str(first_path)
        self.first_finished = threading.Event()
        self.release_cancellation = threading.Event()

    def transcribe_short_audio(self, *, audio_path, **_kwargs):
        if audio_path == self.first_path:
            self.first_finished.set()
            return "first paid success"
        assert self.first_finished.wait(timeout=2)
        assert self.release_cancellation.wait(timeout=2)
        raise CancelledError("cancel after paid success")


class _SecondFinishesFirstLLM:
    def __init__(self, first_path: Path):
        self.first_path = str(first_path)
        self.second_finished = threading.Event()
        self.release_first = threading.Event()

    def transcribe_short_audio(self, *, audio_path, **_kwargs):
        if audio_path != self.first_path:
            self.second_finished.set()
            return "second finished first"
        assert self.second_finished.wait(timeout=2)
        assert self.release_first.wait(timeout=2)
        return "first finished last"


class _CheckpointObservingLLM:
    def __init__(self, output_path: Path):
        self.output_path = output_path
        self.saw_checkpoint = False

    def transcribe_short_audio(self, **_kwargs):
        self.saw_checkpoint = (
            self.output_path.exists()
            and audio_repair_manifest_path(self.output_path).exists()
            and "分段 1 未完成" in self.output_path.read_text(encoding="utf-8")
        )
        return "recognized"


class _CancelReporterAfterFirstSuccessLLM:
    def __init__(self, reporter):
        self.reporter = reporter
        self.calls = 0

    def transcribe_short_audio(self, **_kwargs):
        self.calls += 1
        self.reporter.cancel()
        return "first success before user cancellation"


class _SuccessThenSetupErrorLLM:
    def __init__(self):
        self.calls = 0

    def transcribe_short_audio(self, **_kwargs):
        self.calls += 1
        if self.calls == 1:
            return "first success before setup failure"
        raise ProviderSetupError("provider SDK unavailable")


def test_short_asr_preserves_success_when_a_later_future_cancels(tmp_path, monkeypatch):
    placeholder = tmp_path / "placeholder"
    llm = _SuccessThenCancelLLM(placeholder)
    processor, source, chunk_paths = _processor(tmp_path, llm)
    llm.first_path = str(chunk_paths[0])
    output = tmp_path / "lecture.md"

    def release_cancellation_after_publication(path, text):
        real_atomic_write(path, text)
        if Path(path) == output and "first paid success" in text:
            llm.release_cancellation.set()

    monkeypatch.setattr(
        "OCRLLM.processors.audio.write_text_atomically",
        release_cancellation_after_publication,
    )

    with pytest.raises(CancelledError, match="cancel after paid success"):
        processor._short_asr(
            str(source),
            None,
            str(output),
            duration=2.0,
            source_path=str(source),
        )

    content = output.read_text(encoding="utf-8")
    assert "first paid success" in content
    assert "分段 2 未完成" in content
    assert audio_repair_manifest_path(output).exists()


def test_short_asr_atomically_publishes_out_of_order_completions(tmp_path, monkeypatch):
    placeholder = tmp_path / "placeholder"
    llm = _SecondFinishesFirstLLM(placeholder)
    processor, source, chunk_paths = _processor(tmp_path, llm)
    llm.first_path = str(chunk_paths[0])
    output = tmp_path / "lecture.md"
    snapshots = []

    def record_atomic_write(path, text):
        real_atomic_write(path, text)
        if Path(path) == output:
            snapshots.append(text)
            if "分段 1 未完成" in text and "second finished first" in text:
                llm.release_first.set()

    monkeypatch.setattr("OCRLLM.processors.audio.write_text_atomically", record_atomic_write)

    processor._short_asr(
        str(source),
        None,
        str(output),
        duration=2.0,
        source_path=str(source),
    )

    assert any(
        "分段 1 未完成" in snapshot and "second finished first" in snapshot
        for snapshot in snapshots
    )
    assert "first finished last" in snapshots[-1]
    assert "second finished first" in snapshots[-1]


def test_short_asr_publishes_repairable_checkpoint_before_provider_dispatch(tmp_path):
    output = tmp_path / "lecture.md"
    llm = _CheckpointObservingLLM(output)
    processor, source, _chunk_paths = _processor(tmp_path, llm)

    processor._short_asr(
        str(source),
        None,
        str(output),
        duration=2.0,
        source_path=str(source),
    )

    assert llm.saw_checkpoint


def test_short_asr_cancellation_stops_new_submissions_and_keeps_success(tmp_path):
    processor, source, _chunk_paths = _processor(
        tmp_path,
        llm=None,
        chunk_count=3,
        workers=1,
    )
    llm = _CancelReporterAfterFirstSuccessLLM(processor.reporter)
    processor.llm = llm
    output = tmp_path / "lecture.md"

    with pytest.raises(CancelledError):
        processor._short_asr(
            str(source),
            None,
            str(output),
            duration=3.0,
            source_path=str(source),
        )

    content = output.read_text(encoding="utf-8")
    assert llm.calls == 1
    assert "first success before user cancellation" in content
    assert "分段 2 未完成" in content
    assert "分段 3 未完成" in content


def test_short_asr_setup_error_drains_success_and_stops_new_submissions(tmp_path):
    llm = _SuccessThenSetupErrorLLM()
    processor, source, _chunk_paths = _processor(
        tmp_path,
        llm,
        chunk_count=3,
        workers=1,
    )
    output = tmp_path / "lecture.md"

    with pytest.raises(ProviderSetupError, match="provider SDK unavailable"):
        processor._short_asr(
            str(source),
            None,
            str(output),
            duration=3.0,
            source_path=str(source),
        )

    content = output.read_text(encoding="utf-8")
    assert llm.calls == 2
    assert "first success before setup failure" in content
    assert "分段 2 未完成" in content
    assert "分段 3 未完成" in content
