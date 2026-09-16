"""Public adapter accounting contracts at process, clock and filesystem boundaries."""
import json
import os
from pathlib import Path
from threading import Event

import pytest

from ocrllm import CodexCLISettings, Config, observation_context, recognize_images_to_markdown
from ocrllm.errors import Cancelled, OutputError, ProviderError, ProviderUnavailable
from ocrllm.providers.provider_model import ProviderModel
from ocrllm.providers.recognize_provider_model_images import recognize_provider_model_images
from ocrllm.providers.codex_cli import recognize_images as adapter
from test_codex_cli_adapter import fake_cli, _images


def _settings(tmp_path, **kwargs):
    return CodexCLISettings(usage_event_dir=tmp_path / 'events', **kwargs)


def _events(tmp_path):
    return [json.loads(line) for path in sorted((tmp_path / 'events').glob('*.jsonl'))
            for line in path.read_text().splitlines()]


def _provider(settings):
    return ProviderModel(vendor='openai', model='gpt-5.6-luna', adapter_id='codex_cli', settings=settings,
        supports_plain_ocr=True, supports_detail_ocr=False, supports_audio=False,
        default_image_batch_size=8, default_audio_minutes=None, retry_rules={})


def _run(tmp_path, settings=None):
    with observation_context(sink=lambda event: None, lecture_id='lecture-123', runtime_version='test-version'):
        return adapter.recognize_images(_images(tmp_path, 1), prompt='read', config=Config(provider=settings or _settings(tmp_path)))


def test_durable_start_precedes_spawn_and_turns_are_independent(tmp_path, fake_cli):
    fake_cli['script'] = [('ok', 'valid text')]
    fake_cli['on_call'] = lambda: assert_started(tmp_path)
    fake_cli['events'] = [
        {'type': 'thread.started', 'thread_id': 'thread-1'},
        {'type': 'turn.started'},
        {'type': 'turn.completed', 'usage': {'input_tokens': 100, 'cached_input_tokens': 40, 'output_tokens': 20, 'reasoning_output_tokens': 4}},
        {'type': 'turn.started'},
        {'type': 'turn.completed', 'usage': {'input_tokens': 200, 'cached_input_tokens': 60, 'output_tokens': 30, 'reasoning_output_tokens': 5}},
    ]
    response = _run(tmp_path, _settings(tmp_path, service_tier='default'))
    events = _events(tmp_path)
    assert [row['kind'] for row in events] == ['codex_attempt_started', 'codex_turn_usage', 'codex_turn_usage', 'codex_attempt_finished']
    assert response.input_tokens == 200 and response.output_tokens == 30
    assert response.provider_calls_attempted == 1
    assert events[1]['data']['turn_seq'] == 0 and events[2]['data']['turn_seq'] == 1
    assert events[2]['data']['raw_usage']['input_tokens'] == 200
    assert events[2]['data']['usage']['input_tokens'] == 100
    assert events[2]['data']['normalization'] == 'thread_cumulative_delta'
    assert len({row['event_id'] for row in events}) == 4
    for row in events:
        assert row['data']['start_event_id'] == events[0]['event_id']
        assert row['data']['lecture_id'] == 'lecture-123'
        assert row['data']['requested_service_tier'] == 'default'
        assert row['data']['actual_model'] is None
        assert row['data']['ocrllm_version'] == 'test-version'
    assert events[-1]['data']['usage_capture_complete'] is True
    assert 'service_tier="default"' in fake_cli['calls'][0]


def assert_started(tmp_path):
    events = _events(tmp_path)
    assert len(events) == 1 and events[0]['kind'] == 'codex_attempt_started'


def test_failed_attempt_usage_is_in_total_and_preserved_before_retry(tmp_path, fake_cli):
    fake_cli['script'] = [('ok', 'SORRY4OCRLLM, because 内容令人困惑'), ('ok', 'valid text')]
    response = _run(tmp_path)
    events = _events(tmp_path)
    finishes = [row['data'] for row in events if row['kind'] == 'codex_attempt_finished']
    assert response.provider_calls_attempted == 2
    assert response.input_tokens == 200 and response.output_tokens == 40
    assert finishes[0]['outcome'] == 'failed' and finishes[1]['outcome'] == 'succeeded'
    assert Path(finishes[0]['failure_output_path']).read_text() == 'SORRY4OCRLLM, because 内容令人困惑'
    assert all('SORRY4OCRLLM' not in json.dumps(event) for event in events)
    assert finishes[0]['parent_call_id'] == finishes[1]['parent_call_id']


def test_turn_failed_with_no_usage_is_unknown_even_when_later_retry_succeeds(tmp_path, fake_cli):
    fake_cli['script'] = [('fail', 'failure'), ('ok', 'text')]
    fake_cli['events_per_call'] = [[{'type': 'turn.failed', 'error': {'message': 'private error text'}}],
                                  [{'type': 'turn.completed'}]]
    response = _run(tmp_path)
    events = _events(tmp_path)
    assert response.input_tokens is None and response.output_tokens is None
    turns = [event['data'] for event in events if event['kind'] == 'codex_turn_usage']
    assert len(turns) == 2 and all(turn['usage']['input_tokens'] is None for turn in turns)
    assert all(turn['missing_reason'] for turn in turns)
    assert all('private error text' not in json.dumps(event) for event in events)


def test_absent_usage_is_unknown_not_zero_and_stdout_is_never_markdown(tmp_path, fake_cli):
    fake_cli['script'] = [('ok', '')]
    fake_cli['events'] = [{'type': 'item.completed', 'item': {'text': 'this is NOT final Markdown'}}]
    with pytest.raises(ProviderError) as caught:
        _run(tmp_path)
    assert caught.value.code == 'PROVIDER_RESPONSE_INVALID'
    assert caught.value.details['input_tokens'] is None
    assert len([event for event in _events(tmp_path) if event['kind'] == 'codex_turn_usage']) == 3


def test_spawn_failures_are_zero_model_calls_with_terminal_durable_facts(tmp_path, fake_cli):
    fake_cli['script'] = [('oserror', 'resource pressure')]
    with pytest.raises(ProviderUnavailable) as caught:
        _run(tmp_path)
    assert caught.value.details['provider_calls_attempted'] == 0
    assert caught.value.details['input_tokens'] == 0
    finishes = [event['data'] for event in _events(tmp_path) if event['kind'] == 'codex_attempt_finished']
    assert len(finishes) == 3 and all(row['spawned'] == 0 for row in finishes)
    assert not any(event['kind'] == 'codex_turn_usage' for event in _events(tmp_path))


def test_usage_disk_failure_before_admission_never_spawns(tmp_path, fake_cli, monkeypatch):
    def fail_sync(fd):
        raise OSError('disk error')
    monkeypatch.setattr(os, 'fsync', fail_sync)
    with pytest.raises(OutputError):
        _run(tmp_path)
    assert not fake_cli['calls']


def test_merged_deadline_reaches_internal_retry_and_stops_new_spawn(tmp_path, fake_cli):
    fake_cli['script'] = [('fail', 'temporary')]
    with pytest.raises(ProviderUnavailable) as caught:
        recognize_provider_model_images(_provider(_settings(tmp_path)), _images(tmp_path, 1), prompt='read', timeout_seconds=1)
    assert caught.value.details['provider_calls_attempted'] == 1
    assert fake_cli['timeouts'][0] <= 1
    assert len(fake_cli['calls']) == 1


def test_safe_stop_after_failed_attempt_checkpoints_it_without_internal_retry(tmp_path, fake_cli):
    stop = Event()
    fake_cli['script'] = [('fail', 'temporary')]
    fake_cli['on_call'] = stop.set
    with observation_context(sink=lambda event: None, lecture_id='course-stop'):
        with pytest.raises(Cancelled) as caught:
            recognize_images_to_markdown((tuple(_images(tmp_path, 1)),), provider=_provider(_settings(tmp_path)),
                output_path=tmp_path / 'out.md', image_task='plain_ocr', stop_requested=stop)
    assert caught.value.details['safe_stop'] is True
    assert caught.value.details['current_call_count'] == 1
    assert len(fake_cli['calls']) == 1
    assert _events(tmp_path)[-1]['kind'] == 'codex_attempt_finished'
    state_files = list(tmp_path.glob('*.ocrllm-state.json'))
    assert state_files
    state = json.loads(state_files[0].read_text())
    assert state['slots'][0]['status'] == 'failed'






def test_missing_cumulative_field_does_not_bill_later_total_as_single_turn(tmp_path, fake_cli):
    fake_cli['script'] = [('ok', 'valid text')]
    fake_cli['events'] = [
        {'type': 'thread.started', 'thread_id': 'thread-1'},
        {'type': 'turn.completed', 'usage': {'input_tokens': 100, 'cached_input_tokens': 20, 'output_tokens': 10, 'reasoning_output_tokens': 1}},
        {'type': 'turn.completed', 'usage': {'cached_input_tokens': 30, 'output_tokens': 20, 'reasoning_output_tokens': 2}},
        {'type': 'turn.completed', 'usage': {'input_tokens': 300, 'cached_input_tokens': 40, 'output_tokens': 30, 'reasoning_output_tokens': 3}},
        {'type': 'turn.completed', 'usage': {'input_tokens': 400, 'cached_input_tokens': 50, 'output_tokens': 40, 'reasoning_output_tokens': 4}},
    ]
    response = _run(tmp_path)
    turns = [event['data'] for event in _events(tmp_path) if event['kind'] == 'codex_turn_usage']
    assert [turn['usage']['input_tokens'] for turn in turns] == [100, None, None, 100]
    assert [turn['usage']['output_tokens'] for turn in turns] == [10, 10, 10, 10]
    assert response.input_tokens is None and response.output_tokens == 40
    assert _events(tmp_path)[-1]['data']['usage_capture_complete'] is False


def test_stop_during_durable_start_prevents_spawn_and_finishes_zero_intent(tmp_path, fake_cli, monkeypatch):
    stop = Event()
    original_sync = os.fsync
    def stop_after_sync(fd):
        original_sync(fd)
        stop.set()
    monkeypatch.setattr(os, 'fsync', stop_after_sync)
    from ocrllm.cooperative_stop import ProviderDispatchStopped
    with pytest.raises(ProviderDispatchStopped):
        recognize_provider_model_images(_provider(_settings(tmp_path)), _images(tmp_path, 1),
            prompt='read', timeout_seconds=10, stop_requested=stop)
    assert not fake_cli['calls']
    assert _events(tmp_path)[-1]['data']['spawned'] == 0
    assert _events(tmp_path)[-1]['data']['outcome'] == 'cancelled'


def test_accepted_cli_event_matches_durable_generic_unit_on_safe_stop(tmp_path, fake_cli):
    stop = Event()
    ordinary = []
    fake_cli['script'] = [('ok', 'accepted board content')]
    fake_cli['on_call'] = stop.set
    with observation_context(sink=ordinary.append, lecture_id='joined-course', runtime_version='owner-test'):
        with pytest.raises(Cancelled) as caught:
            recognize_images_to_markdown((tuple(_images(tmp_path, 1)),), provider=_provider(_settings(tmp_path)),
                output_path=tmp_path / 'out.md', image_task='plain_ocr', stop_requested=stop)
    assert caught.value.details['safe_stop'] is True
    unit = next(event for event in ordinary if event['kind'] == 'unit_result')
    finish = _events(tmp_path)[-1]
    assert unit['data']['status'] == 'settled'
    assert unit['data']['acceptance'] == 'durable_checkpoint' and unit['data']['reused'] is False
    assert finish['data']['outcome'] == 'succeeded' and finish['data']['validation_status'] == 'accepted'
    for key in ('lecture_id', 'logical_unit_id'):
        assert unit['data'][key] == finish['data'][key]
    assert unit['instance_id'].split('-', 1)[0] == finish['instance_id'].split('-', 1)[0]
    assert finish['data']['configured_concurrency'] == 1
    assert finish['data']['prompt_version']


def test_terminal_failed_never_accepts_partial_body_even_with_exit_zero(tmp_path, fake_cli):
    fake_cli['script'] = [('ok', 'partial content')]
    fake_cli['events'] = [{'type': 'turn.failed'}]
    with pytest.raises(ProviderUnavailable):
        _run(tmp_path)
    finishes = [event['data'] for event in _events(tmp_path) if event['kind'] == 'codex_attempt_finished']
    assert len(finishes) == 3 and all(event['outcome'] == 'failed' for event in finishes)


def test_actual_cli_version_cached_by_binary_revision(tmp_path, fake_cli, monkeypatch):
    import shutil
    import subprocess
    binary = tmp_path / 'codex-version-fixture'
    binary.write_text('binary-revision')
    monkeypatch.setattr(shutil, 'which', lambda command: str(binary))
    versions = []
    def version_process(argv, **kwargs):
        versions.append(argv)
        assert argv == [str(binary), '--version']
        assert kwargs['timeout'] == 3.0
        return subprocess.CompletedProcess(argv, 0, stdout='codex-cli 0.154.0-alpha.6.1\n', stderr='')
    monkeypatch.setattr(subprocess, 'run', version_process)
    fake_cli['script'] = [('ok', 'board content')]
    _run(tmp_path)
    _run(tmp_path)
    assert len(versions) == 1 and len(fake_cli['calls']) == 2
    assert _events(tmp_path)[-1]['data']['cli_version'] == '0.154.0-alpha.6.1'
    assert _events(tmp_path)[-1]['data']['cli_binary_path'] == str(binary)
    binary.write_text('changed-binary-revision')
    _run(tmp_path)
    assert len(versions) == 2


def test_unknown_cli_version_does_not_invent_one_or_block_real_exec(tmp_path, fake_cli, monkeypatch):
    import shutil
    import subprocess
    binary = tmp_path / 'unknown-version'
    binary.write_text('binary')
    monkeypatch.setattr(shutil, 'which', lambda command: str(binary))
    monkeypatch.setattr(subprocess, 'run', lambda argv, **kwargs:
        subprocess.CompletedProcess(argv, 0, stdout='unexpected private diagnostic', stderr=''))
    fake_cli['script'] = [('ok', 'board content')]
    _run(tmp_path)
    assert _events(tmp_path)[-1]['data']['cli_version'] is None
    assert 'unexpected private diagnostic' not in json.dumps(_events(tmp_path))
    assert len(fake_cli['calls']) == 1
