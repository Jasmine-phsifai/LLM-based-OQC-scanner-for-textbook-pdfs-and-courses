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

## Read-only confirmation for the first old-consumer migration

The real old consumer did not load the new cooperative signal. A public durable
`unit_result` alone cannot prove that it has not already saved the next attempt's
reservation. The maintainer authorized a narrow read-only check for this exposed
migration gap, without a new checkpoint format or retry state machine.

`inspect_audio_completion(output_path)` now additionally returns:

```json
{
  "audio_dispatch_checkpoint_confirmed": true,
  "audio_dispatch_checkpoint_reason": "confirmed"
}
```

This is an assertion about the **saved v4 binary-policy checkpoint**, not a stop,
lock, model-idle assertion or acknowledgement from the old running process.
The caller must first prevent **all** consumer threads from issuing calls or
committing a new checkpoint, and keep that barrier through the reload decision.
Sending SIGSTOP alone is asynchronous: the caller must verify that the exact
process identity and all of its threads have actually stopped before querying.
It must separately establish its existing current-phase / final durable event /
model-idle and exclusive-maintenance conditions. A false result or any inspection
exception means the caller must restore the old consumer and reject this candidate.
This API does not authorize model termination; Model Lab still owns that lifecycle.

Only the saved v4 policy is evaluated. Missing state gives `missing_state`; a
legacy or non-policy state gives `unsupported_state`. Invalid/unreadable state
keeps the existing typed inspection error contract and cannot count as confirmed.
The optional policy arguments used to evaluate future recovery eligibility do
not change this assertion about the actual saved checkpoint.

For every current leaf, confirmation accepts an already `settled` result, or an
`unresolved` leaf with zero reservations. A cap-failed leaf needs a persisted
record whose exact logical start/end, split depth and **latest** attempt number
match its current reservation; explicitly unknown adopted history does not prove
that match. Missing/newer unconfirmed reservations give `unconfirmed_reservation`.
A non-cap failure gives `unverifiable_outcome`: the current schema lacks a general
per-attempt confirmation for those errors, so no inference is made from its text.
Ancestors which have already split are not executable leaves; their historical
unknown reservations do not block new zero-reservation children. No history is
removed, filled in or relabelled by inspection.

If a consumer is stopped before reservation `os.replace`, the committed state
still has no new reservation, and owner ordering proves no HTTP dispatch yet.
After reservation `os.replace`, the new count is visible but its outcome evidence
is absent, so the assertion is false even before HTTP starts. Completed outcome
`os.replace` restores a provable match. These ordering guarantees require the
caller barrier: a query against an actively changing process is insufficient.

Extended real-media/HTTP scenario output:
`/mnt/r/course-pipeline-state/validation/cooperative-safe-stop-20260913/owner-dispatch-confirmation/result.json`.
It checks the tempfile / atomic replace / pre-HTTP boundaries, old cap evidence
versus a new reservation, current unknown denial, split-ancestor history, unequal
leaves, no-speech/settled results, non-cap denial, legacy/unknown history, and
missing state. Each inspection compares checkpoint bytes and request counts before
and after, proving that this query does not mutate either. No real model was called.
32 existing merged-audio and import tests also passed.

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
