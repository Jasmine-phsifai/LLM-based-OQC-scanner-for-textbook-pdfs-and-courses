# Merged recognition: cooperative safe stop

The user requested an orchestrator stop/continue control which allows the current
image or audio segment to finish and reach disk. OCRLLM owns that recognition
boundary; the orchestrator owns the persistent run/paused intent and process UI.
This change adds no scheduler, worker protocol, model control or checkpoint format.

## Public contract

The four existing `recognize_images_to_markdown`, `resume_images_to_markdown`,
`recognize_audio_to_markdown` and `resume_audio_to_markdown` functions accept
optional `stop_requested: object | None = None`. The object must expose
`is_set() -> bool`, following the existing cancellation signal protocol.
`None` preserves ordinary behavior. Signal checks must return promptly; keep a
request set until the library acknowledges it. A request observed once remains
latched for that invocation, even if the caller clears its signal early.

OCRLLM checks the signal before admitting the next provider attempt, including
same-model transient retries. For the ASR binary policy, this is **before** the
durable budget reservation. An admitted call finishes even when the signal is
set during reservation, encoding or HTTP. Its success, no-speech outcome or
provider error is checkpointed first. Every already admitted lane must drain;
the first `unit_result` is not a whole-job stop acknowledgement.

After all lanes have stopped and completed outcomes have been saved, the API
raises the existing `ocrllm.errors.Cancelled`, with code `CANCELLED` and details:

```json
{
  "safe_stop": true,
  "resume_available": true,
  "current_call_count": 2,
  "provider_calls_attempted": 2
}
```

Both counts mean actual provider calls accounted for in **this invocation**,
including failures. They do not include historical calls. A pre-set signal
creates/retains the validated resumable plan and returns these counts as zero.
The existing observation stage records `status=cancelled`, not `failed`.
Actual failed provider units remain failed units; stopping does not hide them.
A checkpoint write failure remains `OUTPUT_WRITE_FAILED` and never carries a
successful safe-stop acknowledgement.

After acknowledgement, the caller may stop its consumer process. To continue,
clear/recreate its signal and use the corresponding ordinary resume function
with the same inputs, output path and policy. Do not issue a fresh recognition
with overwrite. Settled results and usage are reused. Stopping after the last
successful checkpoint but before Markdown publication leaves a pending job;
resume publishes it with zero model calls. Already accepted-with-gaps jobs can
perform their existing zero-inference finalization without entering execution.

The signal is deliberately not passed into an in-flight provider adapter.
`Config.cancellation`, an observation sink, SIGSTOP and process termination are
not substitutes for this acknowledgement. A stop is cooperative: timeout and
failure bounds on the current provider call still govern how long it may take.
The checkpoint writer flushes/fsyncs its temporary file then atomically replaces
the state; this proves the process-stop boundary, not every hard-power-loss case.

## Retry and responsibility boundaries

When stopping during a transient retry wait, the retry helper sends its latest
returned `ProviderError` and cumulative usage back to the owner for checkpoint.
It does not discard that evidence by throwing cancellation immediately.
The optional stop path checks a long retry wait every 0.2 seconds; the default
path retains its existing single sleep. No busy polling occurs during inference.

ASR `AudioOutputLimitPolicy` reservations and split depth remain persistent.
Pauses cannot replenish the per-range initial request plus two retries. Only
the existing canonical `output_token_limit` failure permits subdivision; all
other classifications, successful siblings, uneven child ranges and short final
source intervals retain their existing behavior. `only_output_limit=True`
controls old fixed-interval resplitting, and does not filter a binary-policy
transient failure out of ordinary resume while that leaf has remaining budget.

This change does not add generic per-provider retry cursors to checkpoint
schemas. OCR and non-policy audio keep their existing ordinary-resume semantics:
a resumed unresolved slot applies the configured finite provider retry recipe
again. The persistent three-call guarantee applies to the opted-in ASR binary
policy. The orchestrator must preserve its own attempt accounting and must not
turn repeated process restarts into a new autonomous retry mechanism.

## Verification (2026-09-13)

`tools/verify_cooperative_safe_stop.py` uses real generated PNGs and a 121.375-second
FFmpeg MP3, the actual compatible SDK/HTTP adapter, and a deterministic local HTTP
server. It sends **zero real-model requests**. OS `replace` fault injection reaches
the reservation and durable publication boundaries without mocking OCRLLM internals.

The completed report is:
`/mnt/r/course-pipeline-state/validation/cooperative-safe-stop-20260913/owner-third/result.json`.
It proves:

- pre-set stop with zero calls/reservations, then ordinary resume;
- two image/audio lanes finish and persist before acknowledgement;
- transient retry wait preserves failure and usage, with the original
  `only_output_limit=True` resume parameters;
- final settled checkpoint publishes Markdown with zero resumed inference;
- no-speech result is settled before stopping;
- signal set while reservation is saved still permits the admitted request to
  finish, leaving no abandoned reservation;
- three successive cap failures separated by pauses retain exactly three
  reservations/evidence records, and cannot issue a fourth request;
- two split levels with 30/15/15-second leaves, successful sibling reuse and a
  1.375-second original tail;
- pause after the binary plan is saved, before any child reservation;
- checkpoint failure takes precedence over a simultaneous stop request;
- malformed signal rejection before dispatch.

The first two scenario runs exposed only assertions which assumed optional
zero-valued checkpoint fields were always serialized; corrected fixtures then
completed the full scenario. 69 existing merged-image/audio, provider-model and
import tests passed. Real production stop/continue is a separate orchestrator
deployment gate; this owner session neither restarted production nor called GPUs.
