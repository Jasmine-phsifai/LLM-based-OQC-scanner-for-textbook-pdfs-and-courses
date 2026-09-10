"""Opt-in owner JSONL observations; emission never controls recognition."""
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
from threading import Lock
import uuid

_OBSERVER = ContextVar('ocrllm_observer', default=None)
_FIELDS = ContextVar('ocrllm_observation_fields', default={})
_ATTEMPT = ContextVar('ocrllm_observation_attempt', default=None)
_INSTANCE = f'{os.getpid()}-{uuid.uuid4().hex}'
_LOG = logging.getLogger('ocrllm.observation')


def _now():
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def observation_context(*, path=None, sink=None, lecture_id=None, runtime_version=None):
    """Observe enclosed preparation/merged recognition without changing defaults.

    Supply exactly one JSONL file path or callable sink receiving envelope dicts.
    Use a persistent owner directory. The built-in sink serializes local worker
    writes and flushes each line; it does not provide cross-process file locking
    or power-loss fsync guarantees. Use one file per producing process if needed.
    Sink exceptions are logged without response bodies or credentials and cannot
    change recognition results. A custom sink should return promptly.
    """
    if (path is None) == (sink is None):
        raise ValueError('Supply exactly one observation path or callable sink.')
    if sink is not None and not callable(sink):
        raise TypeError('Observation sink must be callable.')
    destination = Path(path) if path is not None else None
    observer = {'path': destination, 'sink': sink, 'lock': Lock(),
                'lecture_id': lecture_id, 'runtime_version': runtime_version}
    token = _OBSERVER.set(observer)
    try:
        yield
    finally:
        _OBSERVER.reset(token)


def emit(kind, *, task=None, **data):
    observer = _OBSERVER.get()
    if observer is None:
        return
    try:
        fields = {**_FIELDS.get(), **data}
        selected_task = task or fields.pop('task', None)
        fields.pop('task', None)
        for key in ('lecture_id', 'runtime_version'):
            if observer[key] is not None:
                fields[key] = observer[key]
        event = {'schema_version': 'course-observation/v1', 'event_id': uuid.uuid4().hex,
                 'owner': 'ocrllm', 'kind': kind, 'at': _now(), 'task': selected_task,
                 'instance_id': _INSTANCE, 'data': fields}
        with observer['lock']:
            if observer['sink'] is not None:
                observer['sink'](event)
            else:
                destination = observer['path']
                destination.parent.mkdir(parents=True, exist_ok=True)
                with destination.open('a', encoding='utf-8') as stream:
                    stream.write(json.dumps(event, ensure_ascii=False, allow_nan=False)+'\n')
    except Exception as error:
        _LOG.warning('Observation emission failed (%s); recognition continues.', type(error).__name__)


@contextmanager
def observation_fields(**fields):
    token = _FIELDS.set({**_FIELDS.get(), **fields})
    try:
        yield
    finally:
        _FIELDS.reset(token)
