"""Recognize independent requests in caller order."""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Sequence
from pathlib import Path
from typing import TYPE_CHECKING

from .batch_item_outcome import BatchItemOutcome
from .clear_public_error import clear_public_error
from .config import Config
from .errors import Cancelled, InvalidSource, OCRLLMError
from .output.output_target_claims import OutputTargetClaims
from .recognize import _recognize
from .validate_config import validate_config

if TYPE_CHECKING:
    from concurrent.futures import Future, ThreadPoolExecutor

    from .providers.provider_request_start_gate import ProviderRequestStartGate
    from .result import RecognitionResult


_NOT_ATTEMPTED_MESSAGE = "Recognition batch stopped before this source was attempted."
_SOURCE_ITERATION_FAILED_MESSAGE = "The batch source iterable could not be read."


def recognize_batch(
    sources: Iterable[str | Path | Sequence[str | Path]],
    *,
    config: Config | None = None,
) -> list[BatchItemOutcome]:
    """Return one ordered outcome per source, never losing completed work.

    Execution stays fail-fast: the first failure aborts the start gate and no
    further source is dispatched. It is no longer destructive. Every source gets
    a ``BatchItemOutcome`` carrying either its ``RecognitionResult`` or its typed
    error, so work that was already produced and already paid for still reaches
    the caller alongside the failure. If reading the iterable itself fails, one
    final typed outcome reports that terminal input position.
    """
    from .providers.provider_request_start_gate import (
        ProviderRequestStartGate,
        activate_provider_request_start_gate,
    )

    cfg = validate_config(config)
    try:
        source_iterator = iter(sources)
    except Exception:
        return [_source_iteration_failure(0)]
    gate = ProviderRequestStartGate(
        cfg.execution.provider_request_start_interval_seconds
    )
    with OutputTargetClaims() as output_claims:
        if cfg.execution.max_parallel_requests == 1:
            with activate_provider_request_start_gate(gate):
                return _recognize_batch_serially(
                    source_iterator,
                    config=cfg,
                    gate=gate,
                    output_claims=output_claims,
                )
        return _recognize_batch_in_parallel(
            source_iterator,
            config=cfg,
            gate=gate,
            output_claims=output_claims,
        )


def _recognize_batch_serially(
    source_iterator: Iterator[str | Path | Sequence[str | Path]],
    *,
    config: Config,
    gate: ProviderRequestStartGate,
    output_claims: OutputTargetClaims,
) -> list[BatchItemOutcome]:
    """Recognize one source at a time, stopping after the first failure."""
    outcomes: list[BatchItemOutcome] = []
    index = 0
    while True:
        try:
            source = next(source_iterator)
        except StopIteration:
            break
        except Exception:
            outcomes.append(_source_iteration_failure(index))
            break
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
            _append_not_attempted(outcomes, source_iterator, first_index=index + 1)
            break
        index += 1
    return outcomes


def _recognize_batch_in_parallel(
    source_iterator: Iterator[str | Path | Sequence[str | Path]],
    *,
    config: Config,
    gate: ProviderRequestStartGate,
    output_claims: OutputTargetClaims,
) -> list[BatchItemOutcome]:
    """Recognize with a bounded worker pool, settling every dispatched item."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    outcomes: list[BatchItemOutcome | None] = []
    failed = False
    accepting_sources = True
    with ThreadPoolExecutor(
        max_workers=config.execution.max_parallel_requests,
        thread_name_prefix="ocrllm-recognition",
    ) as executor:
        future_indexes: dict[Future[RecognitionResult], int] = {}
        try:
            for _ in range(config.execution.max_parallel_requests):
                if not _submit_next_batch_item(
                    source_iterator,
                    executor=executor,
                    config=config,
                    gate=gate,
                    output_claims=output_claims,
                    outcomes=outcomes,
                    future_indexes=future_indexes,
                ):
                    accepting_sources = False
                    break

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
                    accepting_sources = _submit_next_batch_item(
                        source_iterator,
                        executor=executor,
                        config=config,
                        gate=gate,
                        output_claims=output_claims,
                        outcomes=outcomes,
                        future_indexes=future_indexes,
                    )
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
        _append_not_attempted(settled, source_iterator, first_index=len(settled))
    return settled


def _submit_next_batch_item(
    source_iterator: Iterator[str | Path | Sequence[str | Path]],
    *,
    executor: ThreadPoolExecutor,
    config: Config,
    gate: ProviderRequestStartGate,
    output_claims: OutputTargetClaims,
    outcomes: list[BatchItemOutcome | None],
    future_indexes: dict[Future[RecognitionResult], int],
) -> bool:
    """Submit at most one source so queued work never exceeds the worker bound."""
    try:
        source = next(source_iterator)
    except StopIteration:
        return False
    except Exception:
        outcomes.append(_source_iteration_failure(len(outcomes)))
        return False

    result_index = len(outcomes)
    outcomes.append(None)
    future = executor.submit(
        _recognize_batch_item,
        source,
        config=config,
        gate=gate,
        output_claims=output_claims,
    )
    future_indexes[future] = result_index
    return True


def _recognize_batch_item(
    source: str | Path | Sequence[str | Path],
    *,
    config: Config,
    gate: ProviderRequestStartGate,
    output_claims: OutputTargetClaims,
) -> RecognitionResult:
    """Run one batch item with the operation-wide provider start gate."""
    from .providers.provider_request_start_gate import (
        activate_provider_request_start_gate,
    )

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
    for future, result_index in future_indexes.items():
        try:
            outcomes[result_index] = BatchItemOutcome(
                index=result_index,
                result=future.result(),
            )
        except OCRLLMError as error:
            clear_public_error(error)
            outcomes[result_index] = BatchItemOutcome(index=result_index, error=error)
        except BaseException:
            outcomes[result_index] = BatchItemOutcome(
                index=result_index,
                error=Cancelled(_NOT_ATTEMPTED_MESSAGE),
            )


def _append_not_attempted(
    outcomes: list[BatchItemOutcome],
    source_iterator: Iterator[str | Path | Sequence[str | Path]],
    *,
    first_index: int,
) -> None:
    """Give every undispatched source an outcome so the caller order stays whole."""
    next_index = first_index
    while True:
        try:
            next(source_iterator)
        except StopIteration:
            return
        except Exception:
            outcomes.append(_source_iteration_failure(next_index))
            return
        outcomes.append(
            BatchItemOutcome(
                index=next_index,
                error=Cancelled(_NOT_ATTEMPTED_MESSAGE),
            )
        )
        next_index += 1


def _source_iteration_failure(index: int) -> BatchItemOutcome:
    """Return a secret-safe terminal outcome for a broken source iterable."""
    return BatchItemOutcome(
        index=index,
        error=InvalidSource(_SOURCE_ITERATION_FAILED_MESSAGE),
    )
