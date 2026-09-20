"""Capture image metadata from the real CLI against an unauthenticated loopback fake API.

No auth files, cloud inference, raw HTTP headers, image base64, or prompts are
persisted. Temporary CLI home contains only the caller-selected model cache.
"""
import argparse
import base64
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

from PIL import Image
from ocrllm.profiles.build_legacy_course_ocr_prompt import build_legacy_course_ocr_prompt
from ocrllm.providers.codex_cli.build_codex_exec_command import build_codex_exec_command, build_codex_exec_prompt
from ocrllm.providers.codex_cli.stage_codex_images import stage_codex_images


def describe(raw):
    with Image.open(io.BytesIO(raw)) as im:
        rgb = im.convert('RGB')
        return {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw),
                'dimensions': list(im.size), 'format': im.format,
                'rgb_sha256': hashlib.sha256(rgb.tobytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--model-cache', type=Path, required=True)
    parser.add_argument('--work-dir', type=Path, required=True)
    parser.add_argument('--model-verbosity', choices=('low', 'high'))
    args = parser.parse_args()
    args.work_dir.mkdir(parents=True, exist_ok=False)
    selected = json.loads(args.config.read_text())['image_provider']
    cache = args.model_cache.read_bytes()
    records = []
    active = {}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            self.send_error(404)

        def do_POST(self):
            try:
                raw = self.rfile.read(int(self.headers['Content-Length']))
                encoding = self.headers.get('Content-Encoding', '')
                if encoding == 'gzip':
                    raw = gzip.decompress(raw)
                elif encoding:
                    raise ValueError('unsupported_content_encoding:' + encoding)
                body = json.loads(raw)
                images, texts = [], []
                for item in body.get('input', []):
                    for content in item.get('content', []) if isinstance(item.get('content'), list) else []:
                        if content.get('type') == 'input_image':
                            url = content['image_url']
                            assert url.startswith('data:') and ';base64,' in url
                            decoded = base64.b64decode(url.split(';base64,', 1)[1], validate=True)
                            images.append({**describe(decoded), 'detail': content.get('detail')})
                        elif content.get('type') == 'input_text':
                            texts.append(content['text'])
                matches = [re.search(r'（JSON数组，仅作文件身份映射）：(\[[^\n]*\])。', text) for text in texts]
                names = [json.loads(match.group(1)) for match in matches if match]
                row = {'group': active['group'], 'path': self.path, 'model': body.get('model'),
                       'reasoning': body.get('reasoning'), 'text': body.get('text'),
                       'service_tier': body.get('service_tier'), 'images': images,
                       'prompt_source_name_arrays': names, 'authorization_present': 'Authorization' in self.headers}
                records.append(row)
                (args.work_dir/'requests.json').write_text(json.dumps(records, indent=2))
                response = {'id': 'resp_local_synthetic', 'object': 'response', 'created_at': 0,
                    'status': 'completed', 'model': selected['model'],
                    'output': [{'id':'msg_local','type':'message','role':'assistant','status':'completed',
                        'content':[{'type':'output_text','text':'Synthetic loopback capture complete.','annotations':[]}]}],
                    'usage':{'input_tokens':0,'output_tokens':0,'total_tokens':0}}
                events = [
                    ('response.created', {'type':'response.created','response':{**response,'status':'in_progress','output':[]}}),
                    ('response.output_item.added', {'type':'response.output_item.added','output_index':0,'item':response['output'][0]}),
                    ('response.output_text.delta', {'type':'response.output_text.delta','output_index':0,'content_index':0,'item_id':'msg_local','delta':'Synthetic loopback capture complete.'}),
                    ('response.output_item.done', {'type':'response.output_item.done','output_index':0,'item':response['output'][0]}),
                    ('response.completed', {'type':'response.completed','response':response}),
                ]
                payload = ''.join('event: '+kind+'\ndata: '+json.dumps(event)+'\n\n' for kind,event in events).encode()
                self.send_response(200)
                self.send_header('Content-Type','text/event-stream')
                self.send_header('Content-Length',str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
            except Exception as error:
                (args.work_dir/'capture-error.txt').write_text(type(error).__name__ + ': ' + str(error)[:160])
                self.send_error(400)

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    report = {'cli_version': subprocess.check_output([selected['command'],'--version'],text=True).strip(),
              'cli_binary': selected['command'], 'cache_sha256': hashlib.sha256(cache).hexdigest(),
              'real_cloud_model_calls':0, 'requested_model_verbosity':args.model_verbosity, 'groups':[]}
    try:
        for group in json.loads(args.manifest.read_text())['groups']:
            active['group'] = group['name']
            sources = tuple(Path(p) for p in group['images'])
            expected = [describe(p.read_bytes()) for p in sources]
            with tempfile.TemporaryDirectory(prefix='ocrllm-wire-') as tmp:
                isolated = Path(tmp)
                home = isolated/'codex-home'; home.mkdir()
                (home/'models_cache.json').write_bytes(cache)
                staged = stage_codex_images(sources, isolated)
                prompt = build_codex_exec_prompt(build_legacy_course_ocr_prompt(tuple(p.name for p in sources)),
                    len(sources), source_names=tuple(p.name for p in sources))
                argv = build_codex_exec_command(command=selected['command'], model=selected['model'],
                    reasoning_effort=selected.get('reasoning_effort','low'), fast_mode=False,
                    service_tier=selected.get('service_tier','default'), image_paths=staged,
                    cwd=isolated, output_path=isolated/'last.txt', prompt=prompt)
                overrides = ['model_provider="loopback_capture"',
                    'model_providers.loopback_capture.name="Loopback capture"',
                    f'model_providers.loopback_capture.base_url="http://127.0.0.1:{server.server_port}/v1"',
                    'model_providers.loopback_capture.wire_api="responses"',
                    'model_providers.loopback_capture.requires_openai_auth=false',
                    'model_providers.loopback_capture.request_max_retries=0',
                    'model_providers.loopback_capture.stream_max_retries=0',
                    'model_providers.loopback_capture.stream_idle_timeout_ms=10000']
                if args.model_verbosity is not None:
                    overrides.append('model_verbosity=' + json.dumps(args.model_verbosity))
                index = argv.index('--')
                argv[index:index] = [part for value in overrides for part in ('-c',value)]
                env = {'PATH':os.environ.get('PATH','/usr/bin:/bin'), 'LANG':'C.UTF-8', 'CODEX_HOME':str(home),
                       'HTTP_PROXY':'http://127.0.0.1:1','HTTPS_PROXY':'http://127.0.0.1:1',
                       'ALL_PROXY':'http://127.0.0.1:1','NO_PROXY':'127.0.0.1,localhost'}
                try:
                    proc = subprocess.run(argv, env=env, capture_output=True, timeout=45)
                    code = proc.returncode
                    # No raw stdout/stderr: only known warning classifications.
                    warnings = {label: marker in proc.stderr.decode(errors='replace') for label,marker in {
                        'model_fallback':'fallback', 'cache_warning':'cache', 'auth_warning':'auth'}.items()}
                except subprocess.TimeoutExpired:
                    code, warnings = 'timeout', {}
            captured = [row for row in records if row['group']==group['name']]
            summary = {'group':group['name'], 'exit_code':code, 'warning_signals':warnings,
                       'source_names':[p.name for p in sources], 'expected':expected, 'requests':len(captured)}
            if captured:
                summary['bytes_and_order_equal'] = all(
                    len(row['images'])==len(expected) and all(
                        all(original[key]==actual[key] for key in original)
                        for original,actual in zip(expected,row['images'])) for row in captured)
                summary['prompt_mapping_equal'] = all(row['prompt_source_name_arrays']==[[p.name for p in sources]] for row in captured)
            report['groups'].append(summary)
            (args.work_dir/'result.json').write_text(json.dumps(report,indent=2))
            print(json.dumps({k:v for k,v in summary.items() if k!='expected'}),flush=True)
    finally:
        server.shutdown(); server.server_close(); thread.join()
    passed = (len(report['groups']) == 3 and len(records) == 3
              and all(row['exit_code'] == 0 and row['requests'] == 1
                      and row.get('bytes_and_order_equal') is True
                      and row.get('prompt_mapping_equal') is True for row in report['groups'])
              and all(row['authorization_present'] is False for row in records)
              and (args.model_verbosity is None or all(
                  (row.get('text') or {}).get('verbosity') == args.model_verbosity for row in records))
              and not (args.work_dir/'capture-error.txt').exists())
    report['passed'] = passed
    (args.work_dir/'result.json').write_text(json.dumps(report,indent=2))
    if not passed:
        raise SystemExit('CLI wire capture failed; inspect the durable result.json')


if __name__ == '__main__':
    main()
