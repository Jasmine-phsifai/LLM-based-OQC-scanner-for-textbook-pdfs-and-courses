"""Prove merged safe-stop with encoded media and deterministic local HTTP.

No model service is called. OS replace injection covers the exact admission /
reservation race and failed checkpoint writes; no OCRLLM internals are mocked.
"""

import argparse
import json
import os
import subprocess
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Barrier, Event, Lock, Thread, Timer

from PIL import Image

from ocrllm import (
    AudioOutputLimitPolicy, OpenAICompatibleSettings, ProviderModel,
    inspect_audio_completion, inspect_markdown_job, observation_context,
    recognize_audio_to_markdown, recognize_images_to_markdown,
    resume_audio_to_markdown, resume_images_to_markdown, split_audio,
)
from ocrllm.audio.load_audio_ffmpeg_executable import load_audio_ffmpeg_executable
from ocrllm.errors import Cancelled, ConfigError, OutputError


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
