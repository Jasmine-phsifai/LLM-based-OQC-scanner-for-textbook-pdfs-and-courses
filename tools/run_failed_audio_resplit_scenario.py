"""Recover a real partial audio job, interrupt between real calls, then resume.

This scenario reads checkpoint evidence but never edits it. All transitions and
Markdown output go through the public API. No provider result is fabricated.
"""
import argparse
import json
import time
from pathlib import Path

from ocrllm import (ProviderModel, OpenAICompatibleSettings, split_audio,
                    resume_audio_to_markdown, inspect_markdown_job)
from ocrllm.merged_audio_resume_state import MergedAudioResumeState
from ocrllm.output.resolve_resume_state_path import resolve_resume_state_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--base-url', required=True)
    parser.add_argument('--model', required=True)
    parser.add_argument('--original-minutes', type=int, default=10)
    parser.add_argument('--failed-minutes', type=int, default=2)
    args = parser.parse_args()
    provider = ProviderModel(vendor='local-benchmark', model=args.model,
        adapter_id='openai_compatible_chat', settings=OpenAICompatibleSettings(
            base_url=args.base_url, send_audio_prompt=False, response_validation='nonempty_text'),
        supports_audio=True, supports_plain_ocr=False, supports_detail_ocr=False,
        default_image_batch_size=None, default_audio_minutes=args.original_minutes, retry_rules={})
    plan = split_audio(args.source, interval_minutes=args.original_minutes, include_boundary_context=False)
    state_path = resolve_resume_state_path(args.output)
    before = MergedAudioResumeState.from_bytes(state_path.read_bytes())
    settled = {slot.index: slot for slot in before.slots if slot.status == 'settled'}
    assert settled and any(slot.status == 'failed' for slot in before.slots)
    report = {'initial_settled': len(settled), 'interruption_injected_between_requests': True}
    def save():
        args.report.write_text(json.dumps(report, indent=2, default=lambda v:dict(v))+'\n')
    import httpx
    original_send = httpx.Client.send
    calls = 0
    def interrupt_after_two(client, request, *a, **kw):
        nonlocal calls
        if calls == 2:
            raise KeyboardInterrupt('scenario interruption before third provider request')
        calls += 1
        return original_send(client, request, *a, **kw)
    started = time.monotonic()
    httpx.Client.send = interrupt_after_two
    try:
        resume_audio_to_markdown(plan, provider=provider, output_path=args.output,
                                timeout_seconds=600, failed_slice_minutes=args.failed_minutes)
        raise AssertionError('Expected deliberate process-level interruption')
    except KeyboardInterrupt:
        report['interrupted_calls'] = calls
        report['interrupted_seconds'] = time.monotonic()-started
    finally:
        httpx.Client.send = original_send
    mid = MergedAudioResumeState.from_bytes(state_path.read_bytes())
    assert all(mid.slots[index] == slot for index, slot in settled.items())
    report['settled_subslots_after_interruption'] = sum(child.status=='settled' for slot in mid.slots for child in slot.subslots)
    report['pending_after_interruption'] = inspect_markdown_job(args.output)
    report['original_settled_unchanged'] = True
    save()
    started = time.monotonic()
    result = resume_audio_to_markdown(plan, provider=provider, output_path=args.output, timeout_seconds=600)
    report['resume_seconds'] = time.monotonic()-started
    report['status'] = result.status
    report['metadata'] = dict(result.metadata)
    report['publication_status'] = inspect_markdown_job(args.output)
    save()
    print(json.dumps(report, default=lambda v:dict(v)), flush=True)
    return 0 if result.status == 'complete' else 1


if __name__ == '__main__':
    raise SystemExit(main())
