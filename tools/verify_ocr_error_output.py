"""Verify rejected OCR output through a real SDK/HTTP boundary, without a model."""
from __future__ import annotations

import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
import tempfile
import threading

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from ocrllm import (AllCandidatesExhausted, OpenAICompatibleSettings, ProviderModel,
                    recognize_images_to_markdown, resume_images_to_markdown)

RAW = '原始输出，不改写 <svg>图</svg>\n' * 1000
THINKING = 'separate reasoning\n' * 1000
OUTPUT = {'message': {'content': RAW, 'reasoning_content': THINKING},
          'finish_reason': 'length', 'context_tokens': 8192, 'max_output_tokens': 7168,
          'usage': {'prompt_tokens': 1642, 'completion_tokens': 6550, 'total_tokens': 8192},
          'artifact_saved': True, 'artifact_path': '/private/ocr/request.json'}


class Handler(BaseHTTPRequestHandler):
    responses = []
    calls = 0

    def do_POST(self):
        self.rfile.read(int(self.headers['Content-Length']))
        type(self).calls += 1
        success = type(self).responses.pop(0)
        body = ({'id': 'chatcmpl-synthetic', 'object': 'chat.completion', 'created': 0,
                 'model': 'synthetic', 'choices': [{'index': 0, 'finish_reason': 'stop',
                 'message': {'role': 'assistant', 'content': 'saved successful frame'}}],
                 'usage': {'prompt_tokens': 10, 'completion_tokens': 5, 'total_tokens': 15}}
                if success else {'error': {'code': 'output_token_limit',
                 'message': 'do not copy arbitrary error-message secrets',
                 'details': {'generation_output': OUTPUT, 'api_key': 'DO-NOT-COPY'}}})
        raw = json.dumps(body).encode()
        self.send_response(200 if success else 422)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(raw)))
        self.send_header('x-request-id', 'chatcmpl-' + 'a' * 32)
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *args):
        pass


def main():
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'frame.png'
            source.write_bytes(base64.b64decode(
                'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk'
                '+A8AAQUBAScY42YAAAAASUVORK5CYII='))
            def provider(capture):
                return ProviderModel(vendor='synthetic', model='synthetic',
                    adapter_id='openai_compatible_chat', supports_plain_ocr=True,
                    supports_detail_ocr=False, supports_audio=False,
                    default_image_batch_size=1, default_audio_minutes=None, retry_rules={},
                    settings=OpenAICompatibleSettings(base_url=f'http://127.0.0.1:{server.server_port}/v1',
                        api_key='synthetic', capture_error_output=capture))
            for capture in (False, True):
                Handler.responses = [False]
                try:
                    recognize_images_to_markdown(((source,),), provider=provider(capture),
                        image_task='plain_ocr', output_path=root / f'all-failed-{capture}.md', timeout_seconds=5)
                except AllCandidatesExhausted as error:
                    failures = error.details.get('provider_failures', ())
                    assert bool(failures) == capture
                    if capture:
                        evidence = failures[0]['details']['generation_output']
                        assert evidence['message']['content'] == RAW
                        assert evidence['message']['reasoning_content'] == THINKING
                    assert 'DO-NOT-COPY' not in repr(error.details)
                else:
                    raise AssertionError('Truncated output accepted')
            Handler.responses = [True, False]
            output = root / 'mixed.md'
            plan = ((source,), (source,))
            result = recognize_images_to_markdown(plan, provider=provider(True), image_task='plain_ocr', output_path=output, timeout_seconds=5)
            assert result.status == 'partial'
            assert result.metadata['provider_failures'][0]['details']['generation_output']['message']['content'] == RAW
            assert RAW not in output.read_text() and 'saved successful frame' in output.read_text()
            before = Handler.calls
            Handler.responses = [False]
            result = resume_images_to_markdown(plan, provider=provider(True), output_path=output, timeout_seconds=5)
            assert Handler.calls - before == 1 and result.metadata['reused_slot_count'] == 1
            assert result.metadata['provider_failures'][0]['details']['generation_output']['message']['reasoning_content'] == THINKING
            assert result.status == 'partial'
            print(json.dumps({'passed': True, 'http_calls': Handler.calls, 'model_calls': 0,
                              'raw_characters_preserved': len(RAW), 'reasoning_characters_preserved': len(THINKING),
                              'default_redaction': True, 'resume_reuses_success': True}))
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


if __name__ == '__main__':
    main()
