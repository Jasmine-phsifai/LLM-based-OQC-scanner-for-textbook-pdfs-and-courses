from __future__ import annotations

import concurrent.futures
import importlib
import threading
import time
from collections.abc import Sequence

import pytest

from ocrllm import (
    Config,
    RecognitionExecutionPolicy,
    RecognitionPreferences,
    recognize,
    recognize_batch,
)
from ocrllm.errors import (
    ConfigError,
    InvalidSource,
    OCRLLMError,
    OutputExists,
    ProviderError,
    ProviderUnavailable,
    ResumeStateError,
)

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
            self.started_at.append(time.perf_counter())
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


class StructuredFailureProvider:
    def __init__(self) -> None:
        self.names: list[str] = []

    def recognize_images(self, image_paths, *, prompt, config):
        name = image_paths[0].name
        self.names.append(name)
        if name == "failure.png":
            raise ProviderUnavailable(details={"failure_scope": "provider"})
        return f"# {name}\n"


class NumberedProvider:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.calls = 0
        self.groups: list[tuple[str, ...]] = []

    def recognize_images(self, image_paths, *, prompt, config):
        with self._lock:
            self.calls += 1
            call_number = self.calls
            self.groups.append(tuple(path.name for path in image_paths))
        return f"# Result {call_number}\n"


class CustomInnerSources(Sequence):
    def __init__(self, sources):
        self.sources = tuple(sources)

    def __len__(self):
        return len(self.sources)

    def __getitem__(self, index):
        return self.sources[index]


def _colliding_sources(tmp_path):
    return [
        write_test_image(tmp_path / directory / "same.png", color=color)
        for directory, color in (("first", (1, 0, 0)), ("second", (2, 0, 0)))
    ]


def test_batch_accepts_one_exact_tuple_and_preserves_order(tmp_path):
    sources = tuple(
        write_test_image(tmp_path / f"{index}.png", color=(index, 0, 0))
        for index in range(2)
    )
    provider = NumberedProvider()

    outcomes = recognize_batch(sources, config=Config(provider=provider))

    assert provider.calls == 2
    assert [outcome.succeeded for outcome in outcomes] == [True, True]


def test_pre_cancelled_image_batch_creates_no_output_or_temp_directories(tmp_path):
    source = write_test_image(tmp_path / "source.png")
    output_dir = tmp_path / "output"
    temp_dir = tmp_path / "temp"
    cancellation = threading.Event()
    cancellation.set()
    provider = NumberedProvider()

    outcomes = recognize_batch(
        (source,),
        config=Config(
            provider=provider,
            cancellation=cancellation,
            output_dir=output_dir,
            temp_dir=temp_dir,
        ),
    )

    assert len(outcomes) == 1
    assert outcomes[0].error is not None
    assert outcomes[0].error.code == "CANCELLED"
    assert outcomes[0].error.details["provider_calls_attempted"] == 0
    assert provider.calls == 0
    assert not output_dir.exists()
    assert not temp_dir.exists()


def test_pre_cancelled_image_batch_does_not_read_missing_source(tmp_path):
    source = tmp_path / "missing.png"
    output_dir = tmp_path / "output"
    temp_dir = tmp_path / "temp"
    cancellation = threading.Event()
    cancellation.set()
    provider = NumberedProvider()

    outcomes = recognize_batch(
        (source,),
        config=Config(
            provider=provider,
            cancellation=cancellation,
            output_dir=output_dir,
            temp_dir=temp_dir,
        ),
    )

    assert len(outcomes) == 1
    assert outcomes[0].error is not None
    assert outcomes[0].error.code == "CANCELLED"
    assert outcomes[0].error.details["provider_calls_attempted"] == 0
    assert provider.calls == 0
    assert not output_dir.exists()
    assert not temp_dir.exists()


@pytest.mark.parametrize(
    "build_sources",
    (
        lambda source: [source],
        lambda source: (item for item in (source,)),
    ),
)
def test_batch_rejects_non_tuple_outer_container_before_provider_or_output(
    tmp_path,
    build_sources,
):
    source = write_test_image(tmp_path / "source.png")
    output_dir = tmp_path / "output"
    temp_dir = tmp_path / "temp"
    provider = NumberedProvider()

    with pytest.raises(InvalidSource):
        recognize_batch(
            build_sources(source),
            config=Config(
                provider=provider,
                output_dir=output_dir,
                temp_dir=temp_dir,
            ),
        )

    assert provider.calls == 0
    assert not output_dir.exists()
    assert not temp_dir.exists()


@pytest.mark.parametrize(
    ("provider", "expected_code"),
    (
        (None, "CONFIG_MISSING"),
        (object(), "CONFIG_INVALID"),
    ),
)
def test_batch_preflights_invalid_image_provider_before_output_work(
    tmp_path,
    provider,
    expected_code,
):
    source = write_test_image(tmp_path / "source.png")
    output_dir = tmp_path / "output"
    temp_dir = tmp_path / "temp"
    cancellation = threading.Event()
    cancellation.set()

    with pytest.raises(ConfigError) as caught:
        recognize_batch(
            (source,),
            config=Config(
                provider=provider,
                cancellation=cancellation,
                output_dir=output_dir,
                temp_dir=temp_dir,
            ),
        )

    assert caught.value.code == expected_code
    assert not output_dir.exists()
    assert not temp_dir.exists()


def test_batch_rejects_custom_sequence_before_provider_or_output(tmp_path):
    source = write_test_image(tmp_path / "source.png")
    output_dir = tmp_path / "output"
    provider = NumberedProvider()

    class CustomSources(Sequence):
        def __len__(self):
            return 1

        def __getitem__(self, index):
            if index == 0:
                return source
            raise IndexError

    with pytest.raises(InvalidSource):
        recognize_batch(
            CustomSources(),
            config=Config(provider=provider, output_dir=output_dir),
        )

    assert provider.calls == 0
    assert not output_dir.exists()


@pytest.mark.parametrize(
    "group_factory",
    (
        lambda sources: list(sources),
        lambda sources: CustomInnerSources(sources),
    ),
)
def test_batch_preserves_supported_sequence_group_items(
    tmp_path,
    group_factory,
):
    first = write_test_image(tmp_path / "first.png")
    second = write_test_image(tmp_path / "second.png")
    provider = NumberedProvider()

    outcomes = recognize_batch(
        (group_factory((first, second)),),
        config=Config(provider=provider),
    )

    assert provider.calls == 1
    assert provider.groups == [("first.png", "second.png")]
    assert len(outcomes) == 1
    assert outcomes[0].succeeded is True


def test_batch_rejects_tuple_subclass_before_provider_or_output(tmp_path):
    source = write_test_image(tmp_path / "source.png")
    output_dir = tmp_path / "output"
    temp_dir = tmp_path / "temp"
    provider = NumberedProvider()

    class BatchTuple(tuple):
        pass

    with pytest.raises(InvalidSource):
        recognize_batch(
            BatchTuple((source,)),
            config=Config(
                provider=provider,
                output_dir=output_dir,
                temp_dir=temp_dir,
            ),
        )

    assert provider.calls == 0
    assert not output_dir.exists()
    assert not temp_dir.exists()


def test_batch_rejects_non_path_group_member_before_provider_or_output(tmp_path):
    source = write_test_image(tmp_path / "source.png")
    output_dir = tmp_path / "output"
    provider = NumberedProvider()
    cancellation = threading.Event()
    cancellation.set()

    with pytest.raises(InvalidSource):
        recognize_batch(
            ((source, 7),),
            config=Config(
                provider=provider,
                cancellation=cancellation,
                output_dir=output_dir,
            ),
        )

    assert provider.calls == 0
    assert not output_dir.exists()


def test_batch_preflights_colliding_targets_before_any_call_or_output(tmp_path):
    sources = tuple(_colliding_sources(tmp_path))
    output_dir = tmp_path / "output"
    temp_dir = tmp_path / "temp"
    provider = NumberedProvider()

    with pytest.raises(OutputExists) as caught:
        recognize_batch(
            sources,
            config=Config(
                provider=provider,
                output_dir=output_dir,
                temp_dir=temp_dir,
                overwrite=True,
            ),
        )
    assert caught.value.code == "OUTPUT_EXISTS"
    assert provider.calls == 0
    assert not output_dir.exists()
    assert not temp_dir.exists()


def test_batch_preflights_existing_target_before_any_call_or_temp_work(tmp_path):
    first = write_test_image(tmp_path / "first.png")
    second = write_test_image(tmp_path / "second.png")
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    existing_target = output_dir / "second_board.md"
    existing_target.write_text("original", encoding="utf-8")
    temp_dir = tmp_path / "temp"
    provider = NumberedProvider()

    with pytest.raises(OutputExists) as caught:
        recognize_batch(
            (first, second),
            config=Config(
                provider=provider,
                output_dir=output_dir,
                temp_dir=temp_dir,
            ),
        )

    assert caught.value.code == "OUTPUT_EXISTS"
    assert provider.calls == 0
    assert existing_target.read_text(encoding="utf-8") == "original"
    assert not (output_dir / "first_board.md").exists()
    assert not temp_dir.exists()


def test_batch_preflights_later_missing_source_before_any_call_or_output(tmp_path):
    first = write_test_image(tmp_path / "first.png")
    missing = tmp_path / "missing.png"
    output_dir = tmp_path / "output"
    temp_dir = tmp_path / "temp"
    provider = NumberedProvider()

    with pytest.raises(InvalidSource) as caught:
        recognize_batch(
            (first, missing),
            config=Config(
                provider=provider,
                output_dir=output_dir,
                temp_dir=temp_dir,
            ),
        )
    assert caught.value.code == "SOURCE_NOT_FOUND"
    assert provider.calls == 0
    assert not output_dir.exists()
    assert not temp_dir.exists()


def test_batch_preflights_later_corrupt_image_before_any_call_or_output(tmp_path):
    first = write_test_image(tmp_path / "first.png")
    corrupt = tmp_path / "corrupt.png"
    corrupt.write_bytes(b"not an image")
    output_dir = tmp_path / "output"
    temp_dir = tmp_path / "temp"
    provider = NumberedProvider()

    with pytest.raises(InvalidSource) as caught:
        recognize_batch(
            (first, corrupt),
            config=Config(
                provider=provider,
                output_dir=output_dir,
                temp_dir=temp_dir,
            ),
        )

    assert caught.value.code == "SOURCE_INVALID"
    assert provider.calls == 0
    assert not output_dir.exists()
    assert not temp_dir.exists()


@pytest.mark.parametrize("later_state_bytes", (None, b"{"))
def test_batch_preflights_every_later_resume_sidecar_before_any_call(
    tmp_path,
    later_state_bytes,
):
    first = write_test_image(tmp_path / "first.png")
    later = write_test_image(tmp_path / "later.png")
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    later_output = output_dir / "later_board.md"
    later_output.write_text("original", encoding="utf-8")
    if later_state_bytes is not None:
        (output_dir / "later_board.ocrllm-state.json").write_bytes(
            later_state_bytes
        )
    temp_dir = tmp_path / "temp"
    provider = NumberedProvider()
    provider.resume_identity = "batch-preflight-v1"

    with pytest.raises(ResumeStateError) as caught:
        recognize_batch(
            (first, later),
            config=Config(
                provider=provider,
                output_dir=output_dir,
                temp_dir=temp_dir,
                resume=True,
            ),
        )

    assert caught.value.code == "RESUME_STATE_INVALID"
    assert provider.calls == 0
    assert later_output.read_text(encoding="utf-8") == "original"
    assert not (output_dir / "first_board.md").exists()
    assert not (output_dir / "first_board.ocrllm-state.json").exists()
    assert not temp_dir.exists()


def test_serial_batch_preserves_paid_failure_details_without_copying_to_siblings(
    tmp_path,
):
    sources = tuple(
        write_test_image(tmp_path / name)
        for name in ("success.png", "failure.png", "never.png")
    )
    provider = StructuredFailureProvider()

    outcomes = recognize_batch(sources, config=Config(provider=provider))

    assert provider.names == ["success.png", "failure.png"]
    assert [outcome.succeeded for outcome in outcomes] == [True, False, False]
    assert outcomes[0].result.markdown == "# success.png\n"

    failure = outcomes[1].error
    assert failure.code == "PROVIDER_UNAVAILABLE"
    assert failure.retryable is True
    assert dict(failure.details) == {
        "failed_model": None,
        "failure_scope": "provider",
        "model_attempts": (
            {
                "disposition": "retry",
                "model": "",
                "outcome": "PROVIDER_UNAVAILABLE",
                "provider_calls_attempted": 1,
            },
        ),
        "provider_calls_attempted": 1,
        "workflow_pass": "draft",
    }
    assert failure.__cause__ is None
    assert failure.__context__ is None
    assert failure.__traceback__ is None

    cancelled = outcomes[2].error
    assert cancelled.code == "CANCELLED"
    assert cancelled.details == {}
    assert cancelled.__cause__ is None
    assert cancelled.__context__ is None
    assert cancelled.__traceback__ is None


def test_parallel_batch_is_bounded_and_returns_caller_order(tmp_path):
    sources = tuple(
        write_test_image(tmp_path / f"{index}.png", color=(index, 0, 0))
        for index in range(4)
    )
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
    sources = tuple(
        write_test_image(tmp_path / f"{index}.png", color=(0, index, 0))
        for index in range(2)
    )
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

    assert recognize_batch((), config=config) == []
    assert provider.started_at == []


def test_parallel_failure_aborts_provider_calls_still_waiting_for_the_gate(tmp_path):
    sources = tuple(
        write_test_image(tmp_path / f"{index}.png", color=(0, 0, index))
        for index in range(4)
    )
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
    paid_failure = next(
        outcome.error
        for outcome in outcomes
        if outcome.error.code == "PROVIDER_UNAVAILABLE"
    )
    assert paid_failure.details["workflow_pass"] == "draft"
    assert paid_failure.details["provider_calls_attempted"] == 1
    assert len(paid_failure.details["model_attempts"]) == 1
    for outcome in outcomes:
        if outcome.error.code != "CANCELLED":
            continue
        assert outcome.error.details.get("provider_calls_attempted", 0) == 0
        assert "model_attempts" not in outcome.error.details


def test_parallel_batch_aborts_gate_before_main_observes_worker_failure(
    tmp_path,
    monkeypatch,
):
    sources = tuple(
        write_test_image(tmp_path / f"{index}.png", color=(0, index, 0))
        for index in range(4)
    )
    provider_lock = threading.Lock()
    initial_calls_started = threading.Barrier(2)
    provider_call_count = 0

    class CoordinatedProvider:
        def recognize_images(self, image_paths, *, prompt, config):
            nonlocal provider_call_count
            with provider_lock:
                call_index = provider_call_count
                provider_call_count += 1
            if call_index < 2:
                initial_calls_started.wait(timeout=5)
            if call_index == 1:
                raise ProviderError(
                    "The coordinated provider request failed.",
                    code="PROVIDER_UNAVAILABLE",
                )
            return f"# {image_paths[0].name}\n"

    initial_futures = set()
    failed_future = None

    def deliver_success_before_already_completed_failure(futures, timeout=None):
        nonlocal failed_future
        current_futures = tuple(futures)
        if not initial_futures:
            _, pending = concurrent.futures.wait(current_futures, timeout=5)
            assert not pending
            initial_futures.update(current_futures)
            failed_future = next(
                future
                for future in current_futures
                if isinstance(future.exception(), ProviderError)
            )
            yield next(future for future in current_futures if future is not failed_future)
            return

        later_future = next(
            future for future in current_futures if future not in initial_futures
        )
        try:
            later_future.result(timeout=5)
        except OCRLLMError:
            pass
        assert failed_future is not None
        yield failed_future

    monkeypatch.setattr(
        concurrent.futures,
        "as_completed",
        deliver_success_before_already_completed_failure,
    )

    outcomes = recognize_batch(
        sources,
        config=Config(
            provider=CoordinatedProvider(),
            execution=RecognitionExecutionPolicy(max_parallel_requests=2),
        ),
    )

    assert provider_call_count == 2
    assert [outcome.index for outcome in outcomes] == [0, 1, 2, 3]
    assert sum(outcome.succeeded for outcome in outcomes[:2]) == 1
    assert sorted(
        outcome.error.code
        for outcome in outcomes[:2]
        if outcome.error is not None
    ) == ["PROVIDER_UNAVAILABLE"]
    assert [outcome.error.code for outcome in outcomes[2:]] == [
        "CANCELLED",
        "CANCELLED",
    ]


@pytest.mark.parametrize("process_exception_type", [KeyboardInterrupt, SystemExit])
def test_parallel_settlement_propagates_process_control_from_running_item(
    tmp_path,
    monkeypatch,
    process_exception_type,
):
    sources = (
        write_test_image(tmp_path / "failure.png"),
        write_test_image(tmp_path / "process-control.png"),
    )
    process_call_started = threading.Event()
    settlement_started = threading.Event()
    process_exception_raised = threading.Event()
    process_exception = process_exception_type("process-control-sentinel")

    class CoordinatedProvider:
        def recognize_images(self, image_paths, *, prompt, config):
            if image_paths[0].name == "failure.png":
                assert process_call_started.wait(timeout=5)
                raise ProviderError(
                    "The first provider request failed.",
                    code="PROVIDER_UNAVAILABLE",
                )

            process_call_started.set()
            assert settlement_started.wait(timeout=5)
            process_exception_raised.set()
            raise process_exception

    batch_module = importlib.import_module("ocrllm.recognize_batch")
    real_settle = batch_module._settle_dispatched_outcomes

    def signal_settlement(*args, **kwargs):
        settlement_started.set()
        return real_settle(*args, **kwargs)

    monkeypatch.setattr(
        batch_module,
        "_settle_dispatched_outcomes",
        signal_settlement,
    )

    with pytest.raises(process_exception_type) as captured:
        recognize_batch(
            sources,
            config=Config(
                provider=CoordinatedProvider(),
                execution=RecognitionExecutionPolicy(max_parallel_requests=2),
            ),
        )

    assert captured.value is process_exception
    assert process_exception_raised.is_set()


def test_parallel_settlement_marks_cancelled_future_as_not_attempted():
    from concurrent.futures import Future

    batch_module = importlib.import_module("ocrllm.recognize_batch")
    cancelled_future = Future()
    assert cancelled_future.cancel()
    outcomes = [None]

    batch_module._settle_dispatched_outcomes({cancelled_future: 0}, outcomes)

    assert outcomes[0].index == 0
    assert outcomes[0].error.code == "CANCELLED"
