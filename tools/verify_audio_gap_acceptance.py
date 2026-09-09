"""Verify explicit audio-gap policy with real encoded media and synthetic HTTP.

No model calls. Tests the public owner APIs, persistent cap evidence, visible
child output and zero-call recovery of an accepted terminal with retained state.
"""
import argparse
import json
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from ocrllm import (AudioGapPolicy, ProviderModel, OpenAICompatibleSettings, split_audio,
                    recognize_audio_to_markdown, resume_audio_to_markdown,
                    inspect_markdown_job, inspect_audio_completion)
from ocrllm.audio.load_audio_ffmpeg_executable import load_audio_ffmpeg_executable


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-dir',type=Path,required=True)
    args=parser.parse_args();args.work_dir.mkdir(parents=True,exist_ok=True)
    source=args.work_dir/'input.mp3'
    subprocess.run([str(load_audio_ffmpeg_executable()),'-nostdin','-v','error','-y',
        '-f','lavfi','-i','sine=frequency=440:sample_rate=16000','-t','241',
        '-c:a','libmp3lame',str(source)],check=True,timeout=30)
    outcomes=[(422,'output_token_limit'),(200,'Original first child.'),
        (422,'output_token_limit'),(422,'output_token_limit'),(422,'output_token_limit'),
        (200,'NOSPEECH4OCRLLM'),(200,'Original fourth child.'),(200,'Original tail child.')]
    calls=[]
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*a):pass
        def do_POST(self):
            data=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            assert all(x['type']=='input_audio' for x in data['messages'][0]['content'])
            status,value=outcomes[len(calls)];calls.append(data['model'])
            payload=({'error':{'code':value,'message':'Synthetic output failure'}} if status!=200 else
                {'id':f'chatcmpl-gap-{len(calls)}','model':'synthetic-audio',
                 'choices':[{'index':0,'finish_reason':'stop','message':{'role':'assistant','content':value}}],
                 'usage':{'prompt_tokens':12,'completion_tokens':8}})
            raw=json.dumps(payload).encode();self.send_response(status)
            self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)))
            self.end_headers();self.wfile.write(raw)
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=Thread(target=server.serve_forever,daemon=True);thread.start()
    provider=ProviderModel(vendor='scenario',model='synthetic-audio',adapter_id='openai_compatible_chat',
        settings=OpenAICompatibleSettings(base_url=f'http://127.0.0.1:{server.server_port}/v1',send_audio_prompt=False,audio_response_validation='visible_text'),
        supports_audio=True,supports_plain_ocr=False,supports_detail_ocr=False,
        default_image_batch_size=None,default_audio_minutes=1,retry_rules={})
    strict=AudioGapPolicy(max_failed_fraction=.2,max_failed_segment_seconds=120)
    permissive=AudioGapPolicy(max_failed_fraction=.3,max_failed_segment_seconds=120)
    try:
        plan=split_audio(source,interval_minutes=-1);out=args.work_dir/'audio.md';cp=args.work_dir/'audio.ocrllm-state.json'
        result=recognize_audio_to_markdown(plan,provider=provider,output_path=out,failed_slice_minutes=1,audio_gap_policy=strict)
        assert result.status=='partial' and len(calls)==8
        state=json.loads(cp.read_text());children=state['slots'][0]['subslots']
        assert children[1]['output_limit_attempts']==3 and children[1]['status']=='failed'
        assert children[2]['no_speech'] is True
        assert result.metadata['failed_seconds']==60 and not result.metadata['gap_threshold_met']
        assert 'Original first child.' in result.markdown and '**FAIL**' in result.markdown
        assert '60.000-120.000s' in result.markdown and 'OCRLLM_NO_SPEECH_AUDIO_SUBSLOT' in result.markdown
        before=cp.read_bytes();summary=inspect_audio_completion(out,audio_gap_policy=permissive)
        assert summary['would_accept_with_supplied_policy'] and not summary['accepted_with_gaps']
        assert cp.read_bytes()==before and len(calls)==8
        accepted=resume_audio_to_markdown(plan,provider=provider,output_path=out,audio_gap_policy=permissive)
        assert accepted.status=='complete_with_gaps' and accepted.metadata['provider_call_count']==0
        assert inspect_markdown_job(out)=='complete_with_gaps' and cp.exists()
        accepted_state=json.loads(cp.read_text())
        assert accepted_state['slots']==state['slots']
        assert accepted.metadata['accepted_with_gaps'] and accepted.metadata['failed_seconds']==60
        terminal=resume_audio_to_markdown(plan,provider=provider,output_path=out)
        assert terminal.status=='complete_with_gaps' and terminal.metadata['provider_call_count']==0 and len(calls)==8
        assert terminal.metadata['failed_segments']==accepted.metadata['failed_segments']
        assert terminal.markdown==accepted.markdown
        out.unlink()
        assert inspect_markdown_job(out)=='pending'
        rebuilt=resume_audio_to_markdown(plan,provider=provider,output_path=out)
        assert rebuilt.markdown==accepted.markdown and rebuilt.metadata['provider_call_count']==0
        assert inspect_markdown_job(out)=='complete_with_gaps' and len(calls)==8
        # Default route remains finite and does not gain the policy's two cap repeats.
        calls.clear();outcomes[:]=[(422,'output_token_limit'),(200,'Normal child.'),
            (422,'output_token_limit'),(200,'NOSPEECH4OCRLLM'),(200,'Other child.'),(200,'Tail child.')]
        default=recognize_audio_to_markdown(plan,provider=provider,output_path=args.work_dir/'default.md',failed_slice_minutes=1)
        assert default.status=='partial' and len(calls)==6
        default_state=json.loads((args.work_dir/'default.ocrllm-state.json').read_text())
        assert default_state['state_version']=='ocrllm.merged-audio-resume.v2'
        assert 'output_limit_attempts' not in default_state['slots'][0]['subslots'][1]
        prior_summary=inspect_audio_completion(args.work_dir/'default.md',audio_gap_policy=permissive)
        assert prior_summary['gap_threshold_met'] and not prior_summary['gap_retry_evidence_sufficient']
        # A legacy v2 failed response supplies no invented attempt history.
        calls.clear();outcomes[:]=[(422,'output_token_limit')]*3
        legacy=resume_audio_to_markdown(plan,provider=provider,output_path=args.work_dir/'default.md',audio_gap_policy=permissive)
        assert legacy.status=='complete_with_gaps' and legacy.metadata['provider_call_count']==3 and len(calls)==3
        legacy_state=json.loads((args.work_dir/'default.ocrllm-state.json').read_text())
        assert legacy_state['slots'][0]['subslots'][1]['output_limit_attempts']==3
        for index in (0,2,3,4):
            assert legacy_state['slots'][0]['subslots'][index]==default_state['slots'][0]['subslots'][index]
        short_source=args.work_dir/'short.mp3'
        subprocess.run([str(load_audio_ffmpeg_executable()),'-nostdin','-v','error','-y','-i',str(source),
                        '-t','61','-c:a','libmp3lame',str(short_source)],check=True,timeout=30)
        short_plan=split_audio(short_source,interval_minutes=1,include_boundary_context=False)
        for http_status,machine_code in ((422,'response_validation_failed'),(401,'invalid_api_key'),
                                         (429,'rate_limit'),(503,'service_unavailable')):
            calls.clear();outcomes[:]=[(http_status,machine_code),(200,'Unaffected successful tail.')]
            other=recognize_audio_to_markdown(short_plan,provider=provider,
                output_path=args.work_dir/f'{machine_code}.md',
                audio_gap_policy=AudioGapPolicy(max_failed_fraction=.99,max_failed_segment_seconds=120))
            assert other.status=='partial' and len(calls)==2
            assert not other.metadata['accepted_with_gaps'] and not other.metadata['gap_retry_evidence_sufficient']
        # Interrupt at the actual HTTP transport boundary after two cap outcomes
        # were checkpointed, before dispatching a third request.
        import httpx
        from ocrllm.errors import AllCandidatesExhausted
        whole_short=split_audio(short_source,interval_minutes=-1)
        interrupted_out=args.work_dir/'interrupted.md'
        calls.clear();outcomes[:]=[(422,'output_token_limit')]*3
        original_send=httpx.Client.send
        def interrupted_send(client,*a,**kw):
            if len(calls)==2:
                raise KeyboardInterrupt('Scenario interruption before third wire request')
            return original_send(client,*a,**kw)
        httpx.Client.send=interrupted_send
        try:
            recognize_audio_to_markdown(whole_short,provider=provider,output_path=interrupted_out,audio_gap_policy=permissive)
        except KeyboardInterrupt:pass
        else:raise AssertionError('Missing scenario interruption')
        finally:httpx.Client.send=original_send
        interrupted_cp=args.work_dir/'interrupted.ocrllm-state.json'
        assert len(calls)==2 and json.loads(interrupted_cp.read_text())['slots'][0]['output_limit_attempts']==2
        try:resume_audio_to_markdown(whole_short,provider=provider,output_path=interrupted_out)
        except AllCandidatesExhausted as error:assert error.details['provider_calls_attempted']==1
        else:raise AssertionError('An all-gap source cannot be accepted')
        assert len(calls)==3 and json.loads(interrupted_cp.read_text())['slots'][0]['output_limit_attempts']==3
        # A different returned reason breaks the consecutive output-limit count.
        calls.clear();outcomes[:]=[(422,'output_token_limit'),(422,'response_validation_failed')]
        changed_out=args.work_dir/'changed-reason.md'
        try:recognize_audio_to_markdown(whole_short,provider=provider,output_path=changed_out,audio_gap_policy=permissive)
        except AllCandidatesExhausted:pass
        else:raise AssertionError('Validation failure was accepted')
        assert len(calls)==2
        changed=json.loads((args.work_dir/'changed-reason.ocrllm-state.json').read_text())
        assert 'output_limit_attempts' not in changed['slots'][0]
        calls.clear();outcomes[:]=[(422,'output_token_limit')]*3
        try:resume_audio_to_markdown(whole_short,provider=provider,output_path=changed_out)
        except AllCandidatesExhausted:pass
        else:raise AssertionError('An all-gap source cannot be accepted')
        assert len(calls)==3
        report={'passed':True,'with_policy_calls':8,'long_parent_cap_calls':1,'short_failed_leaf_cap_calls':3,
            'accepted_terminal_resume_calls':0,'default_calls':6,'legacy_new_cap_calls':3,'noneligible_cases':4,'settled_children_and_no_speech_preserved':True,
            'real_model_calls':0,'synthetic_http':True,'interrupted_after_two_remaining_calls':1,'different_reason_resets_count':True,'missing_accepted_md_rebuilt_without_calls':True}
        (args.work_dir/'result.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
    finally:server.shutdown();server.server_close();thread.join()


if __name__=='__main__':main()
