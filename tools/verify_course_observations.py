"""Verify owner observations via public APIs, real media and synthetic HTTP only."""
import argparse
from collections import Counter
import io
import json
import logging
from pathlib import Path
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread, Lock

from PIL import Image
from ocrllm import (observation_context, batchify_images, split_audio,
    recognize_images_to_markdown, resume_images_to_markdown,
    recognize_audio_to_markdown, resume_audio_to_markdown,
    ProviderModel, OpenAICompatibleSettings, AudioGapPolicy,
    select_extracted_frames, RetainedVideoFrame)
from ocrllm.audio.load_audio_ffmpeg_executable import load_audio_ffmpeg_executable


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--work-dir',type=Path,required=True)
    root=parser.parse_args().work_dir;root.mkdir(parents=True,exist_ok=True)
    events=root/'events.jsonl';outcomes=[];calls=[];lock=Lock()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_POST(self):
            data=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            with lock:
                status,text=outcomes.pop(0);calls.append(data['model']);index=len(calls)
            body=({'error':{'code':text,'message':'PRIVATE_BODY_MUST_NOT_BE_OBSERVED'}} if status!=200 else
                {'id':f'chatcmpl-{index}','model':data['model'],'choices':[{'index':0,'finish_reason':'stop',
                 'message':{'role':'assistant','content':text}}],'usage':{'prompt_tokens':12,'completion_tokens':8}})
            raw=json.dumps(body).encode();self.send_response(status)
            self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)))
            self.send_header('x-request-id',f'request-{index}');self.end_headers();self.wfile.write(raw)
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler);Thread(target=server.serve_forever,daemon=True).start()
    settings=OpenAICompatibleSettings(base_url=f'http://127.0.0.1:{server.server_port}/v1',
        send_audio_prompt=False,response_validation='nonempty_text',audio_response_validation='visible_text')
    def provider(model,audio=False,retries=None):
        return ProviderModel(vendor='scenario',model=model,adapter_id='openai_compatible_chat',settings=settings,
            supports_audio=audio,supports_plain_ocr=not audio,supports_detail_ocr=not audio,
            default_audio_minutes=1 if audio else None,default_image_batch_size=None if audio else 1,
            retry_rules=retries or {})
    images=[]
    for index in range(2):
        path=root/f'frame_{index:06d}.jpg';Image.new('RGB',(96,64),(index*100,100,220)).save(path);images.append(path)
    source=root/'source.mp3'
    subprocess.run([str(load_audio_ffmpeg_executable()),'-nostdin','-v','error','-y','-f','lavfi','-i',
        'sine=frequency=440:sample_rate=16000','-t','121','-c:a','libmp3lame',str(source)],check=True,timeout=30)
    try:
        image_provider=provider('image',retries={'PROVIDER_UNAVAILABLE':('current',1,0)})
        audio_provider=provider('audio',audio=True)
        with observation_context(path=events,lecture_id='synthetic-lecture',runtime_version='scenario'):
            frames=tuple(RetainedVideoFrame(path=path,frame_index=i,timestamp_seconds=i*60.0) for i,path in enumerate(images))
            select_extracted_frames(frames,duration_seconds=121)
            batches=batchify_images(tuple(images),batch_size=1)
            outcomes[:]=[(500,'service_error'),(422,'validation_error'),(200,'PRIVATE_VALID_TEXT')]
            result=recognize_images_to_markdown(batches,provider=[[image_provider],[image_provider]],
                output_path=root/'image.md',image_task='course_ocr')
            assert result.status=='partial'
            outcomes[:]=[(200,'PRIVATE_VALID_TEXT')]
            result=resume_images_to_markdown(batches,provider=image_provider,output_path=root/'image.md')
            assert result.status=='complete'
            plan=split_audio(source,interval_minutes=-1)
            outcomes[:]=[(422,'output_token_limit'),(200,'NOSPEECH4OCRLLM'),
                (422,'output_token_limit'),(422,'output_token_limit'),(422,'output_token_limit'),(200,'PRIVATE_VALID_TEXT')]
            result=recognize_audio_to_markdown(plan,provider=audio_provider,output_path=root/'audio.md',
                failed_slice_minutes=1,audio_gap_policy=AudioGapPolicy(max_failed_fraction=.5,max_failed_segment_seconds=120))
            assert result.status=='complete_with_gaps'
            resume_audio_to_markdown(plan,provider=audio_provider,output_path=root/'audio.md')
        rows=[json.loads(line) for line in events.read_text().splitlines()]
        starts={row['data']['attempt_id']:row for row in rows if row['kind']=='attempt_started'}
        ends=[row for row in rows if row['kind']=='attempt_finished']
        assert len(starts)==len(ends)==len(calls)==10
        assert all(row['data']['attempt_id'] in starts and row['data']['elapsed_seconds']>=0 for row in ends)
        assert all(row['data'].get('request_id') for row in ends)
        assert all(row['data']['lecture_id']=='synthetic-lecture' for row in rows)
        assert sum(row['data']['valid_units'] for row in ends if row['task']=='ocr')==2
        audio_seconds=sum(row['data']['valid_units'] for row in ends if row['task']=='asr')
        assert abs(audio_seconds-(result.metadata['duration_seconds']-60))<1e-6
        assert all(row['data']['valid_units']==0 for row in ends if row['data']['status']=='failed')
        reused=[row for row in rows if row['kind']=='unit_result' and row['data']['reused']]
        assert len(reused)==3 and all(row['data']['valid_units']==0 for row in reused)
        assert any(row['kind']=='plan' and row['data'].get('parent_unit_id') for row in rows)
        assert any(row['kind']=='stage_finished' and row['data'].get('accepted_with_gaps') for row in rows)
        assert any(row['kind']=='stage_finished' and row['data'].get('stage')=='prepare_audio_clip' for row in rows)
        assert 'PRIVATE_' not in events.read_text() and 'base_url' not in events.read_text()
        # Observation failure is isolated; no exception text or payload leaks through its warning.
        messages=io.StringIO();handler=logging.StreamHandler(messages);logger=logging.getLogger('ocrllm.observation');logger.addHandler(handler)
        def broken_sink(event):raise OSError('PRIVATE_SINK_MESSAGE')
        outcomes[:]=[(200,'PRIVATE_VALID_TEXT')]
        with observation_context(sink=broken_sink,lecture_id='sink-failure'):
            result=recognize_images_to_markdown((batches[0],),provider=image_provider,output_path=root/'sink-failure.md',image_task='course_ocr')
        logger.removeHandler(handler)
        assert result.status=='complete' and 'recognition continues' in messages.getvalue() and 'PRIVATE_' not in messages.getvalue()
        report={'passed':True,'actual_synthetic_http_calls':len(calls),'observed_calls':len(ends),
            'ocr_new_frames':2,'asr_new_seconds':audio_seconds,'reused_units':len(reused),
            'failed_attempts':sum(row['data']['status']=='failed' for row in ends),
            'worker_context_propagated':True,'sink_failure_isolated':True,'real_model_calls':0,
            'event_kinds':dict(Counter(row['kind'] for row in rows))}
        (root/'result.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
    finally:server.shutdown();server.server_close()


if __name__=='__main__':main()
