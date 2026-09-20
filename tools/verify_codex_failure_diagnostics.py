"""Real OS process scenario; no network, credentials or model calls."""
import json
from pathlib import Path
import sys
import tempfile

from ocrllm import CodexCLISettings
from ocrllm.providers.codex_cli.usage_events import CodexUsageAttempt
from ocrllm.providers.codex_cli.run_codex_process import run_codex_process


def main():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        cases = [
            ("terminal", "import json; print(json.dumps({'type':'turn.failed', 'error':"
             "{'message':'You have hit your usage limit. HTTP 429 Bearer SECRET_SENTINEL'}}), flush=True)", False),
            ("timeout", "import sys,time; print('status code: 401 authentication failed SECRET_SENTINEL',"
             "file=sys.stderr,flush=True); print('connection timed out',file=sys.stderr,flush=True); time.sleep(10)", True),
        ]
        for name, code, timeout in cases:
            attempt = CodexUsageAttempt(settings=CodexCLISettings(usage_event_dir=root),
                model="scenario", source_paths=(root/'synthetic.jpg',), parent_call_id=name)
            attempt.started()
            exit_code, _, timed_out = run_codex_process(
                [sys.executable, '-c', code], timeout_seconds=.5 if timeout else 3, attempt=attempt)
            assert timed_out is timeout
            attempt.finish(spawned=True, exit_code=exit_code,
                outcome='timed_out' if timeout else 'failed', validation_status='not_run')
        events = [json.loads(line) for p in root.glob('*.jsonl') for line in p.read_text().splitlines()]
        finishes = [e['data'] for e in events if e['kind']=='codex_attempt_finished']
        first, second = [e['failure_diagnostics'][0] for e in finishes]
        assert first['source']=='turn.failed' and first['signals']==['usage_limit']
        assert first['http_status_codes']==[429]
        assert second['source']=='stderr_tail' and set(second['signals'])=={'authentication','connection','timeout'}
        assert second['http_status_codes']==[401]
        assert all(e['usage_capture_complete'] is False for e in finishes)
        assert 'SECRET_SENTINEL' not in json.dumps(events)
        attempt.record_diagnostic('stderr_tail', 'x'*20000 + ' timeout')
        assert attempt.common['failure_diagnostics'][-1]['truncated'] is True
        for i in range(20):
            attempt.record_diagnostic('error', str(i))
        assert len(attempt.common['failure_diagnostics'])==8
        print(json.dumps({'status':'passed','real_subprocesses':2,'model_calls':0,
                          'terminal_failure':first,'timeout_failure':second}, indent=2))


if __name__ == '__main__':
    main()
