"""Recognize independent requests in caller order."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING

from .batch_item_outcome import BatchItemOutcome
from .config import Config
from .errors import Cancelled, OCRLLMError

if TYPE_CHECKING:
    from concurrent.futures import Future, ThreadPoolExecutor

    from .output.output_target_claims import OutputTargetClaims
    from .providers.provider_request_start_gate import ProviderRequestStartGate
    from .result import RecognitionResult


_NOT_ATTEMPTED_MESSAGE = "Recognition batch stopped before this source was attempted."


def recognize_batch(
    sources: tuple[str | Path | Sequence[str | Path], ...],
    *,
    config: Config | None = None,
) -> list[BatchItemOutcome]:
    """Return one ordered outcome per source, never losing completed work.

    Execution stays fail-fast: the first failure aborts the start gate and no
    further source is dispatched. It is no longer destructive. Every source gets
    a ``BatchItemOutcome`` carrying either its ``RecognitionResult`` or its typed
    error, so work that was already produced and already paid for still reaches
    the caller alongside the failure. The complete tuple is validated before
    any item is dispatched.
    """
    from .output.output_target_claims import OutputTargetClaims
    from .preflight_recognition_batch import preflight_recognition_batch
    from .providers.provider_request_start_gate import (
        ProviderRequestStartGate,
        activate_provider_request_start_gate,
    )
    from .validate_config import validate_config

    cfg = validate_config(config)
    normalized_sources = preflight_recognition_batch(sources, config=cfg)
    gate = ProviderRequestStartGate(
        cfg.execution.provider_request_start_interval_seconds
    )
    with OutputTargetClaims() as output_claims:
        if cfg.execution.max_parallel_requests == 1:
            with activate_provider_request_start_gate(gate):
                return _recognize_batch_serially(
                    normalized_sources,
                    config=cfg,
                    gate=gate,
                    output_claims=output_claims,
                )
        return _recognize_batch_in_parallel(
            normalized_sources,
            config=cfg,
            gate=gate,
            output_claims=output_claims,
        )


def _recognize_batch_serially(
    sources: tuple[tuple[Path, ...], ...],
    *,
    config: Config,
    gate: ProviderRequestStartGate,
    output_claims: OutputTargetClaims,
) -> list[BatchItemOutcome]:
    """Recognize one source at a time, stopping after the first failure."""
    from .clear_public_error import clear_public_error
    from .recognize import _recognize

    outcomes: list[BatchItemOutcome] = []
    for index, source in enumerate(sources):
        try:
            outcomes.append(
                BatchItemOutcome(
                    index=index,
                    result=_recognize(
                        source,
                        config=config,
                        output_claims=output_claims,
                    ),
                )
            )
        except OCRLLMError as error:
            clear_public_error(error)
            gate.abort()
            outcomes.append(BatchItemOutcome(index=index, error=error))
            _append_not_attempted(outcomes, len(sources), first_index=index + 1)
            break
    return outcomes


def _recognize_batch_in_parallel(
    sources: tuple[tuple[Path, ...], ...],
    *,
    config: Config,
    gate: ProviderRequestStartGate,
    output_claims: OutputTargetClaims,
) -> list[BatchItemOutcome]:
    """Recognize with a bounded worker pool, settling every dispatched item."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    from .clear_public_error import clear_public_error

    outcomes: list[BatchItemOutcome | None] = []
    failed = False
    accepting_sources = True
    with ThreadPoolExecutor(
        max_workers=config.execution.max_parallel_requests,
        thread_name_prefix="ocrllm-recognition",
    ) as executor:
        future_indexes: dict[Future[RecognitionResult], int] = {}
        next_source_index = 0
        try:
            for _ in range(min(config.execution.max_parallel_requests, len(sources))):
                next_source_index = _submit_next_batch_item(
                    sources,
                    next_source_index,
                    executor=executor,
                    config=config,
                    gate=gate,
                    output_claims=output_claims,
                    outcomes=outcomes,
                    future_indexes=future_indexes,
                )
            accepting_sources = next_source_index < len(sources)

            while future_indexes and not failed:
                future = next(as_completed(tuple(future_indexes)))
                result_index = future_indexes.pop(future)
                try:
                    outcomes[result_index] = BatchItemOutcome(
                        index=result_index,
                        result=future.result(),
                    )
                except OCRLLMError as error:
                    clear_public_error(error)
                    outcomes[result_index] = BatchItemOutcome(
                        index=result_index,
                        error=error,
                    )
                    failed = True
                    continue
                if accepting_sources:
                    next_source_index = _submit_next_batch_item(
                        sources,
                        next_source_index,
                        executor=executor,
                        config=config,
                        gate=gate,
                        output_claims=output_claims,
                        outcomes=outcomes,
                        future_indexes=future_indexes,
                    )
                    accepting_sources = next_source_index < len(sources)
        except BaseException:
            gate.abort()
            for future in future_indexes:
                future.cancel()
            raise

        if failed:
            gate.abort()
            for future in future_indexes:
                future.cancel()
            _settle_dispatched_outcomes(future_indexes, outcomes)

    settled = [outcome for outcome in outcomes if outcome is not None]
    if len(settled) != len(outcomes):  # pragma: no cover - defensive.
        raise AssertionError("recognize_batch() left a dispatched item unsettled")
    if failed and accepting_sources:
        _append_not_attempted(settled, len(sources), first_index=len(settled))
    return settled


def _submit_next_batch_item(
    sources: tuple[tuple[Path, ...], ...],
    source_index: int,
    *,
    executor: ThreadPoolExecutor,
    config: Config,
    gate: ProviderRequestStartGate,
    output_claims: OutputTargetClaims,
    outcomes: list[BatchItemOutcome | None],
    future_indexes: dict[Future[RecognitionResult], int],
) -> int:
    """Submit at most one source so queued work never exceeds the worker bound."""
    source = sources[source_index]
    result_index = source_index
    outcomes.append(None)
    future = executor.submit(
        _recognize_batch_item,
        source,
        config=config,
        gate=gate,
        output_claims=output_claims,
    )
    future_indexes[future] = result_index
    return source_index + 1


def _recognize_batch_item(
    source: tuple[Path, ...],
    *,
    config: Config,
    gate: ProviderRequestStartGate,
    output_claims: OutputTargetClaims,
) -> RecognitionResult:
    """Run one batch item with the operation-wide provider start gate."""
    from .providers.provider_request_start_gate import (
        activate_provider_request_start_gate,
    )
    from .recognize import _recognize

    with activate_provider_request_start_gate(gate):
        return _recognize(
            source,
            config=config,
            output_claims=output_claims,
        )


def _settle_dispatched_outcomes(
    future_indexes: dict[Future[RecognitionResult], int],
    outcomes: list[BatchItemOutcome | None],
) -> None:
    """Settle calls that were already dispatched, and therefore already paid for."""
    from concurrent.futures import CancelledError

    from .clear_public_error import clear_public_error

    for future, result_index in future_indexes.items():
        try:
            outcomes[result_index] = BatchItemOutcome(
                index=result_index,
                result=future.result(),
            )
        except OCRLLMError as error:
            clear_public_error(error)
            outcomes[result_index] = BatchItemOutcome(index=result_index, error=error)
        except CancelledError:
            outcomes[result_index] = BatchItemOutcome(
                index=result_index,
                error=Cancelled(_NOT_ATTEMPTED_MESSAGE),
            )


def _append_not_attempted(
    outcomes: list[BatchItemOutcome],
    source_count: int,
    *,
    first_index: int,
) -> None:
    """Give every undispatched source an outcome so the caller order stays whole."""
    for next_index in range(first_index, source_count):
        outcomes.append(
            BatchItemOutcome(
                index=next_index,
                error=Cancelled(_NOT_ATTEMPTED_MESSAGE),
            )
        )
