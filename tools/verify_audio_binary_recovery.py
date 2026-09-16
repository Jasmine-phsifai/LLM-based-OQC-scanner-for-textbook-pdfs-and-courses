"""Exercise real encoded audio and deterministic HTTP failures; no model calls.

This scenario proves bounded binary retries, failed-output references, legacy
adoption, interruption, transient retries, sibling reuse and unchanged gaps.
It does not prove ASR quality; production must separately observe real requests.
"""
import argparse
import json
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Event, Thread

import httpx

from ocrllm import (AudioGapPolicy, AudioOutputLimitPolicy, OpenAICompatibleSettings,
                    ProviderModel, inspect_audio_completion, inspect_markdown_job,
                    recognize_audio_to_markdown, resume_audio_to_markdown, split_audio, observation_context)
from ocrllm.audio.load_audio_ffmpeg_executable import load_audio_ffmpeg_executable
from ocrllm.errors import AllCandidatesExhausted, Cancelled, ConfigError, ResumeStateError


CAP = (422, 'output_token_limit')
OK = (200, 'Synthetic successful transcript.')


def main():
    # A provider's free description can mention a different machine code;
    # only the final canonical diagnostic block authorizes cap recovery.
    from types import SimpleNamespace
    from ocrllm.audio_gap_summary import is_output_limit_failure
    for description, expected in (
        ('Rejected. [provider_code=output_token_limit request_id=chatcmpl-test]', True),
        ('Rejected. [provider_code=output_token_limit]', True),
        ('Mentions provider_code=output_token_limit but has no diagnostic block.', False),
        ('Mentions [provider_code=output_token_limit] [provider_code=response_validation_failed]', False),
        ('Rejected. [provider_code=context_length_exceeded]', False),
        ('Rejected. [provider_code=response_incomplete]', False),
    ):
        assert is_output_limit_failure(SimpleNamespace(status='failed', error_code='PROVIDER_REQUEST_INVALID',
                                                       error_description=description)) is expected
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-dir', required=True, type=Path)
    parser.add_argument('--create-legacy-repetition-fixture', action='store_true',
                        help='Run only with historical fe68015 owner code to save a naturally interrupted loop tree.')
    parser.add_argument('--legacy-repetition-fixture', type=Path,
                        help='Read/resume a fixture produced by historical owner code; never edit its state.')
    args = parser.parse_args()
    args.work_dir.mkdir(parents=True, exist_ok=True)
    media = args.work_dir / 'input.mp3'
    subprocess.run([str(load_audio_ffmpeg_executable()), '-nostdin', '-v', 'error', '-y',
                    '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=16000', '-t', '601',
                    '-c:a', 'libmp3lame', str(media)], check=True, timeout=30)
    outcomes, calls = [], []
    historical_stop = Event()
    artifact_dir = args.work_dir / 'synthetic-service-artifacts'
    artifact_dir.mkdir(exist_ok=True)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_POST(self):
            request = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            assert all(item['type'] == 'input_audio' for item in request['messages'][0]['content'])
            index = len(calls)
            status, value = outcomes[index]
            request_id = f'chatcmpl-binary-{len(list(artifact_dir.iterdir()))}-{index}'
            calls.append((status, value))
            if args.create_legacy_repetition_fixture and len(calls) == 3:
                historical_stop.set()
            if status == 200:
                payload = {'id': request_id, 'model': 'synthetic-audio',
                           'choices': [{'index': 0, 'finish_reason': 'stop',
                                        'message': {'role': 'assistant', 'content': value}}],
                           'usage': {'prompt_tokens': 12, 'completion_tokens': 8}}
            else:
                artifact = artifact_dir / f'{request_id}.json'
                artifact.write_text(json.dumps({'raw_decode': '我' * 8192}), encoding='utf-8')
                payload = {'error': {'code': value, 'message': 'Synthetic rejected generation',
                    'details': {'generation_output': {'artifact_path': str(artifact),
                        'artifact_saved': True, 'request_id': request_id,
                        'input_audio_sha256': '0' * 64, 'input_tokens': 12,
                        'generated_tokens': 8192, 'max_new_tokens': 8192, 'reached_eos': False}}}}
            raw = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(raw)))
            self.send_header('x-request-id', request_id)
            self.end_headers()
            self.wfile.write(raw)

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    provider = ProviderModel(vendor='scenario', model='synthetic-audio', adapter_id='openai_compatible_chat',
        settings=OpenAICompatibleSettings(base_url=f'http://127.0.0.1:{server.server_port}/v1',
            send_audio_prompt=False, audio_response_validation='visible_text', capture_error_output=True),
        supports_audio=True, supports_plain_ocr=False, supports_detail_ocr=False,
        default_image_batch_size=None, default_audio_minutes=10,
        retry_rules={'PROVIDER_UNAVAILABLE': ('current', 8, 0), 'PROVIDER_REQUEST_INVALID': ('current', 8, 0)})
    policy = AudioOutputLimitPolicy()
    gap = AudioGapPolicy(max_failed_fraction=.05, max_failed_segment_seconds=120)
    plan = split_audio(media, interval_minutes=10, include_boundary_context=False)

    def reset(sequence):
        calls.clear()
        outcomes[:] = sequence

    def state(path):
        return json.loads(path.with_suffix('.ocrllm-state.json').read_text())

    def recognize(path, **kwargs):
        return recognize_audio_to_markdown(plan, provider=provider, output_path=path,
                                          audio_output_limit_policy=policy, audio_gap_policy=gap, **kwargs)

    try:
        if args.create_legacy_repetition_fixture:
            reset([(422, 'generation_repetition'), OK, (422, 'generation_repetition')])
            historical = args.work_dir / 'historical-repetition.md'
            try:
                recognize(historical, stop_requested=historical_stop)
            except Cancelled as error:
                assert error.details['provider_calls_attempted'] == 3
            else:
                raise AssertionError('Historical safe stop was not acknowledged')
            saved = state(historical)
            children = saved['slots'][0]['subslots']
            assert len(calls) == 3 and len(children) == 2
            assert children[0]['status'] == 'settled' and children[1]['status'] == 'failed'
            assert children[1]['recovery_attempts'] == 1
            import os
            pending_loop = args.work_dir / 'historical-pending-loop.md'
            original_replace = os.replace
            def stop_after_old_loop_split(source, destination, *args, **kwargs):
                original_replace(source, destination, *args, **kwargs)
                if Path(destination) == pending_loop.with_suffix('.ocrllm-state.json'):
                    saved = json.loads(Path(destination).read_text())
                    if saved['slots'][0].get('subslots'):
                        raise KeyboardInterrupt('Historical loop children persisted before their first dispatch')
            reset([(422, 'generation_repetition')])
            os.replace = stop_after_old_loop_split
            try:
                recognize(pending_loop)
            except KeyboardInterrupt:
                pass
            finally:
                os.replace = original_replace
            assert len(calls) == 1
            assert all(row['status'] == 'unresolved' for row in state(pending_loop)['slots'][0]['subslots'])
            print('Saved historical public-API loop trees: settled/failed siblings and unstarted children; no state edits.')
            return
        # A loop is a validation failure, not a token-cap split request. Its
        # original range consumes at most the first call plus two retries.
        reset([(422, 'generation_repetition')] * 3 + [OK])
        repeated_out = args.work_dir / 'all-repetition.md'
        repeated_result = recognize(repeated_out)
        assert repeated_result.status == 'partial' and len(calls) == 4
        repeated_state = state(repeated_out)
        repeated_leaf = repeated_state['slots'][0]
        assert not repeated_leaf.get('subslots') and repeated_leaf['recovery_attempts'] == 3
        assert repeated_leaf.get('output_limit_attempts', 0) == 0
        assert not repeated_result.metadata['accepted_with_gaps']
        assert not repeated_result.metadata['output_limit_failure_evidence']
        assert not repeated_result.metadata['output_limit_exhausted_segments']
        assert len(repeated_result.metadata['generation_repetition_failure_evidence']) == 3
        assert all(r['provider_code'] == 'generation_repetition'
                   and r['generation_output']['artifact_saved']
                   and Path(r['generation_output']['artifact_path']).is_file()
                   for r in repeated_result.metadata['generation_repetition_failure_evidence'])
        assert repeated_result.metadata['generation_repetition_failed_segments'][0]['retry_exhausted']
        assert not inspect_audio_completion(repeated_out, audio_output_limit_policy=policy)['output_limit_recovery_available']
        before_calls = len(calls)
        resume_audio_to_markdown(plan, provider=provider, output_path=repeated_out)
        assert len(calls) == before_calls
        reset([(422, 'generation_repetition')] * 2 + [OK, OK])
        loop_recovered_out = args.work_dir / 'loop-same-range-recovered.md'
        loop_recovered = recognize(loop_recovered_out)
        assert loop_recovered.status == 'complete' and len(calls) == 4
        assert not state(loop_recovered_out)['slots'][0].get('subslots')
        assert len(loop_recovered.metadata['generation_repetition_failure_evidence']) == 2

        legacy_loop_checked = False
        if args.legacy_repetition_fixture:
            historical = args.legacy_repetition_fixture / 'historical-repetition.md'
            historical_plan = split_audio(args.legacy_repetition_fixture / 'input.mp3',
                interval_minutes=10, include_boundary_context=False)
            old = state(historical)
            old_children = old['slots'][0]['subslots']
            assert len(old_children) == 2 and old_children[1]['recovery_attempts'] == 1
            before = historical.with_suffix('.ocrllm-state.json').read_bytes()
            inspection = inspect_audio_completion(historical, audio_output_limit_policy=policy)
            assert not inspection['output_limit_recovery_available']
            assert inspection['output_limit_recovery_candidates'] == []
            assert inspection['output_limit_failure_evidence'] == []
            assert len(inspection['generation_repetition_failure_evidence']) == 2
            assert historical.with_suffix('.ocrllm-state.json').read_bytes() == before
            reset([(422, 'generation_repetition')] * 2 + [OK])
            restored = resume_audio_to_markdown(historical_plan, provider=provider,
                output_path=historical, audio_output_limit_policy=policy)
            assert restored.status == 'partial' and len(calls) == 3
            children = state(historical)['slots'][0]['subslots']
            assert len(children) == 2 and children[0] == old_children[0]
            assert children[1]['split_depth'] == 1 and children[1]['recovery_attempts'] == 3
            assert len(restored.metadata['generation_repetition_failure_evidence']) == 4
            assert not restored.metadata['output_limit_failure_evidence']
            again = resume_audio_to_markdown(historical_plan, provider=provider, output_path=historical)
            assert again.metadata['provider_call_count'] == 0 and len(calls) == 3
            pending_loop = args.legacy_repetition_fixture / 'historical-pending-loop.md'
            before = pending_loop.with_suffix('.ocrllm-state.json').read_bytes()
            inspection = inspect_audio_completion(pending_loop, audio_output_limit_policy=policy)
            assert not inspection['output_limit_recovery_available']
            assert inspection['output_limit_recovery_candidates'] == []
            assert pending_loop.with_suffix('.ocrllm-state.json').read_bytes() == before
            reset([(422, 'generation_repetition')] * 3 + [OK, OK])
            continued = resume_audio_to_markdown(historical_plan, provider=provider, output_path=pending_loop)
            assert continued.status == 'partial' and len(calls) == 5
            assert len(state(pending_loop)['slots'][0]['subslots']) == 2
            assert not inspect_audio_completion(pending_loop, audio_output_limit_policy=policy)['output_limit_recovery_available']
            legacy_loop_checked = True
        print('Passed: loops remain unsplit; at most three attempts, evidence retained, exhausted resume zero calls.', flush=True)

        # The original 600-second interval fails at every level; tail continues.
        reset([CAP] * 21 + [OK])
        out = args.work_dir / 'all-cap.md'
        result = recognize(out)
        assert result.status == 'partial' and len(calls) == 22
        saved = state(out)
        leaves = saved['slots'][0]['subslots']
        assert len(leaves) == 4 and all(row['split_depth'] == 2 and row['recovery_attempts'] == 3 for row in leaves)
        assert all(row['logical_end_seconds'] - row['logical_start_seconds'] == 150 for row in leaves)
        assert result.metadata['failed_seconds'] == 600 and not result.metadata['gap_threshold_met']
        assert not inspect_audio_completion(out, audio_output_limit_policy=policy)['output_limit_recovery_available']
        evidence = result.metadata['output_limit_failure_evidence']
        assert len(evidence) == 21
        assert all(Path(row['generation_output']['artifact_path']).is_file() for row in evidence)
        assert all(row['generation_output']['generated_tokens'] == 8192 for row in evidence)
        assert '我我我' not in result.markdown
        assert inspect_audio_completion(out)['audio_output_limit_policy']['max_split_depth'] == 2
        repeated = resume_audio_to_markdown(plan, provider=provider, output_path=out)
        assert repeated.status == 'partial' and repeated.metadata['provider_call_count'] == 0 and len(calls) == 22

        print('Passed: 21-attempt tree, artifact refs, zero-call exhausted resume.', flush=True)

        # One 5-minute child settles, only its failed sibling divides further.
        reset([CAP] * 3 + [OK] + [CAP] * 3 + [OK, OK, OK])
        recovered = args.work_dir / 'recovered.md'
        result = recognize(recovered)
        assert result.status == 'complete' and len(calls) == 10
        saved = state(recovered)
        assert [row['split_depth'] for row in saved['slots'][0]['subslots']] == [1, 2, 2]
        assert saved['slots'][0]['subslots'][0]['recovery_attempts'] == 1
        assert len(result.metadata['output_limit_failure_evidence']) == 6
        assert inspect_markdown_job(recovered) == 'complete'
        resumed = resume_audio_to_markdown(plan, provider=provider, output_path=recovered)
        assert resumed.status == 'complete' and resumed.metadata['provider_call_count'] == 0
        recovered.unlink()
        rebuilt = resume_audio_to_markdown(plan, provider=provider, output_path=recovered)
        assert rebuilt.status == 'complete' and rebuilt.metadata['provider_call_count'] == 0 and len(calls) == 10

        print('Passed: settled sibling reuse and completed-state evidence retention.', flush=True)

        # Interrupt after the third reservation, before its wire request. It is
        # spent but unconfirmed: resume divides after only two recorded cap replies.
        reset([CAP] * 21 + [OK])
        interrupted = args.work_dir / 'interrupted.md'
        original_send = httpx.Client.send
        def interrupt_send(client, *args, **kwargs):
            if len(calls) == 2:
                raise KeyboardInterrupt('Synthetic interruption after saved third reservation')
            return original_send(client, *args, **kwargs)
        httpx.Client.send = interrupt_send
        try:
            recognize(interrupted)
        except KeyboardInterrupt:
            pass
        else:
            raise AssertionError('Missing transport interruption')
        finally:
            httpx.Client.send = original_send
        first = state(interrupted)['slots'][0]
        assert first['recovery_attempts'] == 3 and first['output_limit_attempts'] == 2
        # The original unknown attempt is not repeated. Two child ranges and
        # four grandchildren can still consume their 18 independent attempts.
        outcomes[:] = [CAP] * 20 + [OK]
        resumed = resume_audio_to_markdown(plan, provider=provider, output_path=interrupted)
        assert resumed.metadata['provider_call_count'] == 19 and len(calls) == 21
        assert state(interrupted)['slots'][0]['output_limit_attempts'] == 2

        print('Passed: interruption consumes third reservation without a third confirmed cap.', flush=True)

        # Existing provider transient retry settings are honored within three
        # reserved attempts, without a hidden ninth retry or a binary split.
        reset([(503, 'service_unavailable')] * 3 + [OK])
        temporary = args.work_dir / 'temporary.md'
        result = recognize(temporary)
        assert result.status == 'partial' and len(calls) == 4
        assert not state(temporary)['slots'][0].get('subslots')
        assert not result.metadata['gap_retry_evidence_sufficient']
        assert not inspect_audio_completion(temporary, audio_output_limit_policy=policy)['output_limit_recovery_available']
        reset([(503, 'service_unavailable'), OK, OK])
        temporary_recovered = recognize(args.work_dir / 'temporary-recovered.md')
        assert temporary_recovered.status == 'complete' and len(calls) == 3

        print('Passed: original transient rules survive within the three-attempt cap.', flush=True)

        # A v3 2-minute leaf has already used one split and three known cap
        # attempts; only that leaf becomes two 1-minute ranges on adoption.
        old_media = args.work_dir / 'legacy.mp3'
        subprocess.run([str(load_audio_ffmpeg_executable()), '-nostdin', '-v', 'error', '-y',
                        '-i', str(media), '-t', '241', '-c:a', 'libmp3lame', str(old_media)],
                       check=True, timeout=30)
        old_plan = split_audio(old_media, interval_minutes=-1)
        # The old path intentionally has no generic request-invalid retry rule.
        old_provider = ProviderModel(vendor=provider.vendor, model=provider.model,
            adapter_id=provider.adapter_id, settings=provider.settings,
            supports_audio=True, supports_plain_ocr=False, supports_detail_ocr=False,
            default_image_batch_size=None, default_audio_minutes=10, retry_rules={})
        legacy = args.work_dir / 'legacy.md'
        reset([CAP, OK, CAP, CAP, CAP, OK])
        old = recognize_audio_to_markdown(old_plan, provider=old_provider, output_path=legacy,
                                         failed_slice_minutes=2, audio_gap_policy=gap)
        assert old.status == 'partial' and len(calls) == 6
        old_children = state(legacy)['slots'][0]['subslots']
        checkpoint_before_inspect = legacy.with_suffix('.ocrllm-state.json').read_bytes()
        eligible = inspect_audio_completion(legacy, audio_output_limit_policy=policy)
        assert eligible['output_limit_recovery_available']
        assert eligible['output_limit_recovery_candidates'][0]['action'] == 'bisect'
        assert eligible['output_limit_recovery_candidate_seconds'] == 120
        assert legacy.with_suffix('.ocrllm-state.json').read_bytes() == checkpoint_before_inspect
        reset([OK, OK])
        adopted = resume_audio_to_markdown(old_plan, provider=provider, output_path=legacy,
                                          audio_output_limit_policy=policy)
        assert adopted.status == 'complete' and len(calls) == 2
        new_children = state(legacy)['slots'][0]['subslots']
        assert [row['split_depth'] for row in new_children] == [1, 2, 2, 1]
        assert new_children[0]['markdown'] == old_children[0]['markdown']
        assert new_children[-1]['markdown'] == old_children[-1]['markdown']
        assert new_children[0]['recovery_attempts'] == 0  # no fresh call for settled work
        try:
            resume_audio_to_markdown(old_plan, provider=provider, output_path=legacy,
                                    audio_output_limit_policy=AudioOutputLimitPolicy(max_split_depth=1))
        except ResumeStateError:
            pass
        else:
            raise AssertionError('Saved policy was reset')
        try:
            recognize(args.work_dir / 'conflicting.md', failed_slice_minutes=2)
        except ConfigError:
            pass
        else:
            raise AssertionError('Two splitting policies were combined')
        # All-candidate exhaustion has no Markdown, but the owner inspection
        # still exposes the retained policy and every rejected-output reference.
        short_media = args.work_dir / 'short.mp3'
        subprocess.run([str(load_audio_ffmpeg_executable()), '-nostdin', '-v', 'error', '-y',
                        '-i', str(media), '-t', '61', '-c:a', 'libmp3lame', str(short_media)],
                       check=True, timeout=30)
        short_plan = split_audio(short_media, interval_minutes=-1)
        no_split = AudioOutputLimitPolicy(max_split_depth=0)
        all_failed = args.work_dir / 'all-failed.md'
        reset([CAP] * 3)
        try:
            recognize_audio_to_markdown(short_plan, provider=provider, output_path=all_failed,
                                        audio_output_limit_policy=no_split, audio_gap_policy=gap)
        except AllCandidatesExhausted as error:
            assert error.details['provider_calls_attempted'] == 3
        else:
            raise AssertionError('All failed audio was accepted')
        summary = inspect_audio_completion(all_failed)
        assert summary['status'] == 'partial' and not all_failed.exists()
        assert len(summary['output_limit_failure_evidence']) == 3
        assert summary['audio_output_limit_policy']['max_split_depth'] == 0
        # A reservation interrupted at a final leaf cannot become a third
        # confirmed cap, and ordinary resume cannot issue an uncounted request.
        unknown_leaf = args.work_dir / 'unknown-leaf.md'
        reset([CAP] * 3)
        httpx.Client.send = interrupt_send
        try:
            recognize_audio_to_markdown(short_plan, provider=provider, output_path=unknown_leaf,
                                        audio_output_limit_policy=no_split, audio_gap_policy=gap)
        except KeyboardInterrupt:
            pass
        finally:
            httpx.Client.send = original_send
        try:
            resume_audio_to_markdown(short_plan, provider=provider, output_path=unknown_leaf)
        except AllCandidatesExhausted as error:
            assert error.details['provider_calls_attempted'] == 0
        else:
            raise AssertionError('Unknown final attempt was treated as settled')
        unknown = inspect_audio_completion(unknown_leaf)
        assert len(calls) == 2 and not unknown['gap_retry_evidence_sufficient']
        assert unknown['output_limit_exhausted_segments'][0]['confirmed_consecutive_output_limits'] == 2
        # An old partial MD must not become complete merely because the final
        # provider result was saved just before Markdown publication crashed.
        import os
        publication = args.work_dir / 'publication.md'
        publication_plan = split_audio(short_media, interval_minutes=1, include_boundary_context=False)
        reset([(401, 'invalid_api_key'), OK])
        partial = recognize_audio_to_markdown(publication_plan, provider=provider, output_path=publication,
                                              audio_output_limit_policy=policy, audio_gap_policy=gap)
        assert partial.status == 'partial' and len(calls) == 2
        before = publication.read_bytes()
        original_replace = os.replace
        def interrupt_publication(source, destination, *args, **kwargs):
            if Path(destination) == publication:
                raise KeyboardInterrupt('Synthetic crash before final MD replace')
            return original_replace(source, destination, *args, **kwargs)
        reset([OK])
        os.replace = interrupt_publication
        try:
            resume_audio_to_markdown(publication_plan, provider=provider, output_path=publication)
        except KeyboardInterrupt:
            pass
        else:
            raise AssertionError('Missing final-publication interruption')
        finally:
            os.replace = original_replace
        assert all(slot['status'] == 'settled' for slot in state(publication)['slots'])
        assert publication.read_bytes() == before
        assert inspect_markdown_job(publication) == 'pending'
        publication_summary = inspect_audio_completion(publication)
        assert publication_summary['status'] == 'partial'
        assert publication_summary['audio_publication_pending'] and publication_summary['output_limit_recovery_available']
        assert publication_summary['output_limit_recovery_candidate_seconds'] == 0
        published = resume_audio_to_markdown(publication_plan, provider=provider, output_path=publication)
        assert published.status == 'complete' and published.metadata['provider_call_count'] == 0 and len(calls) == 1
        assert inspect_markdown_job(publication) == 'complete' and '**FAIL**' not in publication.read_text()
        # Accepted gaps are never reopened for inference, but a missing or
        # stale final MD remains a zero-inference publication recovery candidate.
        accepted_gaps = args.work_dir / 'accepted-gaps.md'
        reset([CAP] * 3 + [OK] + [CAP] * 3 + [OK] + [CAP] * 3 + [OK])
        accepted = recognize_audio_to_markdown(publication_plan, provider=provider, output_path=accepted_gaps,
            audio_output_limit_policy=policy,
            audio_gap_policy=AudioGapPolicy(max_failed_fraction=.3, max_failed_segment_seconds=120))
        assert accepted.status == 'complete_with_gaps' and len(calls) == 12
        assert not inspect_audio_completion(accepted_gaps, audio_output_limit_policy=policy)['output_limit_recovery_available']
        expected_md = accepted_gaps.read_bytes()
        for stale_contents in (b'Old partial Markdown before final publication.', None):
            if stale_contents is None:
                accepted_gaps.unlink()
            else:
                accepted_gaps.write_bytes(stale_contents)
            missing_publication = inspect_audio_completion(accepted_gaps, audio_output_limit_policy=policy)
            assert missing_publication['status'] == 'partial' and missing_publication['audio_publication_pending']
            assert missing_publication['output_limit_recovery_available']
            assert missing_publication['output_limit_recovery_candidate_seconds'] == 0
            assert missing_publication['output_limit_recovery_candidates'] == []
            rebuilt_gaps = resume_audio_to_markdown(publication_plan, provider=provider, output_path=accepted_gaps)
            assert rebuilt_gaps.status == 'complete_with_gaps' and rebuilt_gaps.metadata['provider_call_count'] == 0
            assert len(calls) == 12 and accepted_gaps.read_bytes() == expected_md
            assert not inspect_audio_completion(accepted_gaps)['output_limit_recovery_available']
        # Old v2 has only one saved failure, not the history of earlier resumes.
        legacy_v2 = args.work_dir / 'legacy-v2.md'
        reset([CAP, OK, CAP, OK])
        old = recognize_audio_to_markdown(old_plan, provider=old_provider, output_path=legacy_v2,
                                         failed_slice_minutes=2)
        assert old.status == 'partial' and len(calls) == 4
        eligible = inspect_audio_completion(legacy_v2, audio_output_limit_policy=policy)
        assert eligible['output_limit_recovery_candidates'][0]['action'] == 'retry'
        assert eligible['output_limit_recovery_candidates'][0]['attempts_remaining'] == 2
        reset([CAP, CAP, OK, OK])
        adopted = resume_audio_to_markdown(old_plan, provider=provider, output_path=legacy_v2,
                                          audio_output_limit_policy=policy, audio_gap_policy=gap)
        assert adopted.status == 'complete' and len(calls) == 4
        assert any(row.get('historical_attempts_unknown') is True
                   for row in adopted.metadata['output_limit_failure_evidence'])
        print('Passed: legacy v2/v3 adoption and all-failed public inspection.', flush=True)
        # The final original interval has a non-integer, non-fixed duration.
        # Its right successful child moves from index 1 to 2 when only the left
        # child divides again; source-range identity and Markdown must survive.
        uneven_media = args.work_dir / 'uneven-tail.mp3'
        subprocess.run([str(load_audio_ffmpeg_executable()), '-nostdin', '-v', 'error', '-y',
                        '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=16000', '-t', '661.375',
                        '-c:a', 'libmp3lame', str(uneven_media)], check=True, timeout=30)
        uneven_plan = split_audio(uneven_media, interval_minutes=10, include_boundary_context=False)
        uneven = args.work_dir / 'uneven-tail.md'
        assert 60 < uneven_plan[-1].logical_end_seconds - uneven_plan[-1].logical_start_seconds < 62
        events = []
        reset([(200, 'Original first interval.')] + [CAP] * 6
              + [(200, 'Right sibling preserved.'), (200, 'First grandchild preserved.'), OK])
        def interrupt_uneven(client, *args, **kwargs):
            if len(calls) == 9:
                raise KeyboardInterrupt('After unequal settled siblings, before final grandchild wire request')
            return original_send(client, *args, **kwargs)
        httpx.Client.send = interrupt_uneven
        try:
            with observation_context(sink=events.append, lecture_id='synthetic-uneven'):
                recognize_audio_to_markdown(uneven_plan, provider=provider, output_path=uneven,
                                            audio_output_limit_policy=policy, audio_gap_policy=gap)
        except KeyboardInterrupt:
            pass
        else:
            raise AssertionError('Missing unequal-tail interruption')
        finally:
            httpx.Client.send = original_send
        saved_uneven = state(uneven)
        children = saved_uneven['slots'][-1]['subslots']
        assert [row['split_depth'] for row in children] == [2, 2, 1]
        assert children[0]['status'] == children[2]['status'] == 'settled'
        assert children[1]['status'] == 'unresolved' and children[1]['recovery_attempts'] == 1
        lengths = [row['logical_end_seconds'] - row['logical_start_seconds'] for row in children]
        assert abs(lengths[0] - lengths[1]) < 1e-9 and abs(lengths[2] - 2 * lengths[0]) < 1e-9
        assert children[0]['logical_start_seconds'] == uneven_plan[-1].logical_start_seconds
        assert children[-1]['logical_end_seconds'] == uneven_plan[-1].logical_end_seconds
        assert all(left['logical_end_seconds'] == right['logical_start_seconds']
                   for left, right in zip(children, children[1:]))
        right_start = children[-1]['logical_start_seconds']
        before_events = list(events)
        before_checkpoint = uneven.with_suffix('.ocrllm-state.json').read_bytes()
        candidate = inspect_audio_completion(uneven, audio_output_limit_policy=policy)
        assert candidate['output_limit_recovery_available']
        assert len(candidate['output_limit_recovery_candidates']) == 1
        assert candidate['output_limit_recovery_candidates'][0]['action'] == 'continue'
        assert abs(candidate['output_limit_recovery_candidate_seconds'] - lengths[1]) < 1e-9
        assert uneven.with_suffix('.ocrllm-state.json').read_bytes() == before_checkpoint
        with observation_context(sink=events.append, lecture_id='synthetic-uneven'):
            completed = resume_audio_to_markdown(uneven_plan, provider=provider, output_path=uneven)
        assert completed.status == 'complete' and completed.metadata['provider_call_count'] == 1 and len(calls) == 10
        resumed_children = state(uneven)['slots'][-1]['subslots']
        assert resumed_children[0] == children[0] and resumed_children[2] == children[2]
        prior_right = [event['data'] for event in before_events if event['kind'] == 'unit_result'
                       and event['data'].get('source_start_seconds') == right_start
                       and event['data'].get('status') == 'settled'][0]
        reused_right = [event['data'] for event in events[len(before_events):] if event['kind'] == 'unit_result'
                        and event['data'].get('source_start_seconds') == right_start
                        and event['data'].get('reused')][0]
        assert prior_right['logical_unit_id'] == reused_right['logical_unit_id']
        assert reused_right['valid_units'] == 0
        result_events = [event['data'] for event in events if event['kind'] == 'unit_result'
                         and event['data'].get('status') == 'settled' and not event['data'].get('reused')]
        unique_ranges = {(row['source_start_seconds'], row['source_end_seconds']): row for row in result_events}
        coverage = sum(end - start for start, end in unique_ranges)
        assert abs(coverage - uneven_plan[-1].logical_end_seconds) < 1e-9
        assert completed.markdown.index('First grandchild preserved.') < completed.markdown.index('Right sibling preserved.')
        assert not inspect_audio_completion(uneven)['output_limit_recovery_available']
        # Interrupt exactly after a fresh binary child plan is durable, before
        # dispatch reserves any child. This must remain discoverable recovery.
        derived = args.work_dir / 'pending-derived.md'
        reset([CAP] * 3 + [OK, OK])
        original_replace = os.replace
        def interrupt_after_split(source, destination, *args, **kwargs):
            original_replace(source, destination, *args, **kwargs)
            if Path(destination) == derived.with_suffix('.ocrllm-state.json'):
                saved = json.loads(Path(destination).read_text())
                if saved['slots'][0].get('subslots'):
                    raise KeyboardInterrupt('Binary children saved; no child dispatched')
        os.replace = interrupt_after_split
        try:
            recognize_audio_to_markdown(short_plan, provider=provider, output_path=derived,
                                        audio_output_limit_policy=policy, audio_gap_policy=gap)
        except KeyboardInterrupt:
            pass
        finally:
            os.replace = original_replace
        assert len(calls) == 3
        candidate = inspect_audio_completion(derived, audio_output_limit_policy=policy)
        assert candidate['output_limit_recovery_available']
        assert len(candidate['output_limit_recovery_candidates']) == 2
        assert all(row['action'] == 'continue' and row['attempts_remaining'] == 3
                   for row in candidate['output_limit_recovery_candidates'])
        continued = resume_audio_to_markdown(short_plan, provider=provider, output_path=derived)
        assert continued.status == 'complete' and continued.metadata['provider_call_count'] == 2
        print('Passed: unequal tail, reindexed sibling identity, logical coverage and pending cap-derived priority.', flush=True)
        report = {'repetition_calls': 4, 'repetition_same_range_max_attempts': 3,
                  'repetition_new_subslots': 0, 'repetition_exhausted_resume_calls': 0,
                  'repetition_gap_accepted': False, 'repetition_evidence_retained': True,
                  'historical_loop_tree_resumed_without_new_subdivision': legacy_loop_checked,
                  'passed': True, 'real_model_calls': 0, 'synthetic_http': True,
                  'worst_case_original_range_calls': 21, 'worst_case_tail_calls': 1,
                  'durable_failed_artifact_references': 21, 'deepest_segment_seconds': 150,
                  'successful_sibling_reused': True, 'complete_checkpoint_retained': True,
                  'exhausted_resume_calls': 0, 'unknown_attempt_not_reissued': True,
                  'transient_retry_calls_bounded': 3, 'legacy_120_to_60_new_calls': 2,
                  'legacy_v2_history_unknown_explicit': True, 'all_failed_inspection_exposes_evidence': True,
                  'unknown_final_attempt_not_gap_evidence': True, 'interrupted_publication_zero_call_resume': True,
                  'unequal_tail_resume_current_calls': 1, 'reindexed_sibling_identity_preserved': True,
                  'logical_source_coverage_exact': True, 'pending_cap_derived_recovery_available': True,
                  'old_cap_priority_inspection_read_only': True, 'only_canonical_output_limit_diagnostic': True,
                  'publication_only_recovery_available': True, 'accepted_gap_stale_md_zero_inference_rebuild': True}
        (args.work_dir / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(report))
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


if __name__ == '__main__':
    main()
