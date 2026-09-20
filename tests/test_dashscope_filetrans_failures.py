from __future__ import annotations

import importlib
import hashlib
import json
from pathlib import Path

import pytest

from ocrllm import NoSpeechDetected, ProviderError
from ocrllm.audio.snapshot_long_mp3 import LongMP3Snapshot
from ocrllm.providers.dashscope.filetrans_settings import DashScopeFileTransSettings


adapter = importlib.import_module("ocrllm.providers.dashscope.recognize_filetrans")


def test_failed_no_words_is_provider_failure(monkeypatch):
    monkeypatch.setattr(
        adapter,
        "_request_json",
        lambda *args, **kwargs: {
            "output": {
                "task_status": "FAILED",
                "code": "ASR_RESPONSE_HAVE_NO_WORDS",
                "message": "ASR_RESPONSE_HAVE_NO_WORDS",
            }
        },
    )

    with pytest.raises(ProviderError) as caught:
        adapter._poll(
            "task-failed",
            model="qwen-audio-3.0-asr-flash-filetrans",
            api_key="secret",
            base_url="https://dashscope.aliyuncs.com",
            timeout_seconds=1,
            poll_interval=0.01,
            cancellation=None,
        )

    assert caught.value.code == "PROVIDER_RESPONSE_INVALID"
    assert caught.value.details["provider_code"] == "ASR_RESPONSE_HAVE_NO_WORDS"
    assert caught.value.details["task_status"] == "FAILED"
    assert caught.value.details["task_id"] == "task-failed"


def test_success_with_no_valid_fragment_remains_legitimate_silence(monkeypatch):
    monkeypatch.setattr(
        adapter,
        "_request_json",
        lambda *args, **kwargs: {
            "output": {
                "task_status": "SUCCESS_WITH_NO_VALID_FRAGMENT",
                "code": "NO_VALID_FRAGMENT",
            }
        },
    )

    with pytest.raises(NoSpeechDetected):
        adapter._poll(
            "task-silent",
            model="qwen-audio-3.0-asr-flash-filetrans",
            api_key="secret",
            base_url="https://dashscope.aliyuncs.com",
            timeout_seconds=1,
            poll_interval=0.01,
            cancellation=None,
        )


def test_terminal_failure_is_persisted_with_existing_task_id(tmp_path, monkeypatch):
    source = tmp_path / "clip.mp3"
    source.write_bytes(b"fake-mp3")
    snapshot = LongMP3Snapshot(
        path=source,
        byte_size=source.stat().st_size,
        sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        duration_seconds=1.0,
    )
    settings = DashScopeFileTransSettings(
        api_key="secret",
        task_state_dir=tmp_path / "state",
        poll_interval_seconds=0.01,
        poll_timeout_seconds=1,
    )
    prompt = "transcribe"
    identity = adapter._request_identity(
        snapshot,
        model="qwen-audio-3.0-asr-flash-filetrans",
        prompt=prompt,
        base_url=settings.base_url,
    )
    sidecar = tmp_path / "state" / f"{identity}.json"
    sidecar.parent.mkdir()
    json.dump(
        {
            "version": adapter._STATE_VERSION,
            "identity": identity,
            "source_sha256": snapshot.sha256,
            "model": "qwen-audio-3.0-asr-flash-filetrans",
            "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
            "status": "submitted",
            "task_id": "task-failed",
        },
        sidecar.open("w"),
    )
    monkeypatch.setattr(
        adapter,
        "_request_json",
        lambda *args, **kwargs: {
            "output": {
                "task_status": "FAILED",
                "code": "ASR_RESPONSE_HAVE_NO_WORDS",
            }
        },
    )

    with pytest.raises(ProviderError):
        adapter.recognize_filetrans(
            snapshot,
            prompt=prompt,
            vendor="dashscope",
            model="qwen-audio-3.0-asr-flash-filetrans",
            settings=settings,
            timeout_seconds=1,
        )

    saved = json.loads(sidecar.read_text())
    assert saved["status"] == "failed"
    assert saved["task_id"] == "task-failed"
    assert saved["failure"]["provider_code"] == "ASR_RESPONSE_HAVE_NO_WORDS"
