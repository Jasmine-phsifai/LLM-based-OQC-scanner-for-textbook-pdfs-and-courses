"""Owner plan, durable unit and stage facts without exposing checkpoint JSON."""
from contextlib import contextmanager
from functools import wraps
import hashlib
import json
import time
import uuid
from .observation_context import _OBSERVER, _FIELDS, _now, emit, observation_fields


def _identity(value):
    return hashlib.sha256(json.dumps(value).encode()).hexdigest()


def audio_unit(slot, *, parent=None, source_id=None):
    source_id = source_id or _FIELDS.get().get('source_id')
    unit_id = _identity((source_id, slot.logical_start_seconds, slot.logical_end_seconds))
    return {'task': 'asr', 'logical_unit_id': unit_id,
            'parent_unit_id': (audio_unit(parent, source_id=source_id)['logical_unit_id'] if parent else None),
            'source_start_seconds': slot.logical_start_seconds, 'source_end_seconds': slot.logical_end_seconds,
            'actual_start_seconds': slot.actual_start_seconds, 'actual_end_seconds': slot.actual_end_seconds,
            'planned_units': slot.logical_end_seconds-slot.logical_start_seconds, 'unit': 'audio_second'}


def image_unit(slot, state):
    return {'task': 'ocr', 'logical_unit_id': _identity(tuple(
        (state.sources[i].sha256, i) for i in slot.source_indexes)),
        'source_indexes': list(slot.source_indexes),
        'source_paths': [state.sources[i].uri for i in slot.source_indexes], 'input_count': len(slot.source_indexes),
        'planned_units': len(slot.source_indexes), 'unit': 'image'}


def unit_result(slot, fields=None, *, reused=False):
    if _OBSERVER.get() is None:
        return
    emit('unit_result', **(fields or {}), status=slot.status, reused=reused,
         valid_units=0 if reused or slot.status != 'settled' else (fields or _FIELDS.get()).get('planned_units'),
         reused_units=(fields or _FIELDS.get()).get('planned_units') if reused else 0,
         no_speech=getattr(slot, 'no_speech', False), error_code=slot.error_code,
         acceptance='durable_checkpoint')


def observe_plan(state, task):
    if _OBSERVER.get() is None:
        return
    summary = {'original_unit_count': len(state.slots), 'plan_role': 'original'}
    if task == 'asr':
        summary.update(source_duration_seconds=state.slots[-1].logical_end_seconds, source_id=state.source.sha256, source_path=state.source.uri)
    else:
        summary.update(input_frame_count=len(state.sources))
    emit('plan', task=task, **summary)
    for slot in state.slots:
        fields = audio_unit(slot, source_id=state.source.sha256) if task == 'asr' else image_unit(slot, state)
        emit('plan', **fields, plan_role='original_unit', status=slot.status)
        if task == 'asr' and slot.subslots:
            for child in slot.subslots:
                child_fields = audio_unit(child, parent=slot, source_id=state.source.sha256)
                emit('plan', **child_fields, plan_role='derived_unit', status=child.status)
                if child.status == 'settled':
                    unit_result(child, child_fields, reused=True)
        elif slot.status == 'settled':
            unit_result(slot, fields, reused=True)


def observed_execution(task):
    def decorate(function):
        @wraps(function)
        def run(state, *args, **kwargs):
            if _OBSERVER.get() is None:
                return function(state, *args, **kwargs)
            with observation_fields(task=task, source_id=state.source.sha256 if task == 'asr' else None):
                observe_plan(state, task)
                return function(state, *args, **kwargs)
        return run
    return decorate


def observed_audio_unit(function):
    @wraps(function)
    def run(slot, *args, **kwargs):
        if _OBSERVER.get() is None:
            return function(slot, *args, **kwargs)
        with observation_fields(**audio_unit(slot, parent=getattr(kwargs['owner'], 'parent', None))):
            return function(slot, *args, **kwargs)
    return run


@contextmanager
def observation_stage(stage, task, **fields):
    if _OBSERVER.get() is None:
        yield {}
        return
    start, clock = _now(), time.monotonic()
    status, error_code = 'success', None
    with observation_fields(task=task, **fields):
        stage_id = uuid.uuid4().hex
        emit('stage_started', stage=stage, stage_id=stage_id, started_at=start)
        summary = {}
        try:
            yield summary
        except BaseException as error:
            status = 'failed' if isinstance(error, Exception) else 'cancelled'
            error_code = getattr(error, 'code', None)
            raise
        finally:
            emit('stage_finished', stage=stage, stage_id=stage_id, started_at=start,
                 finished_at=_now(), elapsed_seconds=time.monotonic()-clock,
                 status=summary.pop('status', status), error_code=error_code, **summary)


def observed_stage(stage, task):
    def decorate(function):
        @wraps(function)
        def run(*args, **kwargs):
            if _OBSERVER.get() is None:
                return function(*args, **kwargs)
            fields = {'output_path': str(kwargs['output_path'])} if kwargs.get('output_path') is not None else {}
            with observation_stage(stage, task, **fields) as summary:
                if stage == 'markdown':
                    state = args[0] if args else kwargs['state']
                    if task == 'ocr':
                        summary.update(input_frame_count=len(state.sources),
                            settled_frame_count=sum(len(slot.source_indexes) for slot in state.slots if slot.status == 'settled'),
                            failed_frame_count=sum(len(slot.source_indexes) for slot in state.slots if slot.status == 'failed'),
                            pending_frame_count=sum(len(slot.source_indexes) for slot in state.slots if slot.status == 'unresolved'))
                    else:
                        from .audio_gap_summary import audio_gap_summary
                        gap = audio_gap_summary(state)
                        summary.update(failed_seconds=gap['failed_seconds'], failed_fraction=gap['failed_fraction'],
                                       accepted_with_gaps=state.accepted_with_gaps,
                                       unresolved_segment_count=gap['unresolved_segment_count'])
                result = function(*args, **kwargs)
                if hasattr(result, 'metadata'):
                    keys = ('slot_count', 'settled_slot_count', 'provider_call_count', 'reused_slot_count',
                            'duration_seconds', 'failed_seconds', 'failed_fraction', 'accepted_with_gaps')
                    data = {key: result.metadata[key] for key in keys if key in result.metadata}
                    if 'failed_segments' in result.metadata:
                        data['failed_segments'] = [{key: row[key] for key in
                            ('slot_index', 'subslot_index', 'start_seconds', 'end_seconds', 'code', 'output_limit_attempts')}
                            for row in result.metadata['failed_segments']]
                    summary.update(status=result.status, **data)
                elif stage == 'select_frames':
                    summary.update(input_frame_count=len(args[0] if args else kwargs['frames']),
                         selected_frame_count=len(result), source_duration_seconds=kwargs.get('duration_seconds'))
                elif stage == 'prepare_audio_plan':
                    summary.update(original_unit_count=len(result), source_duration_seconds=result[-1].logical_end_seconds)
                elif stage == 'prepare_image_batches':
                    summary.update(original_unit_count=len(result), input_frame_count=sum(map(len, result)))
                return result
        return run
    return decorate
