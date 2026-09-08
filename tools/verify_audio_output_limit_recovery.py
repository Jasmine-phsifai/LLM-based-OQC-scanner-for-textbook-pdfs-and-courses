"""Verify opt-in finite recovery through real media and a synthetic HTTP boundary.

The server responses are deliberately synthetic; this proves public recovery
and accounting, not transcription quality or model capability.
"""
import argparse
import json
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from ocrllm import (ProviderModel, OpenAICompatibleSettings, split_audio,
                    recognize_audio_to_markdown, resume_audio_to_markdown, inspect_markdown_job)
from ocrllm.audio.load_audio_ffmpeg_executable import load_audio_ffmpeg_executable
from ocrllm.errors import AllCandidatesExhausted


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-dir', required=True, type=Path)
    args = parser.parse_args()
    args.work_dir.mkdir(parents=True, exist_ok=True)
    source = args.work_dir/'synthetic.mp3'
    subprocess.run([str(load_audio_ffmpeg_executable()), '-nostdin', '-v', 'error', '-y',
                    '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=16000', '-t', '61',
                    '-c:a', 'libmp3lame', str(source)], check=True, timeout=30)
    calls = []
    machine_code = 'output_token_limit'
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            assert all(item['type']=='input_audio' for item in body['messages'][0]['content'])
            calls.append(body['model'])
            failed = len(calls)==1
            response = ({'error': {'code':machine_code, 'message':'Synthetic test rejection'}} if failed else
                        {'id': f'chatcmpl-synthetic-{len(calls)}', 'model':'synthetic-audio', 'choices': [{'index':0,'finish_reason':'stop', 'message':{'role':'assistant','content':f'Synthetic transcript piece {len(calls)}.'}}], 'usage':{'prompt_tokens':12, 'completion_tokens':8}})
            encoded = json.dumps(response).encode()
            self.send_response(422 if failed else 200)
            self.send_header('Content-Type','application/json')
            self.send_header('Content-Length',str(len(encoded)))
            self.end_headers(); self.wfile.write(encoded)
    server = ThreadingHTTPServer(('127.0.0.1',0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True); thread.start()
    provider = ProviderModel(vendor='scenario', model='synthetic-audio', adapter_id='openai_compatible_chat',
        settings=OpenAICompatibleSettings(base_url=f'http://127.0.0.1:{server.server_port}/v1',send_audio_prompt=False),
        supports_audio=True,supports_plain_ocr=False,supports_detail_ocr=False,
        default_image_batch_size=None,default_audio_minutes=1,retry_rules={})
    try:
        plan = split_audio(source, interval_minutes=-1)
        output = args.work_dir/'recovered.md'
        result = recognize_audio_to_markdown(plan, provider=provider, output_path=output, failed_slice_minutes=1)
        assert result.status=='complete' and result.metadata['provider_call_count']==3
        assert len(calls)==3 and inspect_markdown_job(output)=='complete'
        assert result.metadata['provider_failures'][0]['code']=='PROVIDER_REQUEST_INVALID'
        calls.clear()
        saved_output = args.work_dir/'saved-cap.md'
        try:
            recognize_audio_to_markdown(plan, provider=provider, output_path=saved_output)
            raise AssertionError('An unconfigured initial cap must fail')
        except AllCandidatesExhausted:
            assert len(calls)==1
        resumed = resume_audio_to_markdown(plan, provider=provider, output_path=saved_output,
                                          failed_slice_minutes=1, only_output_limit=True)
        assert resumed.status=='complete' and resumed.metadata['provider_call_count']==2
        assert len(calls)==3  # Saved original cap was not sent again.
        calls.clear(); machine_code = 'response_validation_failed'
        try:
            recognize_audio_to_markdown(plan,provider=provider,output_path=args.work_dir/'invalid.md',failed_slice_minutes=1)
            raise AssertionError('Non-budget rejection must stay failed')
        except AllCandidatesExhausted:
            assert len(calls)==1
        print(json.dumps({'passed':True,'automatic_cap_calls':3,'non_budget_calls':1,'saved_cap_resume_calls':2,'real_model_calls':0,'synthetic_http':True}))
    finally:
        server.shutdown();server.server_close();thread.join()
    return 0


if __name__=='__main__':
    raise SystemExit(main())
