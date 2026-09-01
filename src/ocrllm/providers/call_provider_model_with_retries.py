"""Apply one ProviderModel's finite retry rules around one provider call."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import TypeVar

from ..errors import NoSpeechDetected, OCRLLMError, ProviderError
from ..provider_failure_evidence import (
    provider_cleanup_failed,
    provider_failure_usage,
)
from .provider_model import ProviderModel
from .provider_model_call_result import ProviderModelCallResult


_ResponseT = TypeVar("_ResponseT")


def call_provider_model_with_retries(
    provider: ProviderModel,
    call: Callable[[], _ResponseT],
) -> ProviderModelCallResult[_ResponseT]:
    """Return one final response plus every finite attempt spent to obtain it."""
    if type(provider) is not ProviderModel or not callable(call):
        raise TypeError("provider retry execution requires exact inputs") from None

    attempts = 0
    total_calls = 0
    total_input_tokens: int | None = 0
    total_output_tokens: int | None = 0
    cleanup_failed = False
    while True:
        attempts += 1
        try:
            response = call()
            return ProviderModelCallResult(
                response=response,
                calls=total_calls + 1,
                failed_input_tokens=total_input_tokens,
                failed_output_tokens=total_output_tokens,
                prior_cleanup_failed=cleanup_failed,
            )
        except NoSpeechDetected as error:
            _attach_attempt_evidence(
                error,
                previous_calls=total_calls,
                previous_input_tokens=total_input_tokens,
                previous_output_tokens=total_output_tokens,
                previous_cleanup_failed=cleanup_failed,
            )
            raise
        except ProviderError as error:
            calls, input_tokens, output_tokens = provider_failure_usage(error)
            total_calls += calls
            total_input_tokens = _add_known(total_input_tokens, input_tokens)
            total_output_tokens = _add_known(total_output_tokens, output_tokens)
            cleanup_failed = cleanup_failed or provider_cleanup_failed(error)
            rule = provider.retry_rules.get(error.code)
            if rule is None or calls == 0:
                _attach_aggregate_error(
                    error,
                    calls=total_calls,
                    input_tokens=total_input_tokens,
                    output_tokens=total_output_tokens,
                    cleanup_failed=cleanup_failed,
                )
                raise
            _label, extra_retries, wait_seconds = rule
            if attempts > extra_retries:
                _attach_aggregate_error(
                    error,
                    calls=total_calls,
                    input_tokens=total_input_tokens,
                    output_tokens=total_output_tokens,
                    cleanup_failed=cleanup_failed,
                )
                raise
            if wait_seconds:
                time.sleep(wait_seconds)
        except OCRLLMError:
            raise


def _attach_attempt_evidence(
    error: OCRLLMError,
    *,
    previous_calls: int,
    previous_input_tokens: int | None,
    previous_output_tokens: int | None,
    previous_cleanup_failed: bool,
) -> None:
    calls, input_tokens, output_tokens = provider_failure_usage(error)
    _attach_aggregate_error(
        error,
        calls=previous_calls + calls,
        input_tokens=_add_known(previous_input_tokens, input_tokens),
        output_tokens=_add_known(previous_output_tokens, output_tokens),
        cleanup_failed=previous_cleanup_failed or provider_cleanup_failed(error),
    )


def _attach_aggregate_error(
    error: OCRLLMError,
    *,
    calls: int,
    input_tokens: int | None,
    output_tokens: int | None,
    cleanup_failed: bool,
) -> None:
    error._add_safe_detail("provider_calls_attempted", calls)
    error._add_safe_detail("input_tokens", input_tokens)
    error._add_safe_detail("output_tokens", output_tokens)
    if cleanup_failed:
        error._add_safe_detail("provider_cleanup_failed", True)


def _add_known(left: int | None, right: int | None) -> int | None:
    return left + right if left is not None and right is not None else None
