from __future__ import annotations

import importlib
import threading
import time

import pytest

from ocrllm import (
    Config,
    RecognitionExecutionPolicy,
    RecognitionPreferences,
    recognize,
    recognize_batch,
)
from ocrllm.errors import ProviderError

from write_test_image import write_test_image


class BlockingProvider:
    def __init__(self, expected_parallel: int) -> None:
        self._expected_parallel = expected_parallel
        self._lock = threading.Lock()
        self._release = threading.Event()
        self.active = 0
        self.maximum_active = 0
        self.names: list[str] = []

    def recognize_images(self, image_paths, *, prompt, config):
        name = image_paths[0].name
        with self._lock:
            self.active += 1
            self.maximum_active = max(self.maximum_active, self.active)
            self.names.append(name)
            if self.active == self._expected_parallel:
                self._release.set()
        try:
            if not self._release.wait(timeout=5):
                raise RuntimeError("parallel recognition did not overlap")
            return f"# {name}\n"
        finally:
            with self._lock:
                self.active -= 1


class TimedProvider:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.started_at: list[float] = []

    def recognize_images(self, image_paths, *, prompt, config):
        with self._lock:
            self.started_at.append(time.monotonic())
        return f"# {image_paths[0].name}\n"


class ImmediateFailureProvider:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.call_count = 0

    def recognize_images(self, image_paths, *, prompt, config):
        with self._lock:
            self.call_count += 1
        raise ProviderError(
            "The first provider request failed.",
            code="PROVIDER_UNAVAILABLE",
        )


class NumberedProvider:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.calls = 0

    def recognize_images(self, image_paths, *, prompt, config):
        with self._lock:
            self.calls += 1
            call_number = self.calls
        return f"# Result {call_number}\n"


def _colliding_sources(tmp_path):
    return [
        write_test_image(tmp_path / directory / "same.png", color=color)
        for directory, color in (("first", (1, 0, 0)), ("second", (2, 0, 0)))
    ]


def test_serial_batch_reserves_colliding_overwrite_target_until_batch_ends(tmp_path):
    sources = _colliding_sources(tmp_path)
    output_dir = tmp_path / "output"
    provider = NumberedProvider()

    outcomes = recognize_batch(
        sources,
        config=Config(provider=provider, output_dir=output_dir, overwrite=True),
    )

    assert provider.calls == 1
    assert outcomes[0].succeeded
    assert outcomes[1].error.code == "OUTPUT_EXISTS"
    assert (output_dir / "same_board.md").read_text(encoding="utf-8") == (
        "# Result 1\n"
    )
    assert outcomes[1].error.__cause__ is None
    assert outcomes[1].error.__context__ is None
    assert outcomes[1].error.__traceback__ is None

    standalone = recognize(
        sources[1],
        config=Config(provider=provider, output_dir=output_dir, overwrite=True),
    )

    assert provider.calls == 2
    assert standalone.markdown == "# Result 2\n"
    assert standalone.output_path.read_text(encoding="utf-8") == standalone.markdown


def test_parallel_batch_reserves_target_after_first_item_finishes(
    tmp_path,
    monkeypatch,
):
    sources = _colliding_sources(tmp_path)
    output_dir = tmp_path / "output"
    provider = NumberedProvider()
    batch_module = importlib.import_module("ocrllm.recognize_batch")
    real_batch_item = batch_module._recognize_batch_item
    first_finished = threading.Event()

    def run_first_item_before_second(source, **kwargs):
        if source.parent.name == "second":
            assert first_finished.wait(timeout=5)
            return real_batch_item(source, **kwargs)
        try:
            return real_batch_item(source, **kwargs)
        finally:
            first_finished.set()

    monkeypatch.setattr(
        batch_module,
        "_recognize_batch_item",
        run_first_item_before_second,
    )

    outcomes = recognize_batch(
        sources,
        config=Config(
            provider=provider,
            output_dir=output_dir,
            overwrite=True,
            execution=RecognitionExecutionPolicy(max_parallel_requests=2),
        ),
    )

    assert provider.calls == 1
    assert [outcome.succeeded for outcome in outcomes] == [True, False]
    assert outcomes[1].error.code == "OUTPUT_EXISTS"
    assert (output_dir / "same_board.md").read_text(encoding="utf-8") == (
        outcomes[0].result.markdown
    )


def test_parallel_batch_is_bounded_and_returns_caller_order(tmp_path):
    sources = [
        write_test_image(tmp_path / f"{index}.png", color=(index, 0, 0))
        for index in range(4)
    ]
    provider = BlockingProvider(expected_parallel=2)
    config = Config(
        provider=provider,
        execution=RecognitionExecutionPolicy(max_parallel_requests=2),
    )

    outcomes = recognize_batch(sources, config=config)

    assert provider.maximum_active == 2
    assert sorted(provider.names) == sorted(path.name for path in sources)
    assert [outcome.result.markdown.strip() for outcome in outcomes] == [
        f"# {path.name}" for path in sources
    ]


def test_provider_start_interval_covers_every_parallel_workflow_call(tmp_path):
    sources = [
        write_test_image(tmp_path / f"{index}.png", color=(0, index, 0))
        for index in range(2)
    ]
    provider = TimedProvider()
    configured_interval = 0.04
    config = Config(
        provider=provider,
        execution=RecognitionExecutionPolicy(
            max_parallel_requests=2,
            provider_request_start_interval_seconds=configured_interval,
        ),
        preferences=RecognitionPreferences(review_passes=1),
    )

    outcomes = recognize_batch(sources, config=config)

    assert len(outcomes) == 2
    assert len(provider.started_at) == 4
    observed_intervals = [
        later - earlier
        for earlier, later in zip(provider.started_at, provider.started_at[1:])
    ]
    assert all(interval >= configured_interval - 0.005 for interval in observed_intervals)


def test_direct_recognition_applies_interval_between_draft_and_review(tmp_path):
    source = write_test_image(tmp_path / "board.png")
    provider = TimedProvider()
    configured_interval = 0.03
    config = Config(
        provider=provider,
        execution=RecognitionExecutionPolicy(
            provider_request_start_interval_seconds=configured_interval,
        ),
        preferences=RecognitionPreferences(review_passes=1),
    )

    recognize(source, config=config)

    assert len(provider.started_at) == 2
    assert provider.started_at[1] - provider.started_at[0] >= configured_interval - 0.005


def test_empty_parallel_batch_returns_without_provider_work():
    provider = TimedProvider()
    config = Config(
        provider=provider,
        execution=RecognitionExecutionPolicy(max_parallel_requests=2),
    )

    assert recognize_batch([], config=config) == []
    assert provider.started_at == []


def test_parallel_failure_aborts_provider_calls_still_waiting_for_the_gate(tmp_path):
    sources = [
        write_test_image(tmp_path / f"{index}.png", color=(0, 0, index))
        for index in range(4)
    ]
    provider = ImmediateFailureProvider()
    config = Config(
        provider=provider,
        execution=RecognitionExecutionPolicy(
            max_parallel_requests=4,
            provider_request_start_interval_seconds=0.5,
        ),
    )

    outcomes = recognize_batch(sources, config=config)

    codes = [outcome.error.code for outcome in outcomes]
    assert len(outcomes) == 4
    assert codes.count("PROVIDER_UNAVAILABLE") == 1
    assert codes.count("CANCELLED") == 3
    assert provider.call_count == 1
