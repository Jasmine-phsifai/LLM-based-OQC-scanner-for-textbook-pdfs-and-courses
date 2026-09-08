"""Measure real selected-course recognition; keep inputs and Markdown private.

The input is a private JSON manifest with a courses list. Each row contains id,
audio_path and selected_images (ordered paths). Run one modality per invocation
to keep warm-model measurements comparable. Timers wrap only real HTTP and
subprocess boundaries; no OCRLLM function is replaced or response fabricated.
"""
from __future__ import annotations

import argparse
from collections.abc import Mapping
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import subprocess
import time


def fingerprint(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def json_default(value):
    if isinstance(value, Mapping):
        return dict(value)
    raise TypeError(type(value).__name__)


def emit(path, record):
    line = json.dumps(record, ensure_ascii=True, sort_keys=True, default=json_default)
    with path.open('a', encoding='utf-8') as stream:
        stream.write(line + '\n')
    print(line, flush=True)


@contextmanager
def timed_boundaries(events, log_path, course_id, phase):
    import httpx
    original_send = httpx.Client.send
    original_run = subprocess.run

    def send(client, request, *args, **kwargs):
        started = time.perf_counter()
        row = {'event': 'http', 'course_id': course_id, 'phase': phase}
        try:
            if phase == 'image':
                body = json.loads(request.content)
                content = body['messages'][0]['content']
                prompts = [item['text'] for item in content if item.get('type') == 'text']
                row['prompt_sha256'] = hashlib.sha256('\n'.join(prompts).encode()).hexdigest()
                row['prompt_characters'] = sum(map(len, prompts))
                row['image_count'] = sum(item.get('type') == 'image_url' for item in content)
            if phase == 'audio':
                content = json.loads(request.content)['messages'][0]['content']
                row['text_item_count'] = sum(item.get('type') == 'text' for item in content)
                row['audio_item_count'] = sum(item.get('type') == 'input_audio' for item in content)
            response = original_send(client, request, *args, **kwargs)
            row['http_status'] = response.status_code
            row['request_id'] = response.headers.get('x-request-id')
            if response.status_code == 200:
                body = response.json()
                row['usage'] = body.get('usage')
                choices = body.get('choices', [])
                row['finish_reason'] = choices[0].get('finish_reason') if choices else None
                text = choices[0].get('message', {}).get('content') if choices else None
                row['text_characters'] = len(text) if isinstance(text, str) else 0
            else:
                try:
                    row['provider_code'] = response.json().get('error', {}).get('code')
                except (ValueError, AttributeError):
                    row['provider_code'] = None
            return response
        finally:
            row['seconds'] = time.perf_counter() - started
            events.append(row)
            emit(log_path, row)

    def run(*args, **kwargs):
        started = time.perf_counter()
        try:
            return original_run(*args, **kwargs)
        finally:
            command = args[0] if args else kwargs.get('args', ())
            if isinstance(command, (list, tuple)) and 'libmp3lame' in command:
                row = {'event': 'ffmpeg_clip', 'course_id': course_id, 'phase': phase,
                       'seconds': time.perf_counter() - started}
                events.append(row)
                emit(log_path, row)

    httpx.Client.send = send
    subprocess.run = run
    try:
        yield
    finally:
        httpx.Client.send = original_send
        subprocess.run = original_run


def provider(args, image):
    from ocrllm import ProviderModel, OpenAICompatibleSettings
    return ProviderModel(
        vendor='local-benchmark',
        model=args.image_model if image else args.audio_model,
        adapter_id='openai_compatible_chat',
        settings=OpenAICompatibleSettings(
            base_url=args.base_url,
            send_audio_prompt=not args.no_audio_prompt,
            response_validation=args.response_validation,
        ),
        supports_plain_ocr=image, supports_detail_ocr=image, supports_audio=not image,
        default_image_batch_size=args.batch_size if image else None,
        default_audio_minutes=None if image else args.audio_minutes,
        retry_rules={code: ('current', 1, 2) for code in (
            'PROVIDER_RATE_LIMITED', 'PROVIDER_UNAVAILABLE', 'PROVIDER_TIMEOUT')},
    )


def benchmark(args, row):
    from ocrllm import (
        batchify_images, recognize_images_to_markdown, resume_images_to_markdown,
        split_audio, recognize_audio_to_markdown, resume_audio_to_markdown,
    )
    from ocrllm.errors import OCRLLMError
    image = args.phase == 'image'
    identity = row['id']
    sources = tuple(Path(p) for p in row['selected_images']) if image else (Path(row['audio_path']),)
    before = tuple(fingerprint(p) for p in sources)
    output = args.output_root / f'{identity}-{args.phase}.md'
    log_path = args.output_root / 'events.jsonl'
    settings = provider(args, image)
    events = []
    summary = {'event': 'course_result', 'course_id': identity, 'phase': args.phase,
               'image_count': len(sources) if image else None,
               'image_task': args.image_task if image else None,
               'batch_size': args.batch_size if image else None,
               'audio_minutes': args.audio_minutes if not image else None,
               'resumed_run': args.resume}
    emit(log_path, {'event': 'course_start', 'course_id': identity, 'phase': args.phase,
                    'source_count': len(sources)})
    started = time.perf_counter()
    with timed_boundaries(events, log_path, identity, args.phase):
        try:
            planning_started = time.perf_counter()
            if image:
                plan = batchify_images(sources, batch_size=args.batch_size)
            else:
                plan = split_audio(sources[0], interval_minutes=args.audio_minutes,
                                   include_boundary_context=False)
            summary['planning_seconds'] = time.perf_counter() - planning_started
            summary['planned_slots'] = len(plan)
            if image:
                function = resume_images_to_markdown if args.resume else recognize_images_to_markdown
                extra = {} if args.resume else {'image_task': args.image_task}
            else:
                function = resume_audio_to_markdown if args.resume else recognize_audio_to_markdown
                extra = {}
                summary['audio_duration_seconds'] = plan[-1].logical_end_seconds
            result = function(plan, provider=settings, output_path=output,
                              timeout_seconds=args.timeout, **extra)
            summary['status'] = result.status
            if image:
                summary['image_task'] = result.profile
            summary['text_characters'] = len(result.markdown)
            for key in ('provider_call_count', 'settled_slot_count', 'no_speech_slot_count',
                        'reused_slot_count', 'current_provider_model_usage', 'failed_slots'):
                if key in result.metadata:
                    summary[key] = result.metadata[key]
        except OCRLLMError as error:
            summary['status'] = 'failed'
            summary['code'] = error.code
            summary['failed_slots'] = error.details.get('failed_slots')
            summary['provider_call_count'] = error.details.get('provider_calls_attempted', 0)
    summary['wall_seconds'] = time.perf_counter() - started
    summary['http_seconds'] = sum(e['seconds'] for e in events if e['event'] == 'http')
    summary['ffmpeg_seconds'] = sum(e['seconds'] for e in events if e['event'] == 'ffmpeg_clip')
    summary['sources_unchanged'] = before == tuple(fingerprint(p) for p in sources)
    summary['passed'] = summary.get('status') == 'complete' and summary['sources_unchanged']
    emit(log_path, summary)
    target = args.output_root / f'{identity}-{args.phase}-{"resume" if args.resume else "initial"}.json'
    target.write_text(json.dumps(summary, ensure_ascii=True, indent=2, default=json_default), encoding='utf-8')
    return summary['passed']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', required=True, type=Path)
    parser.add_argument('--output-root', required=True, type=Path)
    parser.add_argument('--phase', required=True, choices=('image', 'audio'))
    parser.add_argument('--image-task', choices=('plain_ocr', 'detail_ocr', 'course_ocr'),
                        default='course_ocr')
    parser.add_argument('--course-id')
    parser.add_argument('--base-url', default='http://127.0.0.1:38871/v1')
    parser.add_argument('--image-model', default='qwen3.8-27b-q6-k-medium-ocr')
    parser.add_argument('--audio-model', default='qwen3-asr-1.7b')
    parser.add_argument('--batch-size', type=int, default=1)
    parser.add_argument('--audio-minutes', type=int, default=30)
    parser.add_argument('--timeout', type=float, default=600)
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--no-audio-prompt', action='store_true')
    parser.add_argument('--response-validation', choices=('markdown', 'nonempty_text'), default='markdown')
    args = parser.parse_args()
    if not 1 <= args.batch_size <= 8 or not 1 <= args.audio_minutes <= 30 or not 0 < args.timeout <= 600:
        parser.error('Use batch size1–8, audio interval1–30 minutes, timeout<=600 seconds.')
    args.output_root.mkdir(parents=True, exist_ok=True)
    rows = json.loads(args.manifest.read_text(encoding='utf-8'))['courses']
    selected = [row for row in rows if args.course_id is None or row['id'] == args.course_id]
    if not selected or len(selected) > 3:
        parser.error('Select one to three explicit courses.')
    passed = True
    for row in selected:
        if args.phase == 'image' and not 1 <= len(row['selected_images']) <= 120:
            parser.error('Only already-selected image sets (at most120) may reach inference.')
        passed = benchmark(args, row) and passed
    raise SystemExit(0 if passed else 1)


if __name__ == '__main__':
    main()
