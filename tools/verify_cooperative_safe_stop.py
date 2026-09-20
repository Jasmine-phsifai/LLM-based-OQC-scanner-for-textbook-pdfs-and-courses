"""Prove merged safe-stop with encoded media and deterministic local HTTP.

No model service is called. OS replace injection covers the exact admission /
reservation race and failed checkpoint writes; no OCRLLM internals are mocked.
"""

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Barrier, Event, Lock, Thread, Timer

from PIL import Image

from ocrllm import (
    AudioOutputLimitPolicy, CodexCLISettings, OpenAICompatibleSettings, ProviderModel,
    inspect_audio_completion, inspect_image_service_recovery, inspect_markdown_job, observation_context,
    recognize_audio_to_markdown, recognize_images_to_markdown,
    resume_audio_to_markdown, resume_images_to_markdown, split_audio,
)
from ocrllm.audio.load_audio_ffmpeg_executable import load_audio_ffmpeg_executable
from ocrllm.errors import AllCandidatesExhausted, Cancelled, ConfigError, OutputError


@dataclass
class Reply:
    status: int = 200
    value: str = 'Synthetic recognized content.'
    request_stop: bool = False
    stop_after: float | None = None
    barrier: Barrier | None = None
    delay: float = 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-dir', required=True, type=Path)
    args = parser.parse_args()
    args.work_dir.mkdir(parents=True, exist_ok=True)
    media = args.work_dir / 'input.mp3'
    subprocess.run([str(load_audio_ffmpeg_executable()), '-nostdin', '-v', 'error', '-y',
                    '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=16000',
                    '-t', '121.375', '-c:a', 'libmp3lame', str(media)],
                   check=True, timeout=30)
    batches = []
    for index in range(4):
        path = args.work_dir / f'frame-{index}.png'
        Image.new('RGB', (80, 60), (index * 35, 40, 90)).save(path)
        batches.append((path,))
    batches = tuple(batches)
    plan = split_audio(media, interval_minutes=1, include_boundary_context=False)
    whole = split_audio(media, interval_minutes=-1)
    stop, lock = Event(), Lock()
    replies, calls, completed, timers = [], [], [], []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_POST(self):
            request = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            with lock:
                index = len(calls)
                calls.append(request['model'])
                reply = replies[index] if index < len(replies) else Reply(500, 'unexpected_call')
            if reply.barrier is not None:
                reply.barrier.wait(timeout=10)
            if reply.request_stop:
                stop.set()
            if reply.stop_after is not None:
                timer = Timer(reply.stop_after, stop.set)
                timers.append(timer)
                timer.start()
            if reply.delay:
                time.sleep(reply.delay)
            request_id = f'chatcmpl-safe-stop-{index}'
            if reply.status == 200:
                payload = {'id': request_id, 'model': request['model'],
                           'choices': [{'index': 0, 'finish_reason': 'stop',
                               'message': {'role': 'assistant', 'content': reply.value}}],
                           'usage': {'prompt_tokens': 12, 'completion_tokens': 8}}
            else:
                payload = {'error': {'code': reply.value, 'message': 'Synthetic rejected generation',
                    'details': {'generation_output': {'artifact_saved': True,
                        'artifact_path': str(args.work_dir / f'{request_id}.json'),
                        'request_id': request_id, 'input_audio_sha256': '0' * 64,
                        'input_tokens': 12, 'generated_tokens': 8192,
                        'max_new_tokens': 8192, 'reached_eos': False}}}}
                (args.work_dir / f'{request_id}.json').write_text(
                    json.dumps({'raw_decode': 'Synthetic rejected content.'}), encoding='utf-8')
            raw = json.dumps(payload).encode()
            self.send_response(reply.status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(raw)))
            self.send_header('x-request-id', request_id)
            self.end_headers()
            self.wfile.write(raw)
            with lock:
                completed.append(index)

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    provider = ProviderModel(
        vendor='scenario', model='synthetic-safe-stop', adapter_id='openai_compatible_chat',
        settings=OpenAICompatibleSettings(
            base_url=f'http://127.0.0.1:{server.server_port}/v1', send_audio_prompt=False,
            response_validation='nonempty_text', audio_response_validation='visible_text',
            capture_error_output=True),
        supports_audio=True, supports_plain_ocr=True, supports_detail_ocr=True,
        default_image_batch_size=1, default_audio_minutes=1,
        retry_rules={'PROVIDER_UNAVAILABLE': ('current', 1, 2)})
    policy = AudioOutputLimitPolicy()
    verdicts = {}

    def reset(sequence):
        for timer in timers:
            timer.join(timeout=2)
        timers.clear()
        replies[:] = sequence
        calls.clear()
        completed.clear()
        stop.clear()

    def checkpoint(out):
        return json.loads(out.with_suffix('.ocrllm-state.json').read_text())

    def dispatch_confirmation(out, expected, reason=None):
        path = out.with_suffix('.ocrllm-state.json')
        before = path.read_bytes() if path.exists() else None
        call_count = len(calls)
        summary = inspect_audio_completion(out)
        assert summary['audio_dispatch_checkpoint_confirmed'] is expected
        if reason is not None:
            assert summary['audio_dispatch_checkpoint_reason'] == reason
        assert (path.read_bytes() if path.exists() else None) == before
        assert len(calls) == call_count

    def audio(out, *, slices=plan, resume=False, provider_arg=provider, **kwargs):
        function = resume_audio_to_markdown if resume else recognize_audio_to_markdown
        return function(slices, provider=provider_arg, output_path=out,
                        stop_requested=stop, audio_output_limit_policy=policy, **kwargs)

    def images(out, *, selected=batches, resume=False, provider_arg=provider, **kwargs):
        function = resume_images_to_markdown if resume else recognize_images_to_markdown
        return function(selected, provider=provider_arg, output_path=out,
                        stop_requested=stop, **({} if resume else {'image_task': 'plain_ocr'}), **kwargs)

    def paused(call, expected_calls):
        events = []
        with observation_context(sink=events.append):
            try:
                call()
            except Cancelled as error:
                assert error.code == 'CANCELLED'
                assert dict(error.details) == {'safe_stop': True, 'resume_available': True,
                    'current_call_count': expected_calls, 'provider_calls_attempted': expected_calls}
            else:
                raise AssertionError('Expected a safe-stop acknowledgement')
        assert len(calls) == expected_calls
        assert len(completed) == expected_calls
        finished = [row['data'] for row in events if row['kind'] == 'stage_finished']
        assert finished[-1]['status'] == 'cancelled' and finished[-1]['error_code'] == 'CANCELLED'
        return events

    try:
        # Narrow image recovery is selected from owner state, not inferred by
        # the caller. Real HTTP supplies both canonical service error classes.
        service_provider = ProviderModel(**{name: getattr(provider, name) for name in (
            "vendor", "model", "adapter_id", "settings", "supports_audio",
            "supports_plain_ocr", "supports_detail_ocr", "default_image_batch_size",
            "default_audio_minutes")}, retry_rules={})
        out = args.work_dir / 'service-only-images.md'
        reset([Reply(), Reply(503, 'unavailable'), Reply(value=''), Reply(504, 'timeout')])
        assert images(out, provider_arg=service_provider).status == 'partial'
        original = checkpoint(out)
        assert [row['error_code'] for row in original['slots']] == [
            None, 'PROVIDER_UNAVAILABLE', 'PROVIDER_RESPONSE_INVALID', 'PROVIDER_TIMEOUT']
        summary = inspect_image_service_recovery(out)
        assert summary['service_recovery_available'] and summary['service_recovery_slot_count'] == 2
        assert checkpoint(out) == original
        # The first service slot now yields invalid output and requests pause.
        # A later recovery must never retry that new validation failure.
        reset([Reply(value='', request_stop=True)])
        paused(lambda: images(out, resume=True, provider_arg=service_provider,
                              service_recovery_only=True, service_recovery_batch_id="scenario-batch"), 1)
        after_pause = checkpoint(out)
        assert after_pause['slots'][1]['error_code'] == 'PROVIDER_RESPONSE_INVALID'
        assert inspect_image_service_recovery(out)['service_recovery_slot_count'] == 1
        reset([Reply()])
        result = images(out, resume=True, provider_arg=[[service_provider], [service_provider]],
                        service_recovery_only=True, service_recovery_batch_id="scenario-batch")
        assert result.status == 'partial' and len(calls) == 1
        assert result.metadata['reused_slot_count'] == 1
        after = checkpoint(out)
        assert after['slots'][0] == original['slots'][0]
        assert after['slots'][1:3] == after_pause['slots'][1:3]
        assert after['slots'][3]['status'] == 'settled'
        assert not inspect_image_service_recovery(out)['service_recovery_available']
        reset([])
        result = images(out, resume=True, provider_arg=service_provider, service_recovery_only=True, service_recovery_batch_id="scenario-batch")
        assert result.status == 'partial' and not calls
        # Default resume keeps its original behavior and can recover other errors.
        reset([Reply(), Reply()])
        assert images(out, resume=True, provider_arg=service_provider).status == 'complete'
        assert len(calls) == 2
        assert not inspect_image_service_recovery(out)['service_recovery_available']
        verdicts['service_only_mixed_errors_pause_preserves_new_validation_failure'] = True
        verdicts['service_only_preserves_settled_groups_and_fixed_lanes'] = True
        verdicts['default_image_resume_unchanged'] = True

        # The filter does not implement its own retry policy: the existing
        # configured finite current-provider retry still executes normally.
        out = args.work_dir / 'service-bounded-retry.md'
        reset([Reply(503, 'unavailable')])
        try:
            images(out, selected=batches[:1], provider_arg=service_provider)
        except AllCandidatesExhausted:
            pass
        reset([Reply(503, 'unavailable'), Reply()])
        result = images(out, selected=batches[:1], resume=True,
                        service_recovery_only=True, service_recovery_batch_id="scenario-batch")
        assert result.status == 'complete' and len(calls) == 2
        verdicts['service_recovery_uses_existing_bounded_provider_retries'] = True


        # Reservations survive repeated pauses and service failures. Every
        # original slot gets one finite execution in this explicit batch.
        out = args.work_dir / 'service-repeated-pause.md'
        reset([Reply(503, 'unavailable')] * len(batches))
        try:
            images(out, provider_arg=service_provider)
        except AllCandidatesExhausted:
            pass
        assert 'service_recovery_reservations' not in checkpoint(out)
        reset([])
        stop.set()
        paused(lambda: images(out, resume=True, provider_arg=service_provider,
            service_recovery_only=True, service_recovery_batch_id='repeated'), 0)
        assert 'service_recovery_reservations' not in checkpoint(out)
        stop.clear()
        try:
            images(out, resume=True, provider_arg=service_provider, service_recovery_only=True)
        except ConfigError:
            pass
        else:
            raise AssertionError('Service recovery without explicit batch ID was accepted')
        assert not calls

        for index in range(len(batches)):
            reset([Reply(503, 'unavailable', request_stop=True)])
            paused(lambda: images(out, resume=True, provider_arg=service_provider,
                service_recovery_only=True, service_recovery_batch_id='repeated'), 1)
            assert checkpoint(out)['service_recovery_reservations']['repeated'] == list(range(index+1))
            assert inspect_image_service_recovery(out, service_recovery_batch_id='repeated')[
                'service_recovery_slot_count'] == len(batches)-index-1
        reset([])
        try:
            images(out, resume=True, provider_arg=service_provider,
                   service_recovery_only=True, service_recovery_batch_id='repeated')
        except AllCandidatesExhausted:
            pass
        assert not calls
        reset([Reply()] * len(batches))
        assert images(out, resume=True, provider_arg=service_provider,
            service_recovery_only=True, service_recovery_batch_id='explicit-new-batch').status == 'complete'
        verdicts['same_batch_repeated_pause_never_retries_reserved_service_slots'] = True

        # A stop during atomic reservation admits that exact request, then
        # blocks subsequent retry/fallback and leaves other slots unreserved.
        out = args.work_dir / 'service-reservation-race.md'
        reset([Reply(503, 'unavailable')] * len(batches))
        try:
            images(out, provider_arg=service_provider)
        except AllCandidatesExhausted:
            pass
        original_replace = os.replace
        def stop_at_service_reservation(source, target):
            original_replace(source, target)
            if Path(target) == out.with_suffix('.ocrllm-state.json'):
                if checkpoint(out).get('service_recovery_reservations', {}).get('race'):
                    stop.set()
        reset([Reply(503, 'unavailable')])
        os.replace = stop_at_service_reservation
        try:
            paused(lambda: images(out, resume=True, service_recovery_only=True,
                                  service_recovery_batch_id='race'), 1)
        finally:
            os.replace = original_replace
        assert checkpoint(out)['service_recovery_reservations']['race'] == [0]
        reset([Reply()] * (len(batches)-1))
        result = images(out, resume=True, provider_arg=service_provider,
                        service_recovery_only=True, service_recovery_batch_id='race')
        assert result.status == 'partial' and len(calls) == len(batches)-1
        assert checkpoint(out)['slots'][0]['error_code'] == 'PROVIDER_UNAVAILABLE'
        verdicts['service_reservation_race_runs_first_call_but_blocks_retry'] = True

        # Codex has its own pre-spawn and internal-retry gates. A true OS
        # subprocess proves the same reservation race at that adapter boundary.
        cli_source = args.work_dir / 'reservation_codex.py'
        cli_calls = args.work_dir / 'reservation_cli_calls.txt'
        cli_ok = args.work_dir / 'reservation_cli_ok'
        cli_source.write_text(
            "import sys\nfrom pathlib import Path\na=sys.argv[1:]\n"
            "if a==['--version']: print('synthetic-reservation 1'); raise SystemExit(0)\n"
            f"with Path({str(cli_calls)!r}).open('a') as f: f.write('call\\n')\n"
            f"if not Path({str(cli_ok)!r}).exists(): raise SystemExit(1)\n"
            "Path(a[a.index('--output-last-message')+1]).write_text('Synthetic course content.')\n",
            encoding='utf-8')
        if os.name == 'nt':
            cli = args.work_dir / 'reservation-codex.cmd'
            cli.write_text(f'@echo off\r\n"{sys.executable}" "{cli_source}" %*\r\n')
        else:
            cli = args.work_dir / 'reservation-codex'
            cli.write_text(f'#!{sys.executable}\nexec(compile(open({str(cli_source)!r}).read(), {str(cli_source)!r}, "exec"))\n')
            cli.chmod(0o755)
        cli_provider = ProviderModel(vendor='openai', model='synthetic-reservation',
            adapter_id='codex_cli', settings=CodexCLISettings(command=str(cli), timeout_seconds=20),
            supports_plain_ocr=True, supports_detail_ocr=True, supports_audio=False,
            default_image_batch_size=1, default_audio_minutes=None, retry_rules={})
        out = args.work_dir / 'service-codex-race.md'
        reset([Reply(503, 'unavailable')] * len(batches))
        try:
            images(out, provider_arg=service_provider)
        except AllCandidatesExhausted:
            pass
        reset([])
        os.replace = stop_at_service_reservation
        try:
            images(out, resume=True, provider_arg=cli_provider,
                   service_recovery_only=True, service_recovery_batch_id='race')
        except Cancelled as error:
            assert error.details['safe_stop'] and error.details['current_call_count'] == 1
        else:
            raise AssertionError('Codex reservation race did not acknowledge stop')
        finally:
            os.replace = original_replace
        assert cli_calls.read_text().splitlines() == ['call']
        assert checkpoint(out)['service_recovery_reservations']['race'] == [0]
        reset([])
        cli_ok.touch()
        result = images(out, resume=True, provider_arg=cli_provider,
            service_recovery_only=True, service_recovery_batch_id='race')
        assert result.status == 'partial' and len(cli_calls.read_text().splitlines()) == len(batches)
        verdicts['codex_reservation_race_runs_one_spawn_and_stops_internal_retries'] = True

        # Unknown crash after atomic reservation conservatively spends that
        # slot's admission. It must not silently repeat on process recovery.
        out = args.work_dir / 'service-reservation-crash.md'
        reset([Reply(503, 'unavailable')] * len(batches))
        try:
            images(out, provider_arg=service_provider)
        except AllCandidatesExhausted:
            pass
        def crash_at_service_reservation(source, target):
            original_replace(source, target)
            if Path(target) == out.with_suffix('.ocrllm-state.json'):
                if checkpoint(out).get('service_recovery_reservations', {}).get('crash'):
                    raise KeyboardInterrupt('Synthetic post-reservation crash')
        reset([])
        os.replace = crash_at_service_reservation
        try:
            images(out, resume=True, provider_arg=service_provider,
                   service_recovery_only=True, service_recovery_batch_id='crash')
        except KeyboardInterrupt:
            pass
        finally:
            os.replace = original_replace
        assert not calls
        reset([Reply()] * (len(batches)-1))
        assert images(out, resume=True, provider_arg=service_provider,
            service_recovery_only=True, service_recovery_batch_id='crash').status == 'partial'
        assert len(calls) == len(batches)-1
        verdicts['unknown_service_reservation_not_reissued'] = True

        # A pending slot from a pre-dispatch pause is not a saved service failure.
        reset([])
        stop.set()
        out = args.work_dir / 'service-only-pending.md'
        paused(lambda: images(out, provider_arg=service_provider), 0)
        assert not inspect_image_service_recovery(out)['service_recovery_available']
        reset([])
        try:
            images(out, resume=True, provider_arg=service_provider, service_recovery_only=True, service_recovery_batch_id="scenario-batch")
        except AllCandidatesExhausted:
            pass
        else:
            raise AssertionError('Unresolved-only checkpoint became success')
        assert not calls
        verdicts['service_only_excludes_unresolved_slots'] = True

        # All-rejected recognition still has a safe owner exit after checkpoint
        # and HTTP-client cleanup. Failed cleanup must withhold this guarantee.
        from contextlib import nullcontext
        from unittest.mock import patch
        import openai
        original_close = openai.OpenAI.close
        def fail_client_close(client):
            original_close(client)
            raise OSError('Synthetic SDK client close failure')
        for cleanup_failed in (False, True):
            for name, function in [('audio', audio), ('images', images)]:
                count = len(plan) if name == 'audio' else len(batches)
                reset([Reply(400, 'invalid_request')] * count)
                out = args.work_dir / f'all-rejected-{name}-{cleanup_failed}.md'
                with (patch.object(openai.OpenAI, 'close', fail_client_close)
                      if cleanup_failed else nullcontext()):
                    try:
                        function(out, provider_arg=[[provider], [provider]])
                    except AllCandidatesExhausted as error:
                        assert error.details['safe_owner_exit'] is (not cleanup_failed)
                    else:
                        raise AssertionError('Rejected recognition became success')
                assert len(calls) == len(completed) == count
                saved = checkpoint(out)
                assert all(slot['status'] == 'failed' for slot in saved['slots'])
                assert saved['provider_cleanup_failed'] is cleanup_failed
                assert not out.exists()
        verdicts['all_rejected_checkpoint_and_cleanup_contract'] = True
        # Inject only the actual SDK cleanup boundary, never checkpoint edits.
        out = args.work_dir / 'service-cleanup-unconfirmed.md'
        reset([Reply(503, 'unavailable')])
        with patch.object(openai.OpenAI, 'close', fail_client_close):
            try:
                images(out, selected=batches[:1], provider_arg=service_provider)
            except AllCandidatesExhausted:
                pass
        assert inspect_image_service_recovery(out) == {
            'service_recovery_available': False, 'service_recovery_slot_count': 0,
            'reason': 'provider_cleanup_unconfirmed'}
        reset([])
        from ocrllm.errors import ResumeStateError
        try:
            images(out, selected=batches[:1], resume=True,
                   provider_arg=service_provider, service_recovery_only=True, service_recovery_batch_id="scenario-batch")
        except ResumeStateError as error:
            assert error.details['provider_calls_attempted'] == 0
        else:
            raise AssertionError('Unconfirmed cleanup admitted recovery')
        assert not calls
        missing = args.work_dir / 'service-missing.md'
        assert not inspect_image_service_recovery(missing)['service_recovery_available']
        missing.with_suffix('.ocrllm-state.json').write_text('{invalid checkpoint')
        assert not inspect_image_service_recovery(missing)['service_recovery_available']
        missing.with_suffix('.ocrllm-state.json').write_text('{"state_version":"unsupported"}')
        assert not inspect_image_service_recovery(missing)['service_recovery_available']
        verdicts['service_recovery_denies_cleanup_missing_corrupt_unsupported'] = True


        # An already requested stop still creates a resumable, zero-call plan.
        for name, function in [('audio', audio), ('images', images)]:
            reset([])
            stop.set()
            out = args.work_dir / f'preset-{name}.md'
            paused(lambda: function(out), 0)
            saved = checkpoint(out)
            assert not saved['usage'] and all(row['status'] == 'unresolved' for row in saved['slots'])
            if name == 'audio':
                assert all(row.get('recovery_attempts', 0) == 0 for row in saved['slots'])
                dispatch_confirmation(out, True)
            reset([Reply()] * (len(plan) if name == 'audio' else len(batches)))
            assert function(out, resume=True).status == 'complete'
        verdicts['preset_stop_zero_calls_and_reservations'] = True

        # Current responses finish; two concurrent lanes both persist before ack.
        for name, function in [('audio', audio), ('images', images)]:
            barrier = Barrier(2)
            reset([Reply(request_stop=True, barrier=barrier),
                   Reply(request_stop=True, barrier=barrier, delay=.3)])
            out = args.work_dir / f'concurrent-{name}.md'
            events = paused(lambda: function(out, provider_arg=[[provider], [provider]]), 2)
            saved = checkpoint(out)
            assert sum(row['status'] == 'settled' for row in saved['slots']) == 2
            assert sum(row['calls'] for row in saved['usage']) == 2
            assert sum(row['kind'] == 'unit_result' and row['data']['acceptance'] == 'durable_checkpoint'
                       for row in events) == 2
            reset([Reply()] * (len(plan) - 2 if name == 'audio' else len(batches) - 2))
            result = function(out, resume=True, provider_arg=[[provider], [provider]])
            assert result.status == 'complete' and result.metadata['reused_slot_count'] == 2
        verdicts['audio_and_image_lanes_drained_before_ack'] = True

        # Stop during the finite transient wait preserves its failure and usage.
        for name, function in [('audio', audio), ('images', images)]:
            reset([Reply(503, 'service_unavailable', stop_after=.3)])
            out = args.work_dir / f'transient-{name}.md'
            paused(lambda: function(out), 1)
            saved = checkpoint(out)
            assert saved['slots'][0]['error_code'] == 'PROVIDER_UNAVAILABLE'
            assert sum(row['calls'] for row in saved['usage']) == 1
            if name == 'audio':
                assert saved['slots'][0]['recovery_attempts'] == 1
                assert saved['slots'][0].get('output_limit_attempts', 0) == 0
                dispatch_confirmation(out, False, 'unverifiable_outcome')
            reset([Reply()] * (len(plan) if name == 'audio' else len(batches)))
            result = function(out, resume=True, **({'only_output_limit': True} if name == 'audio' else {}))
            assert result.status == 'complete'
            assert sum(row['calls'] for row in result.metadata['historical_provider_model_usage']) == 1
            if name == 'audio':
                assert checkpoint(out)['slots'][0]['recovery_attempts'] == 2
                dispatch_confirmation(out, True)
        verdicts['transient_wait_stops_without_losing_failure_or_usage'] = True
        verdicts['only_output_limit_resume_preserves_transient_remaining_budget'] = True

        # Last result saved, but Markdown has not yet been published.
        for name, function in [('audio', audio), ('images', images)]:
            reset([Reply(request_stop=True)])
            out = args.work_dir / f'publication-{name}.md'
            options = {'slices': whole} if name == 'audio' else {'selected': batches[:1]}
            paused(lambda: function(out, **options), 1)
            assert not out.exists() and inspect_markdown_job(out) == 'pending'
            if name == 'audio':
                dispatch_confirmation(out, True)
            reset([])
            result = function(out, resume=True, **options)
            assert result.status == 'complete' and result.metadata['provider_call_count'] == 0
            assert out.is_file() and inspect_markdown_job(out) == 'complete'
        verdicts['final_checkpoint_resumes_publication_with_zero_calls'] = True

        reset([Reply(value='NOSPEECH4OCRLLM', request_stop=True)])
        out = args.work_dir / 'no-speech.md'
        paused(lambda: audio(out), 1)
        assert checkpoint(out)['slots'][0]['no_speech'] is True
        assert checkpoint(out)['slots'][0]['status'] == 'settled'
        dispatch_confirmation(out, True)
        reset([Reply()] * 2)
        assert audio(out, resume=True).status == 'complete' and len(calls) == 2
        verdicts['no_speech_outcome_checkpointed_before_stop'] = True

        # Signal arrives after admission, while reservation is becoming durable.
        # The admitted request MUST run and settle; it must not become unknown.
        reset([Reply()])
        out = args.work_dir / 'reservation-race.md'
        original_replace = os.replace
        def stop_during_reservation(source, target):
            if Path(target) == out.with_suffix('.ocrllm-state.json'):
                candidate = json.loads(Path(source).read_text())['slots'][0]
                if candidate.get('recovery_attempts', 0) == 1 and candidate['status'] == 'unresolved':
                    # The new reservation exists only in the completed tempfile.
                    # Until replace, no provider HTTP can have started.
                    dispatch_confirmation(out, True)
                    assert not calls
                    original_replace(source, target)
                    # Now reserved, but the dispatch closure has not called HTTP.
                    dispatch_confirmation(out, False, 'unconfirmed_reservation')
                    assert not calls
                    stop.set()
                    return
            original_replace(source, target)
        os.replace = stop_during_reservation
        try:
            paused(lambda: audio(out, slices=whole), 1)
        finally:
            os.replace = original_replace
        saved = checkpoint(out)['slots'][0]
        assert saved['status'] == 'settled' and saved['recovery_attempts'] == 1
        dispatch_confirmation(out, True)
        reset([])
        assert audio(out, slices=whole, resume=True).metadata['provider_call_count'] == 0
        verdicts['post_admission_stop_does_not_abandon_reserved_attempt'] = True
        verdicts['reservation_query_changes_only_at_atomic_replace'] = True

        # A real output-cap reply is saved, then no second attempt or bisection
        # runs while stopped. Repeated pauses cannot replenish the leaf budget.
        out = args.work_dir / 'cap-budget.md'
        no_split = AudioOutputLimitPolicy(max_split_depth=0)
        for attempt in range(1, 4):
            reset([Reply(422, 'output_token_limit', request_stop=True)])
            function = recognize_audio_to_markdown if attempt == 1 else resume_audio_to_markdown
            paused(lambda: function(plan, provider=provider, output_path=out,
                audio_output_limit_policy=no_split, stop_requested=stop), 1)
            saved = checkpoint(out)['slots'][0]
            assert saved['recovery_attempts'] == attempt and saved['output_limit_attempts'] == attempt
            assert len(saved['output_limit_evidence']) == attempt
            dispatch_confirmation(out, True)
        reset([Reply(), Reply()])
        result = resume_audio_to_markdown(plan, provider=provider, output_path=out,
                                         audio_output_limit_policy=no_split, stop_requested=stop)
        assert result.status == 'partial' and len(calls) == 2
        assert checkpoint(out)['slots'][0]['recovery_attempts'] == 3
        verdicts['cap_failure_evidence_saved_and_pause_cannot_reset_budget'] = True

        # The previous cap's error fields remain during a later reservation;
        # they cannot confirm the new attempt before its own result is saved.
        reset([Reply(422, 'output_token_limit', request_stop=True)])
        out = args.work_dir / 'previous-cap-evidence.md'
        paused(lambda: audio(out), 1)
        dispatch_confirmation(out, True)
        reset([Reply(422, 'output_token_limit')])
        def stop_after_new_cap_reservation(source, target):
            if Path(target) == out.with_suffix('.ocrllm-state.json'):
                leaf = json.loads(Path(source).read_text())['slots'][0]
                if (leaf.get('recovery_attempts') == 2
                        and len(leaf.get('output_limit_evidence', [])) == 1):
                    dispatch_confirmation(out, True)
                    original_replace(source, target)
                    dispatch_confirmation(out, False, 'unconfirmed_reservation')
                    stop.set()
                    return
            original_replace(source, target)
        os.replace = stop_after_new_cap_reservation
        try:
            paused(lambda: audio(out, resume=True), 1)
        finally:
            os.replace = original_replace
        dispatch_confirmation(out, True)
        verdicts['previous_cap_cannot_confirm_later_reservation'] = True

        # Non-equal leaves [30s, 15s, 15s], then original 60s and short tail.
        # The right leaf remains pending, and successful siblings retain identity.
        cap = Reply(422, 'output_token_limit')
        reset([cap] * 3 + [Reply()] + [cap] * 3 + [Reply(request_stop=True)])
        out = args.work_dir / 'unequal-leaves.md'
        paused(lambda: audio(out), 8)
        saved = checkpoint(out)['slots'][0]
        assert [row['split_depth'] for row in saved['subslots']] == [1, 2, 2]
        assert [row['status'] for row in saved['subslots']] == ['settled', 'settled', 'unresolved']
        settled_before = saved['subslots'][:2]
        dispatch_confirmation(out, True)
        reset([Reply()] * 3)
        result = audio(out, resume=True, only_output_limit=True)
        assert result.status == 'complete' and len(calls) == 3
        after = checkpoint(out)
        assert after['slots'][0]['subslots'][:2] == settled_before
        assert after['slots'][-1]['logical_end_seconds'] - after['slots'][-1]['logical_start_seconds'] < 2
        dispatch_confirmation(out, True)
        verdicts['two_level_unequal_children_and_short_tail_resume'] = True

        # A stop at the saved bisection plan creates no child reservation.
        reset([cap] * 3)
        out = args.work_dir / 'split-boundary.md'
        def stop_after_split(source, target):
            original_replace(source, target)
            if Path(target) == out.with_suffix('.ocrllm-state.json'):
                if checkpoint(out)['slots'][0].get('subslots'):
                    stop.set()
        os.replace = stop_after_split
        try:
            paused(lambda: audio(out), 3)
        finally:
            os.replace = original_replace
        assert all(row.get('recovery_attempts', 0) == 0 for row in checkpoint(out)['slots'][0]['subslots'])
        assert inspect_audio_completion(out, audio_output_limit_policy=policy)['output_limit_recovery_available']
        dispatch_confirmation(out, True)
        reset([Reply()] * 4)
        assert audio(out, resume=True).status == 'complete' and len(calls) == 4
        verdicts['saved_split_stops_before_child_reservation'] = True

        # A historical unknown reservation blocks while it is a current leaf.
        # Once ordinary recovery splits that exhausted parent, its history must
        # not be mistaken for a live reservation on the new zero-budget leaves.
        reset([cap, cap])
        out = args.work_dir / 'unknown-ancestor.md'
        def interrupt_third_reservation(source, target):
            original_replace(source, target)
            if Path(target) == out.with_suffix('.ocrllm-state.json'):
                leaf = checkpoint(out)['slots'][0]
                if leaf.get('recovery_attempts') == 3:
                    raise KeyboardInterrupt('Synthetic unknown third reservation')
        os.replace = interrupt_third_reservation
        try:
            audio(out, slices=whole)
        except KeyboardInterrupt:
            pass
        else:
            raise AssertionError('Third reservation interruption did not happen')
        finally:
            os.replace = original_replace
        assert len(calls) == 2
        dispatch_confirmation(out, False, 'unconfirmed_reservation')
        reset([])
        os.replace = stop_after_split
        try:
            paused(lambda: audio(out, slices=whole, resume=True), 0)
        finally:
            os.replace = original_replace
        dispatch_confirmation(out, True)
        assert all(row.get('recovery_attempts', 0) == 0 for row in checkpoint(out)['slots'][0]['subslots'])
        verdicts['unknown_current_leaf_denied_but_inactive_ancestor_ignored'] = True

        # Unsupported legacy format and unknown adopted history are denied.
        reset([Reply(422, 'output_token_limit', request_stop=True)])
        out = args.work_dir / 'legacy-unconfirmed.md'
        paused(lambda: recognize_audio_to_markdown(whole, provider=provider,
                    output_path=out, stop_requested=stop), 1)
        dispatch_confirmation(out, False, 'unsupported_state')
        reset([])
        stop.set()
        paused(lambda: audio(out, slices=whole, resume=True), 0)
        dispatch_confirmation(out, False, 'unconfirmed_reservation')
        dispatch_confirmation(args.work_dir / 'absent.md', False, 'missing_state')
        verdicts['legacy_missing_and_unknown_history_are_not_confirmed'] = True

        # A real write failure outranks a simultaneously requested soft stop.
        reset([Reply(request_stop=True)])
        out = args.work_dir / 'write-failure.md'
        def fail_settled_replace(source, target):
            if Path(target) == out.with_suffix('.ocrllm-state.json'):
                candidate = json.loads(Path(source).read_text())
                if candidate['slots'][0]['status'] == 'settled':
                    raise OSError('Synthetic checkpoint write failure')
            original_replace(source, target)
        os.replace = fail_settled_replace
        try:
            audio(out)
        except OutputError as error:
            assert error.code == 'OUTPUT_WRITE_FAILED' and not error.details.get('safe_stop')
        else:
            raise AssertionError('Failed checkpoint was acknowledged as safe')
        finally:
            os.replace = original_replace
        verdicts['checkpoint_failure_never_acknowledged_as_safe_stop'] = True

        reset([])
        try:
            recognize_audio_to_markdown(plan, provider=provider,
                output_path=args.work_dir / 'invalid-signal.md', stop_requested=object())
        except ConfigError:
            pass
        else:
            raise AssertionError('Invalid signal was accepted')
        assert not calls
        verdicts['signal_shape_validated_before_dispatch'] = True

        report = {'passed': True, 'real_model_calls': 0, 'synthetic_http': True, **verdicts}
        (args.work_dir / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(report, indent=2), flush=True)
    finally:
        for timer in timers:
            timer.join(timeout=2)
        server.shutdown()
        server.server_close()
        thread.join()


if __name__ == '__main__':
    main()
