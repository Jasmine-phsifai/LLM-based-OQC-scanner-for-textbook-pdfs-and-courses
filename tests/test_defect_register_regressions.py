"""Regression tests for the defect register entries D1-D4."""

from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest

from ocrllm import (
    Config,
    ProviderError,
    RecognitionExecutionPolicy,
    recognize,
    recognize_batch,
)
from ocrllm.errors import ConfigError, OCRLLMError
from ocrllm.provider_error_disposition import get_provider_error_disposition
from ocrllm.providers.looks_like_refusal import looks_like_refusal

from write_test_image import write_test_image


class _FixedResponseProvider:
    def __init__(self, response: str, *, resume_identity: str | None = None) -> None:
        self.response = response
        self.calls = 0
        if resume_identity is not None:
            self.resume_identity = resume_identity

    def recognize_images(self, image_paths, *, prompt, config):
        self.calls += 1
        return self.response


class _SleepingProvider:
    def __init__(self, sleep_seconds: float) -> None:
        self.sleep_seconds = sleep_seconds

    def recognize_images(self, image_paths, *, prompt, config):
        time.sleep(self.sleep_seconds)
        return "# Board\n"


class _FailAfterProvider:
    """Succeed for the first calls, then fail, so paid work exists at failure time."""

    def __init__(self, success_count: int) -> None:
        self._lock = threading.Lock()
        self.calls = 0
        self._success_count = success_count

    def recognize_images(self, image_paths, *, prompt, config):
        with self._lock:
            self.calls += 1
            index = self.calls
        if index > self._success_count:
            raise ProviderError(
                "The provider request failed.",
                code="PROVIDER_UNAVAILABLE",
            )
        return f"# {image_paths[0].name}\n"


# D1 --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "response",
    [
        "无法识别图片内容，请重新上传",
        "抱歉，我无法读取这张图片。",
        "I'm sorry, I can't help with identifying content in this image.",
        "I am unable to read the image you provided.",
    ],
)
def test_refusal_text_is_not_a_successful_recognition(tmp_path, response) -> None:
    source = write_test_image(tmp_path / "board.png")
    provider = _FixedResponseProvider(response)

    with pytest.raises(ProviderError) as failure:
        recognize(source, config=Config(provider=provider))

    assert failure.value.code == "PROVIDER_REFUSED_RECOGNITION"
    assert failure.value.details["reason"] == "refusal"
    disposition = get_provider_error_disposition(failure.value)
    assert disposition.action == "change_source"
    assert disposition.retryable is False


@pytest.mark.parametrize(
    "response",
    [
        "抱歉，我帮不了你识别这张图。",
        "对不起，图片太模糊，请提供更清晰的版本。",
        "Sorry, this request cannot be completed.",
    ],
)
def test_apology_prefixed_refusal_is_not_a_successful_recognition(
    tmp_path,
    response,
) -> None:
    source = write_test_image(tmp_path / "board.png")
    provider = _FixedResponseProvider(response)

    with pytest.raises(ProviderError) as failure:
        recognize(source, config=Config(provider=provider))

    assert failure.value.code == "PROVIDER_REFUSED_RECOGNITION"
    assert failure.value.details["reason"] == "refusal"


def test_long_transcription_mentioning_a_refusal_phrase_is_accepted(tmp_path) -> None:
    source = write_test_image(tmp_path / "board.png")
    transcription = "# Board\n\n" + ("讲义提到无法识别的字符时应当标注。" * 40)
    provider = _FixedResponseProvider(transcription)

    result = recognize(source, config=Config(provider=provider))

    assert result.markdown == transcription


def test_looks_like_refusal_ignores_ordinary_content() -> None:
    assert not looks_like_refusal("# Board\n\n$x = 1$\n")
    assert not looks_like_refusal("<!-- I'm sorry, I cannot read it. -->\n# Board\n")
    assert not looks_like_refusal("")
    assert looks_like_refusal("无法识别")


# D2 --------------------------------------------------------------------------


def test_injected_provider_is_bounded_by_config_timeout(tmp_path) -> None:
    source = write_test_image(tmp_path / "board.png")
    config = Config(provider=_SleepingProvider(5.0), timeout_seconds=0.5)

    started_at = time.monotonic()
    with pytest.raises(ProviderError) as failure:
        recognize(source, config=config)
    elapsed = time.monotonic() - started_at

    assert failure.value.code == "PROVIDER_TIMEOUT"
    assert failure.value.retryable is True
    assert elapsed < 3.0


def test_injected_provider_within_timeout_still_succeeds(tmp_path) -> None:
    source = write_test_image(tmp_path / "board.png")
    config = Config(provider=_SleepingProvider(0.05), timeout_seconds=10.0)

    assert recognize(source, config=config).markdown == "# Board\n"


# D3 --------------------------------------------------------------------------


@pytest.mark.parametrize("failing_position", [0, 2, 4])
def test_serial_batch_reports_every_item_and_keeps_paid_results(
    tmp_path,
    failing_position,
) -> None:
    sources = [
        write_test_image(tmp_path / f"{index}.png", color=(0, index, 0))
        for index in range(5)
    ]
    provider = _FailAfterProvider(success_count=failing_position)

    outcomes = recognize_batch(sources, config=Config(provider=provider))

    assert [outcome.index for outcome in outcomes] == list(range(5))
    assert [outcome.succeeded for outcome in outcomes] == [
        index < failing_position for index in range(5)
    ]
    assert outcomes[failing_position].error.code == "PROVIDER_UNAVAILABLE"
    assert provider.calls == failing_position + 1


def test_batch_successes_retain_their_output_path(tmp_path) -> None:
    sources = [
        write_test_image(tmp_path / f"{index}.png", color=(0, index, 0))
        for index in range(3)
    ]
    output_dir = tmp_path / "output"
    provider = _FailAfterProvider(success_count=2)

    outcomes = recognize_batch(
        sources,
        config=Config(provider=provider, output_dir=output_dir),
    )

    published = [outcome.result.output_path for outcome in outcomes[:2]]
    assert all(path is not None and path.exists() for path in published)
    assert not outcomes[2].succeeded


def test_parallel_batch_failure_keeps_completed_paid_results(tmp_path) -> None:
    sources = [
        write_test_image(tmp_path / f"{index}.png", color=(0, index, 0))
        for index in range(6)
    ]
    provider = _FailAfterProvider(success_count=2)
    config = Config(
        provider=provider,
        execution=RecognitionExecutionPolicy(max_parallel_requests=2),
    )

    outcomes = recognize_batch(sources, config=config)

    assert len(outcomes) == 6
    assert [outcome.index for outcome in outcomes] == list(range(6))
    assert sum(outcome.succeeded for outcome in outcomes) == 2


def test_successful_batch_reports_every_item_as_succeeded(tmp_path) -> None:
    sources = [write_test_image(tmp_path / "only.png")]
    provider = _FailAfterProvider(success_count=1)

    outcomes = recognize_batch(sources, config=Config(provider=provider))

    assert [outcome.succeeded for outcome in outcomes] == [True]
    assert outcomes[0].result.markdown.strip() == "# only.png"


# D4 --------------------------------------------------------------------------


def _resume_config(provider: object, output_dir: Path) -> Config:
    return Config(provider=provider, output_dir=output_dir, resume=True)


def test_injected_provider_resume_reuses_completed_work(tmp_path, monkeypatch) -> None:
    import importlib

    source = write_test_image(tmp_path / "board.png")
    output_dir = tmp_path / "output"
    provider = _FixedResponseProvider("# Resumable\n", resume_identity="fake-v1")
    writer = importlib.import_module("ocrllm.output.write_markdown_atomically")
    original = writer.write_markdown_atomically

    def fail_write(*_args, **_kwargs):
        from ocrllm import OutputError

        raise OutputError("test-only publication failure")

    monkeypatch.setattr(writer, "write_markdown_atomically", fail_write)
    with pytest.raises(OCRLLMError):
        recognize(source, config=_resume_config(provider, output_dir))
    assert provider.calls == 1

    monkeypatch.setattr(writer, "write_markdown_atomically", original)
    result = recognize(source, config=_resume_config(provider, output_dir))

    assert provider.calls == 1
    assert result.markdown == "# Resumable\n"


def test_injected_provider_without_resume_identity_is_rejected(tmp_path) -> None:
    source = write_test_image(tmp_path / "board.png")
    provider = _FixedResponseProvider("# Board\n")

    with pytest.raises(ConfigError) as failure:
        recognize(source, config=_resume_config(provider, tmp_path / "output"))

    assert "resume_identity" in str(failure.value)


def test_changed_injected_resume_identity_does_not_reuse_state(
    tmp_path,
    monkeypatch,
) -> None:
    import importlib

    source = write_test_image(tmp_path / "board.png")
    output_dir = tmp_path / "output"
    writer = importlib.import_module("ocrllm.output.write_markdown_atomically")
    original = writer.write_markdown_atomically

    def fail_write(*_args, **_kwargs):
        from ocrllm import OutputError

        raise OutputError("test-only publication failure")

    monkeypatch.setattr(writer, "write_markdown_atomically", fail_write)
    first = _FixedResponseProvider("# First\n", resume_identity="fake-v1")
    with pytest.raises(OCRLLMError):
        recognize(source, config=_resume_config(first, output_dir))

    monkeypatch.setattr(writer, "write_markdown_atomically", original)
    second = _FixedResponseProvider("# Second\n", resume_identity="fake-v2")
    with pytest.raises(OCRLLMError) as failure:
        recognize(source, config=_resume_config(second, output_dir))

    assert failure.value.code in {"RESUME_STATE_MISMATCH", "RESUME_STATE_INVALID"}


class _FailOneSourceProvider:
    """Fail exactly one named source so a batch can be resumed around it."""

    resume_identity = "fake-batch-v1"

    def __init__(self, failing_name: str | None) -> None:
        self.failing_name = failing_name
        self.seen: list[str] = []

    def recognize_images(self, image_paths, *, prompt, config):
        name = image_paths[0].name
        self.seen.append(name)
        if name == self.failing_name:
            raise ProviderError(
                "The provider request failed.",
                code="PROVIDER_UNAVAILABLE",
            )
        return f"# {name}\n"


def test_batch_resume_repays_only_the_failed_item(tmp_path) -> None:
    sources = [
        write_test_image(tmp_path / f"{index}.png", color=(0, index, 0))
        for index in range(3)
    ]
    output_dir = tmp_path / "output"
    failing = _FailOneSourceProvider("2.png")

    first_pass = recognize_batch(
        sources,
        config=Config(provider=failing, output_dir=output_dir, resume=True),
    )

    assert [outcome.succeeded for outcome in first_pass] == [True, True, False]

    recovered = _FailOneSourceProvider(None)
    second_pass = recognize_batch(
        sources,
        config=Config(provider=recovered, output_dir=output_dir, resume=True),
    )

    assert [outcome.succeeded for outcome in second_pass] == [True, True, True]
    assert recovered.seen == ["2.png"]
