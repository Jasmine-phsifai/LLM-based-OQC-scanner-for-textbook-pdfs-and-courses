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
from threading import Thread

import httpx

from ocrllm import (AudioGapPolicy, AudioOutputLimitPolicy, OpenAICompatibleSettings,
                    ProviderModel, inspect_audio_completion, inspect_markdown_job,
                    recognize_audio_to_markdown, resume_audio_to_markdown, split_audio)
from ocrllm.audio.load_audio_ffmpeg_executable import load_audio_ffmpeg_executable
from ocrllm.errors import AllCandidatesExhausted, ConfigError, ResumeStateError


CAP = (422, 'output_token_limit')
OK = (200, 'Synthetic successful transcript.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-dir', required=True, type=Path)
    args = parser.parse_args()
    args.work_dir.mkdir(parents=True, exist_ok=True)
    media = args.work_dir / 'input.mp3'
    subprocess.run([str(load_audio_ffmpeg_executable()), '-nostdin', '-v', 'error', '-y',
                    '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=16000', '-t', '601',
                    '-c:a', 'libmp3lame', str(media)], check=True, timeout=30)
    outcomes, calls = [], []
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
        assert inspect_audio_completion(publication)['status'] == 'partial'
        published = resume_audio_to_markdown(publication_plan, provider=provider, output_path=publication)
        assert published.status == 'complete' and published.metadata['provider_call_count'] == 0 and len(calls) == 1
        assert inspect_markdown_job(publication) == 'complete' and '**FAIL**' not in publication.read_text()
        # Old v2 has only one saved failure, not the history of earlier resumes.
        legacy_v2 = args.work_dir / 'legacy-v2.md'
        reset([CAP, OK, CAP, OK])
        old = recognize_audio_to_markdown(old_plan, provider=old_provider, output_path=legacy_v2,
                                         failed_slice_minutes=2)
        assert old.status == 'partial' and len(calls) == 4
        reset([CAP, CAP, OK, OK])
        adopted = resume_audio_to_markdown(old_plan, provider=provider, output_path=legacy_v2,
                                          audio_output_limit_policy=policy, audio_gap_policy=gap)
        assert adopted.status == 'complete' and len(calls) == 4
        assert any(row.get('historical_attempts_unknown') is True
                   for row in adopted.metadata['output_limit_failure_evidence'])
        print('Passed: legacy v2/v3 adoption and all-failed public inspection.', flush=True)
        report = {'passed': True, 'real_model_calls': 0, 'synthetic_http': True,
                  'worst_case_original_range_calls': 21, 'worst_case_tail_calls': 1,
                  'durable_failed_artifact_references': 21, 'deepest_segment_seconds': 150,
                  'successful_sibling_reused': True, 'complete_checkpoint_retained': True,
                  'exhausted_resume_calls': 0, 'unknown_attempt_not_reissued': True,
                  'transient_retry_calls_bounded': 3, 'legacy_120_to_60_new_calls': 2,
                  'legacy_v2_history_unknown_explicit': True, 'all_failed_inspection_exposes_evidence': True,
                  'unknown_final_attempt_not_gap_evidence': True, 'interrupted_publication_zero_call_resume': True}
        (args.work_dir / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(report))
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


if __name__ == '__main__':
    main()
