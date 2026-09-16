import shutil
import subprocess
import threading
from pathlib import Path

import pytest

from ocrllm import CodexCLISettings, Config, VisionModelSettings, recognize
from ocrllm.errors import (
    Cancelled,
    ConfigError,
    InvalidSource,
    ProviderError,
    ProviderRequestInvalid,
    ProviderUnavailable,
)
from ocrllm.providers.codex_cli import recognize_images as codex_adapter
from ocrllm.providers.codex_cli.codex_exec_output import (
    is_image_access_refusal,
    parse_codex_refusal,
    summarize_codex_failure_output,
)

from write_test_image import write_test_image


@pytest.fixture
def fake_cli(monkeypatch):
    """Install a scripted `codex exec` subprocess and zero retry delays."""
    monkeypatch.setattr(shutil, "which", lambda command: "/fake/codex")
    monkeypatch.setattr(codex_adapter, "_RETRY_DELAY_SECONDS", 0.0)
    monkeypatch.setattr(
        codex_adapter,
        "_IMAGE_ACCESS_RETRY_DELAYS_SECONDS",
        (0.0, 0.0, 0.0, 0.0, 0.0),
    )
    state = {"script": [], "calls": [], "kwargs": []}

    def fake_run(argv, **kwargs):
        state["calls"].append(list(argv))
        state["kwargs"].append(kwargs)
        hook = state.get("on_call")
        if hook is not None:
            hook()
        index = min(len(state["calls"]) - 1, len(state["script"]) - 1)
        action, payload = state["script"][index]
        if action == "ok":
            output_path = Path(argv[argv.index("--output-last-message") + 1])
            output_path.write_text(payload, encoding="utf-8")
            return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")
        if action == "fail":
            return subprocess.CompletedProcess(argv, 2, stdout="", stderr=payload)
        if action == "timeout":
            raise subprocess.TimeoutExpired(cmd=argv, timeout=1)
        if action == "oserror":
            raise OSError(payload)
        raise AssertionError(f"unknown fake action: {action}")

    monkeypatch.setattr(subprocess, "run", fake_run)
    return state


def _images(tmp_path, count):
    return [write_test_image(tmp_path / f"img_{index}.png") for index in range(count)]


def _run(tmp_path, count=2, config=None):
    return codex_adapter.recognize_images(
        _images(tmp_path, count),
        prompt="识别这些板书",
        config=config or Config(provider=CodexCLISettings()),
    )


def test_adapter_dispatches_luna_low_with_eight_staged_images(tmp_path, fake_cli):
    fake_cli["script"] = [("ok", "# Board\n\ncontent")]

    text = _run(tmp_path, count=8)

    assert text == "# Board\n\ncontent"
    argv = fake_cli["calls"][0]
    assert argv[:2] == ["codex", "--ask-for-approval"]
    assert "exec" in argv
    assert "--ephemeral" in argv
    assert "--ignore-user-config" in argv
    assert "--ignore-rules" in argv
    assert argv[argv.index("--sandbox") + 1] == "read-only"
    assert argv[argv.index("-m") + 1] == "gpt-5.6-luna"
    assert 'model_reasoning_effort="low"' in argv
    assert argv.count("-i") == 8
    staged_names = [argv[index + 1] for index, value in enumerate(argv) if value == "-i"]
    assert all(Path(name).name.startswith("image_") for name in staged_names)
    prompt = argv[argv.index("--") + 1]
    assert "SORRY4OCRLLM" in prompt
    assert "本次共有 8 张图片" in prompt
    assert "识别这些板书" in prompt
    assert fake_cli["kwargs"][0]["timeout"] == 1800.0


def test_adapter_honors_fast_mode_and_model_override(tmp_path, fake_cli):
    fake_cli["script"] = [("ok", "text")]
    config = Config(
        provider=CodexCLISettings(fast_mode=True),
        vision_model=VisionModelSettings(name="gpt-5.6-sol"),
    )

    _run(tmp_path, config=config)

    argv = fake_cli["calls"][0]
    assert argv[argv.index("-m") + 1] == "gpt-5.6-sol"
    assert 'service_tier="priority"' in argv


def test_adapter_rejects_batch_beyond_max_without_spawning(tmp_path, fake_cli):
    with pytest.raises(ProviderRequestInvalid) as caught:
        _run(tmp_path, count=9)

    assert caught.value.details["provider_calls_attempted"] == 0
    assert fake_cli["calls"] == []


def test_adapter_requires_codex_command(tmp_path, fake_cli, monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda command: None)

    with pytest.raises(ConfigError) as caught:
        _run(tmp_path)

    assert caught.value.code == "CONFIG_MISSING"
    assert caught.value.details["provider_calls_attempted"] == 0
    assert fake_cli["calls"] == []


def test_adapter_reports_missing_image_without_provider_call(tmp_path, fake_cli):
    paths = _images(tmp_path, 1)
    paths.append(tmp_path / "missing.png")

    with pytest.raises(InvalidSource) as caught:
        codex_adapter.recognize_images(
            paths,
            prompt="p",
            config=Config(provider=CodexCLISettings()),
        )

    assert caught.value.code == "SOURCE_NOT_FOUND"
    assert caught.value.details["provider_calls_attempted"] == 0
    assert fake_cli["calls"] == []


def test_adapter_retries_failed_exit_then_succeeds(tmp_path, fake_cli):
    fake_cli["script"] = [
        ("fail", "Error: rate limit 429"),
        ("fail", "Error: rate limit 429"),
        ("ok", "recovered"),
    ]

    assert _run(tmp_path) == "recovered"
    assert len(fake_cli["calls"]) == 3


def test_adapter_maps_persistent_exit_failure_to_unavailable(tmp_path, fake_cli):
    fake_cli["script"] = [("fail", "Error: 500 internal\nsession id: abc123")]

    with pytest.raises(ProviderUnavailable) as caught:
        _run(tmp_path)

    assert caught.value.retryable is True
    assert caught.value.details["provider_calls_attempted"] == 3
    assert "500 internal" in caught.value.details["description"]
    assert len(fake_cli["calls"]) == 3


def test_adapter_maps_persistent_refusal_to_refused_recognition(tmp_path, fake_cli):
    fake_cli["script"] = [("ok", "SORRY4OCRLLM, because 内容令人困惑")]

    with pytest.raises(ProviderError) as caught:
        _run(tmp_path)

    assert caught.value.code == "PROVIDER_REFUSED_RECOGNITION"
    assert caught.value.retryable is False
    assert caught.value.details["provider_calls_attempted"] == 3
    assert "内容令人困惑" in caught.value.details["description"]


def test_image_attachment_loss_uses_separate_backoff_budget(tmp_path, fake_cli):
    fake_cli["script"] = [
        ("ok", "SORRY4OCRLLM, because cannot access the attached image"),
        ("ok", "# Board\n\nfinally visible"),
    ]

    assert _run(tmp_path) == "# Board\n\nfinally visible"
    assert len(fake_cli["calls"]) == 2


def test_image_attachment_loss_exhaustion_reports_all_spawns(tmp_path, fake_cli):
    fake_cli["script"] = [
        ("ok", "SORRY4OCRLLM, because 无法访问附加图片"),
    ]

    with pytest.raises(ProviderUnavailable) as caught:
        _run(tmp_path)

    assert "attachments" in str(caught.value)
    # 1 initial attempt + 5 long-backoff retries, all real spawns.
    assert len(fake_cli["calls"]) == 6
    assert caught.value.details["provider_calls_attempted"] == 6


def test_adapter_maps_empty_output_to_response_invalid(tmp_path, fake_cli):
    fake_cli["script"] = [("ok", "")]

    with pytest.raises(ProviderError) as caught:
        _run(tmp_path)

    assert caught.value.code == "PROVIDER_RESPONSE_INVALID"
    assert caught.value.details["reason"] == "empty"
    assert caught.value.details["provider_calls_attempted"] == 3


def test_adapter_timeout_never_retries(tmp_path, fake_cli):
    fake_cli["script"] = [("timeout", "")]

    with pytest.raises(ProviderError) as caught:
        _run(tmp_path)

    assert caught.value.code == "PROVIDER_TIMEOUT"
    assert caught.value.retryable is True
    assert caught.value.details["provider_calls_attempted"] == 1
    assert len(fake_cli["calls"]) == 1


def test_adapter_retries_spawn_resource_pressure(tmp_path, fake_cli):
    fake_cli["script"] = [("oserror", "paging file too small")]

    with pytest.raises(ProviderUnavailable) as caught:
        _run(tmp_path)

    assert "paging file" in caught.value.details["description"]
    assert len(fake_cli["calls"]) == 3


def test_adapter_cancellation_stops_between_attempts(tmp_path, fake_cli):
    cancel = threading.Event()
    fake_cli["script"] = [("fail", "Error: boom")]
    fake_cli["on_call"] = cancel.set

    with pytest.raises(Cancelled):
        codex_adapter.recognize_images(
            _images(tmp_path, 1),
            prompt="p",
            config=Config(
                provider=CodexCLISettings(),
                cancellation=cancel,
            ),
        )

    assert len(fake_cli["calls"]) == 1


def test_parse_codex_refusal_variants():
    assert parse_codex_refusal("# Board\n\ncontent") is None
    assert parse_codex_refusal("") is None
    assert parse_codex_refusal("SORRY4OCRLLM, because 无法访问图片") == "无法访问图片"
    assert parse_codex_refusal("sorry4ocrllm because: 内容违规。") == "内容违规。"
    assert parse_codex_refusal("SORRY4OCRLLM") == "未提供原因"


def test_is_image_access_refusal_markers():
    assert is_image_access_refusal("cannot access the attached image")
    assert is_image_access_refusal("无法读取该路径的图片")
    assert not is_image_access_refusal("内容令人困惑")
    assert not is_image_access_refusal("")


def test_summarize_codex_failure_output_redacts_prompt_and_keeps_session():
    output = (
        "用户原始提示:\n"
        "你是 OCRLLM 的本机 Codex 只读识图子进程。\n"
        "session id: sess-42\n"
        "Error: 429 rate limit exceeded\n"
    )

    summary = summarize_codex_failure_output(output, 2)

    assert "429 rate limit exceeded" in summary
    assert "sess-42" in summary
    assert "用户原始提示" not in summary
    assert "OCRLLM" not in summary
    assert "without diagnostic output" in summarize_codex_failure_output("", 1)


def test_facade_recognize_runs_codex_cli_end_to_end(tmp_path, fake_cli):
    fake_cli["script"] = [("ok", "# Board\n\n- 板书内容")]
    source = write_test_image(tmp_path / "board.png")

    result = recognize(source, config=Config(provider=CodexCLISettings()))

    assert result.status == "complete"
    assert result.markdown == "# Board\n\n- 板书内容"
    assert result.metadata["provider"] == "codex_cli"
    assert result.metadata["model"] == "gpt-5.6-luna"
    assert result.metadata["provider_call_count"] == 1
    assert len(fake_cli["calls"]) == 1
