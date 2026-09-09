"""Inspect or execute one explicitly selected audio gap trial through OCRLLM.

The ordinary production program must coordinate its idle window. This tool
never starts/stops services and never writes a checkpoint directly. A second
optional output is inspected only. The trial disables transient retries to
keep the selected old leaf at most three new HTTP calls; the owner cap policy
is otherwise the same as production.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import time

from ocrllm import (AudioGapPolicy, OpenAICompatibleSettings, ProviderModel,
    split_audio, resume_audio_to_markdown, inspect_audio_completion, OCRLLMError)
from ocrllm.build_merged_audio_resume_state import build_merged_audio_resume_state
from ocrllm.contracts.source_fingerprint import SourceFingerprint
from ocrllm.resolve_audio_slice_mode import resolve_audio_slice_mode
from ocrllm.run_merged_audio_job import _validate_resume_plan
from ocrllm.output.load_merged_audio_resume_state import load_merged_audio_resume_state
from ocrllm.output.resolve_resume_state_path import resolve_resume_state_path


def hash_file(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def successful_leaves(state):
    return {(parent.index, leaf.logical_start_seconds, leaf.logical_end_seconds):leaf
        for parent in state.slots for leaf in parent.subslots or (parent,) if leaf.status=='settled'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--inspect-only-output',type=Path)
    parser.add_argument('--evidence-dir',type=Path,required=True)
    parser.add_argument('--base-url',required=True)
    parser.add_argument('--model',required=True)
    parser.add_argument('--vendor',default='local-course')
    parser.add_argument('--interval-minutes',type=int,default=10)
    parser.add_argument('--max-failed-fraction',type=float,required=True)
    parser.add_argument('--max-failed-segment-seconds',type=float,required=True)
    parser.add_argument('--max-failed-seconds',type=float)
    parser.add_argument('--timeout-seconds',type=float,default=600)
    parser.add_argument('--execute',action='store_true')
    args=parser.parse_args();args.evidence_dir.mkdir(parents=True,exist_ok=True)
    policy=AudioGapPolicy(max_failed_fraction=args.max_failed_fraction,
        max_failed_segment_seconds=args.max_failed_segment_seconds,max_failed_seconds=args.max_failed_seconds)
    cp=resolve_resume_state_path(args.output)
    before=load_merged_audio_resume_state(cp)
    summary=inspect_audio_completion(args.output,audio_gap_policy=policy)
    record={'started_at':datetime.now(timezone.utc).isoformat(),'executed':args.execute,
        'ocrllm_commit':subprocess.check_output(['git','-C',str(Path(__file__).resolve().parents[1]),'rev-parse','HEAD'],text=True).strip(),
        'source_path':str(args.source),'source_sha256_before':hash_file(args.source),
        'output_path':str(args.output),'checkpoint_sha256_before':hash_file(cp),
        'before':summary,'trial_transient_retry_rules':{},'production_transient_rules_changed':False}
    plan=split_audio(args.source,interval_minutes=args.interval_minutes,include_boundary_context=False)
    mode, interval, prompt_version=resolve_audio_slice_mode(plan,duration_seconds=plan[-1].logical_end_seconds)
    requested=build_merged_audio_resume_state(plan,mode=mode,interval_minutes=interval,
        prompt_version=prompt_version,source=SourceFingerprint(uri=args.source.resolve().as_uri(),
            byte_size=args.source.stat().st_size,sha256=record['source_sha256_before']))
    _validate_resume_plan(before,requested)
    record['original_plan_match']={'verified':True,'method':'Existing OCRLLM resume plan validator',
        'mode':mode,'interval_minutes':interval,'prompt_version':prompt_version,'parent_slots':len(plan)}
    other=None
    if args.inspect_only_output:
        other=resolve_resume_state_path(args.inspect_only_output)
        record['inspection_only']={'output':str(args.inspect_only_output),'before':inspect_audio_completion(args.inspect_only_output,audio_gap_policy=policy),'checkpoint_sha256_before':hash_file(other)}
    target=args.evidence_dir/('result.json' if args.execute else 'prepared.json')
    if not args.execute:
        target.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'prepared':str(target),'model_calls':0}));return
    # This bounded real trial is only for the one selected <=120s output-cap gap.
    failures=summary['failed_segments']
    if (not summary['gap_threshold_met'] or len(failures)!=1 or not failures[0]['output_token_limit']
        or summary['unresolved_segment_count']):
        raise ValueError('The requested target is not the one eligible short-leaf trial')
    if target.exists():
        raise ValueError('Do not repeat this completed trial; inspect its persistent result')
    (args.evidence_dir/'before-audio.ocrllm-state.json').write_bytes(cp.read_bytes())
    provider=ProviderModel(vendor=args.vendor,model=args.model,adapter_id='openai_compatible_chat',
        settings=OpenAICompatibleSettings(base_url=args.base_url,send_audio_prompt=False,
            response_validation='nonempty_text',audio_response_validation='visible_text'),
        supports_audio=True,supports_plain_ocr=False,supports_detail_ocr=False,
        default_image_batch_size=None,default_audio_minutes=args.interval_minutes,retry_rules={})
    start=time.monotonic()
    try:
        result=resume_audio_to_markdown(plan,provider=provider,output_path=args.output,
            audio_gap_policy=policy,timeout_seconds=args.timeout_seconds)
        from collections.abc import Mapping
        def plain(value):
            if isinstance(value,Mapping):return {k:plain(v) for k,v in value.items()}
            if isinstance(value,tuple):return [plain(v) for v in value]
            return value
        record['result']={'status':result.status,'metadata':plain(result.metadata),'warnings':list(result.warnings)}
    except OCRLLMError as error:
        record['error']={'code':error.code,'message':str(error),'details':str(error.details)}
    finally:
        record.update(wall_seconds=time.monotonic()-start,finished_at=datetime.now(timezone.utc).isoformat(),
            source_sha256_after=hash_file(args.source),checkpoint_sha256_after=hash_file(cp),output_sha256=hash_file(args.output))
        record['after']=inspect_audio_completion(args.output)
        old=successful_leaves(before)
        if cp.exists():
            new=successful_leaves(load_merged_audio_resume_state(cp))
            record['settled_leaf_preservation']={'method':'Compare original settled leaf dataclass values by parent/range; no state mutation',
                'count':len(old),'all_unchanged':all(new.get(key)==leaf for key,leaf in old.items())}
        else:
            markdown=args.output.read_text()
            record['settled_leaf_preservation']={'method':'Completed state removed; verify all original successful leaf text is present in final MD',
                'count':len(old),'all_text_retained':all(leaf.no_speech or leaf.markdown.strip() in markdown for leaf in old.values())}
        if other:
            record['inspection_only']['checkpoint_sha256_after']=hash_file(other)
            record['inspection_only']['unchanged']=hash_file(other)==record['inspection_only']['checkpoint_sha256_before']
        target.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'evidence':str(target),'status':record.get('result',{}).get('status'),'error':record.get('error',{}).get('code')}))


if __name__=='__main__':main()
