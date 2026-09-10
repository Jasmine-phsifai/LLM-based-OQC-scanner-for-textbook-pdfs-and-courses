"""Observe actual compatible HTTP boundaries through existing retry execution."""
from contextlib import contextmanager
import time
import uuid
from .observation_context import _OBSERVER, _FIELDS, _ATTEMPT, _now, emit


def mark_http_started():
    attempt = _ATTEMPT.get()
    if attempt is not None:
        attempt.update(started_at=_now(), clock=time.monotonic())
        emit('attempt_started', **{key: value for key, value in attempt.items() if key != 'clock'},
             attempt_layer='client_http')


def mark_request_id(request_id):
    attempt = _ATTEMPT.get()
    if attempt is not None and request_id is not None:
        attempt['request_id'] = request_id


@contextmanager
def observed_provider_attempt(provider):
    if _OBSERVER.get() is None or provider.adapter_id != 'openai_compatible_chat':
        yield None
        return
    attempt = {'attempt_id': uuid.uuid4().hex, 'model': provider.model, 'vendor': provider.vendor}
    token = _ATTEMPT.set(attempt)
    status, error, no_speech = 'success', None, False
    try:
        yield attempt
    except BaseException as caught:
        from .errors import NoSpeechDetected
        error = caught
        no_speech = isinstance(caught, NoSpeechDetected)
        status = 'success' if no_speech else 'failed' if isinstance(caught, Exception) else 'cancelled'
        raise
    finally:
        if 'clock' in attempt:
            details = getattr(error, 'details', {})
            data = {key: value for key, value in attempt.items() if key != 'clock'}
            data.update(finished_at=_now(), elapsed_seconds=time.monotonic()-attempt['clock'],
                        status=status, attempt_layer='client_http', no_speech=no_speech,
                        valid_units=_FIELDS.get().get('planned_units') if status == 'success' else 0,
                        acceptance='provider_validation', model_execution_count=None)
            for key in ('request_id', 'provider_code', 'reason', 'input_tokens', 'output_tokens'):
                if key in details:
                    data[key] = details[key]
            if error is not None and not no_speech:
                data.update(error_code=getattr(error, 'code', None),
                            exception_type=type(error).__name__, error_layer='ocrllm_provider')
            emit('attempt_finished', **data)
        elif error is not None:
            emit('error', error_code=getattr(error, 'code', None), error_layer='before_http',
                 exception_type=type(error).__name__, model=provider.model)
        _ATTEMPT.reset(token)
