"""Real subprocess Codex usage/drain scenario; no provider network calls."""
from pathlib import Path
from threading import Event
import argparse
import json
import tempfile

from ocrllm import CodexCLISettings, Config, ProviderModel, observation_context
from ocrllm.errors import ProviderError
from ocrllm.providers.recognize_provider_model_images import recognize_provider_model_images
from ocrllm.providers.codex_cli.recognize_images import recognize_images


def _settings(root, **kwargs):
    return CodexCLISettings(usage_event_dir=root / 'events', **kwargs)


def _images(root, count):
    from PIL import Image
    result = []
    for index in range(count):
        path = root / f'image-{index}.png'
        Image.new('RGB', (32, 32), color='white').save(path)
        result.append(path)
    return result


def _events(root):
    return [json.loads(line) for path in sorted((root / 'events').glob('*.jsonl'))
            for line in path.read_text().splitlines()]


def _provider(settings):
    return ProviderModel(vendor='openai', model='gpt-5.6-luna', adapter_id='codex_cli', settings=settings,
        supports_plain_ocr=True, supports_detail_ocr=True, supports_audio=False,
        default_image_batch_size=8, default_audio_minutes=None, retry_rules={})


def _run(root, settings):
    with observation_context(sink=lambda event: None, lecture_id='real-timeout', runtime_version='scenario'):
        return recognize_images(_images(root, 1), prompt='read', config=Config(provider=settings))


def test_real_cli_stream_is_durable_before_process_exit_and_stop_drains(tmp_path):
    """A real executable writes usage then waits, independently of the owner."""
    import sys
    import time
    from threading import Thread
    release = tmp_path / 'release'
    executable = tmp_path / 'scripted-codex'
    executable.write_text(f'''#!{sys.executable}
import json, pathlib, sys, time
output = pathlib.Path(sys.argv[sys.argv.index('--output-last-message') + 1])
print(json.dumps({{"type":"turn.started"}}), flush=True)
print(json.dumps({{"type":"turn.completed","usage":{{"input_tokens":71,"cached_input_tokens":12,"output_tokens":19,"reasoning_output_tokens":3}}}}), flush=True)
deadline=time.monotonic()+8
while not pathlib.Path({str(release)!r}).exists() and time.monotonic()<deadline:
    time.sleep(0.01)
output.write_text('complete output', encoding='utf-8')
''')
    executable.chmod(0o755)
    stop = Event()
    completed = []
    errors = []
    images = _images(tmp_path, 1)
    def execute():
        try:
            with observation_context(sink=lambda event: None, lecture_id='real-stream'):
                completed.append(recognize_provider_model_images(
                    _provider(_settings(tmp_path, command=str(executable))), images,
                    prompt='read', timeout_seconds=5, stop_requested=stop))
        except BaseException as error:
            errors.append(error)
    worker = Thread(target=execute)
    worker.start()
    deadline = time.monotonic() + 3
    try:
        while time.monotonic() < deadline:
            if any(event['kind'] == 'codex_turn_usage' for event in _events(tmp_path)):
                break
            time.sleep(0.01)
        assert worker.is_alive()
        assert any(event['kind'] == 'codex_turn_usage' for event in _events(tmp_path))
        assert not any(event['kind'] == 'codex_attempt_finished' for event in _events(tmp_path))
        stop.set()
    finally:
        release.touch()
        worker.join(timeout=6)
    assert not worker.is_alive() and not errors
    assert completed[0].markdown == 'complete output'
    assert completed[0].input_tokens == 71
    assert _events(tmp_path)[-1]['data']['outcome'] == 'succeeded'


def test_real_timeout_retains_finished_turn_and_unknown_unfinished_turn(tmp_path):
    import sys
    executable = tmp_path / 'scripted-codex'
    executable.write_text(f'''#!{sys.executable}
import json, pathlib, sys, time
pathlib.Path(sys.argv[sys.argv.index('--output-last-message') + 1]).write_text('partial output')
print(json.dumps({{"type":"turn.started"}}), flush=True)
print(json.dumps({{"type":"turn.completed","usage":{{"input_tokens":71,"cached_input_tokens":12,"output_tokens":19,"reasoning_output_tokens":3}}}}), flush=True)
print(json.dumps({{"type":"turn.started"}}), flush=True)
time.sleep(10)
''')
    executable.chmod(0o755)
    try:
        _run(tmp_path, _settings(tmp_path, command=str(executable), timeout_seconds=0.2))
    except ProviderError as caught:
        error = caught
    else:
        raise AssertionError('Expected bounded timeout')
    assert error.code == 'PROVIDER_TIMEOUT'
    assert error.details['provider_calls_attempted'] == 1
    assert error.details['input_tokens'] is None
    events = _events(tmp_path)
    turns = [event['data'] for event in events if event['kind'] == 'codex_turn_usage']
    assert len(turns) == 2
    assert turns[0]['usage']['input_tokens'] == 71
    assert turns[1]['usage']['input_tokens'] is None
    assert events[-1]['data']['usage_capture_complete'] is False
    assert Path(events[-1]['data']['failure_output_path']).read_text() == 'partial output'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-dir', required=True, type=Path)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, scenario in [('stream_drain', test_real_cli_stream_is_durable_before_process_exit_and_stop_drains),
                           ('timeout_unknown', test_real_timeout_retains_finished_turn_and_unknown_unfinished_turn)]:
        destination = args.output_dir / name
        destination.mkdir()
        scenario(destination)
    result = {'status': 'passed', 'scenarios': 2, 'real_model_calls': 0,
              'checks': ['usage_fsynced_before_process_exit', 'accepted_process_drains_after_stop',
                         'timeout_retains_known_completed_turn_and_unknown_active_turn', 'failed_body_separate_artifact']}
    (args.output_dir / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
