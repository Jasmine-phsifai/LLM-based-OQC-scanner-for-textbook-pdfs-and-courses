# Local service cooperation verification — 2026-09-06

## Scope and evidence levels

Maintainer-authorized implementation: independent OpenAI-compatible service in
Model Lab; explicit batching, bounded retry, output and resume in OCRLLM. No
production CLI, automatic course-frame selector, private cross-repo adapter or
new persistence protocol was introduced. Original unrelated working-tree edits
were preserved in both repositories.

Code inspection found two OCRLLM defects: merged checkpoints discarded safe
provider codes/request IDs, and HTTP 504 was classified as unavailable instead
of timeout. The fixes retain diagnostics in the existing 512-character failure
description and use the canonical timeout code for HTTP 408/504.

Model Lab changes address PID/listener identity, owned process-group cleanup,
restart, startup validation of configurable budgets, backend validation errors,
request-lock waiting and ASR generation completion. ASR timeout is cooperative
between generation steps, not hard kernel cancellation. No throughput or
recognition-accuracy improvement is inferred from configuration alone.

## Offline gates

- OCRLLM targeted provider/merged-image/merged-audio tests: 54 passed.
- Model Lab unittest discovery: 15 passed, including EOS acceptance/rejection.
- Lightweight `import ocrllm`: no Pillow, OpenAI, miniaudio, FastAPI or torch load.
- Recovery tool against a synthetic HTTP server: passed. For each modality,
  first request is injected 429; later requests are injected 503 then 504;
  initial partial result accounts for four calls; resume makes one call and
  reuses one settled slot. Timeout code, safe service code and request ID survive
  the saved checkpoint. Ten total proxy requests, six injected responses.
  This is tool/harness verification, not real model inference or overload proof.

## Real-media gates

The first managed session was PID 13399. An initial 2-image request through the
public OCRLLM merged-image API passed: 2,373 input / 1,334 output tokens,
203.705 seconds including cold model loading. The corresponding ASR request
used 832 input / 4 output tokens in 36.894 seconds. That near-silent excerpt is
not counted as meaningful speech-quality evidence; a speech-bearing excerpt
was prepared for subsequent checks.

Final real recovery used two selected full-frame course images and a bounded
24 kHz mono speech MP3 (about 61 seconds), with two pure logical audio slices.
On managed session PID 18868, each modality passed all of:

- injected 429 on attempt 1, 503 on attempt 3, 504 on attempt 4;
- initial partial result, four accounted calls, one failed slot;
- saved canonical timeout code plus service code and request ID;
- resumed complete result, one new provider call, one reused settled slot;
- nonempty real output and unchanged source hashes.

Total: ten HTTP proxy requests, six deliberate fault responses and four actual
successful model requests. These injected faults prove client behavior; they
are not a measurement of spontaneous service overload. No whole screenshot
folder or full-length course audio was sent.

The first idle-service SIGKILL check exposed an uncaught connection reset in the
manager readiness probe. After catching that OS/network boundary, the maintained
`check_local_qwen_lifecycle.py --exercise-crash` passed: old PID 18868 disappeared,
one orphan backend was identified, saved ownership remained available, the old
HTTP listener stopped, the old process group was removed, and two managed starts
established new identities (21393, then 21399). The service was left running.

Live validation-only HTTP checks also passed: invalid JSON 400 `invalid_json`,
unknown model 404 `model_not_found`, missing image 422 `image_required`, unsupported
WAV request 415 `invalid_audio_format`, and nine images 400 `invalid_request`.
Every response carried a request ID. These checks dispatch no model inference.

Startup configuration probes rejected context 1024 with default output 4096,
image minimum 2048 with default maximum 1024, and a NaN queue wait; an explicit
16384 context was accepted by configuration validation only. No inference or
VRAM claim is made for that larger setting.


A final direct ASR call on the speech-bearing 24 kHz mono excerpt, after the
restart on PID 21399, returned `finish_reason=stop`, 240 text characters,
817 input / 147 output tokens in 42.063 seconds including cold loading.
The output was not the no-speech sentinel. This establishes meaningful speech
output, not a word-error-rate or ground-truth accuracy measurement.

## Practical limits

Two-image recognition and independent short audio slices are live-proven here.
Eight-image context fit, sustained concurrent throughput, full-course accuracy
and tensor batching of independent ASR requests are not established by this run.
The client still uses ordinary per-slice Chat requests, and the single GPU
serializes backend access. OCR quality was not ground-truth scored. Existing
model speed/quality benchmark history remains separate evidence.

The repositories remain decoupled; the future CLI and duration-sensitive frame
selection are not implemented in this task. Test media and recognition text
remain outside Git. Safe run summaries contain no course content or identifying
archive paths.
